// SPDX-License-Identifier: GPL-2.0
/*
 * fb_ili9488.c - fbtft framebuffer driver for ILI9488 SPI LCDs
 *
 * Why this version:
 * - ILI9488 native resolution is 320x480
 * - Many ILI9488 SPI panels want COLMOD = 0x66 (18-bit mode)
 * - Linux framebuffer is usually RGB565 (16bpp)
 * - So we convert RGB565 -> 3 bytes/pixel when sending to the panel
 *
 * This should help with:
 * - "everything looks blue"
 * - white bar / missing lines caused by wrong geometry
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>   /* gpiod_set_value() */

#include "fbtft.h"

#define DRVNAME "fb_ili9488"
#define WIDTH   320
#define HEIGHT  480
#define BPP     16
#define FPS     30

/*
 * Common ILI9488 init sequence for SPI panels.
 *
 * Important:
 *   0x3A = 0x66  => 18-bit pixel format on panel side
 * We keep Linux framebuffer at 16bpp and convert in write_vmem().
 */
static const s16 default_init_sequence[] = {
        /* Positive Gamma Control */
        -1, 0xE0, 0x00, 0x03, 0x09, 0x08, 0x16, 0x0A,
                 0x3F, 0x78, 0x4C, 0x09, 0x0A, 0x08, 0x16, 0x1A, 0x0F,

        /* Negative Gamma Control */
        -1, 0xE1, 0x00, 0x16, 0x19, 0x03, 0x0F, 0x05,
                 0x32, 0x45, 0x46, 0x04, 0x0E, 0x0D, 0x35, 0x37, 0x0F,

        /* Power Control 1 */
        -1, 0xC0, 0x17, 0x15,

        /* Power Control 2 */
        -1, 0xC1, 0x41,

        /* VCOM Control */
        -1, 0xC5, 0x00, 0x12, 0x80,

        /*
         * MADCTL default.
         * set_var() will overwrite this later depending on rotation/bgr.
         */
        -1, 0x36, 0x48,

        /*
         * COLMOD:
         * 0x66 = 18-bit mode
         */
        -1, 0x3A, 0x66,

        /* Interface Mode Control */
        -1, 0xB0, 0x00,

        /* Frame Rate Control */
        -1, 0xB1, 0xA0,

        /* Display Inversion Control */
        -1, 0xB4, 0x02,

        /* Display Function Control */
        -1, 0xB6, 0x02, 0x02, 0x3B,

        /* Entry Mode Set */
        -1, 0xB7, 0xC6,

        /* Adjust Control 3 */
        -1, 0xF7, 0xA9, 0x51, 0x2C, 0x82,

        /* Sleep Out */
        -1, 0x11,
        -2, 120,

        /* Display ON */
        -1, 0x29,
        -2, 20,

        /* end marker */
        -3
};

/*
 * Set active drawing window
 */
static void set_addr_win(struct fbtft_par *par, int xs, int ys, int xe, int ye)
{
        /* Column address set */
        write_reg(par, 0x2A,
                  xs >> 8, xs & 0xFF,
                  xe >> 8, xe & 0xFF);

        /* Page address set */
        write_reg(par, 0x2B,
                  ys >> 8, ys & 0xFF,
                  ye >> 8, ye & 0xFF);

        /* Memory write */
        write_reg(par, 0x2C);
}

/*
 * Convert framebuffer pixels from RGB565 (16-bit) to 3 bytes/pixel.
 *
 * Why:
 *   panel is in 18-bit mode (0x3A = 0x66)
 *   Linux framebuffer is 16bpp
 * So we expand each pixel to:
 *   R8, G8, B8
 *
 * The ILI9488 in SPI mode is happy with this style of 3-byte pixel stream.
 */
static int write_vmem16_18bus8(struct fbtft_par *par, size_t offset, size_t len)
{
        u16 *vmem16;
        u8  *txbuf = par->txbuf.buf;
        size_t remain_pixels;
        size_t to_copy;
        size_t max_pixels_per_chunk;
        int i;
        int ret = 0;

        /* Number of pixels remaining in this framebuffer update */
        remain_pixels = len / 2;
        vmem16 = (u16 *)(par->info->screen_buffer + offset);

        /* Put D/C into DATA mode before streaming pixels */
        if (par->gpio.dc)
                gpiod_set_value(par->gpio.dc, 1);

        /* Each pixel becomes 3 bytes in tx buffer */
        max_pixels_per_chunk = par->txbuf.len / 3;

        while (remain_pixels) {
                to_copy = min(max_pixels_per_chunk, remain_pixels);

                for (i = 0; i < to_copy; i++) {
                        u16 p = vmem16[i];

                        /* RGB565 extraction */
                        u8 r5 = (p >> 11) & 0x1F;
                        u8 g6 = (p >> 5)  & 0x3F;
                        u8 b5 = (p >> 0)  & 0x1F;

                        /* Expand to 8-bit channels */
                        u8 r8 = (r5 << 3) | (r5 >> 2);
                        u8 g8 = (g6 << 2) | (g6 >> 4);
                        u8 b8 = (b5 << 3) | (b5 >> 2);

                        txbuf[i * 3 + 0] = r8;
                        txbuf[i * 3 + 1] = g8;
                        txbuf[i * 3 + 2] = b8;
                }

                vmem16 += to_copy;
                remain_pixels -= to_copy;

                ret = par->fbtftops.write(par, txbuf, to_copy * 3);
                if (ret < 0)
                        return ret;
        }

        return ret;
}

/*
 * Rotation and color-order handling.
 *
 * MADCTL bits:
 *   MY  = 0x80
 *   MX  = 0x40
 *   MV  = 0x20
 *   BGR = 0x08
 */
static int set_var(struct fbtft_par *par)
{
        u8 madctl;

        switch (par->info->var.rotate) {
        case 0:
                madctl = 0x80;
                break;
        case 90:
                madctl = 0x20;
                break;
        case 180:
                madctl = 0x40;
                break;
        case 270:
                madctl = 0xE0;
                break;
        default:
                madctl = 0x80;
                break;
        }

        /* Apply BGR bit if requested by core/device-tree */
        if (par->bgr)
                madctl |= 0x08;

        write_reg(par, 0x36, madctl);
        return 0;
}

static struct fbtft_display display = {
        .regwidth = 8,
        .width    = WIDTH,
        .height   = HEIGHT,
        .bpp      = BPP,
        .fps      = FPS,
        .init_sequence = default_init_sequence,
        .fbtftops = {
                .set_addr_win = set_addr_win,
                .set_var      = set_var,
                .write_vmem   = write_vmem16_18bus8,
        },
};

FBTFT_REGISTER_DRIVER(DRVNAME, "ilitek,ili9488", &display);

MODULE_ALIAS("spi:" DRVNAME);
MODULE_ALIAS("platform:" DRVNAME);
MODULE_ALIAS("spi:ili9488");
MODULE_ALIAS("platform:ili9488");

MODULE_DESCRIPTION("FB driver for the ILI9488 LCD controller (SPI, RGB565->18-bit write)");
MODULE_AUTHOR("Oswaldo + ChatGPT");
MODULE_LICENSE("GPL");
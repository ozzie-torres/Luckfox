
#include "fbdev.h"
#include "lvgl/lvgl.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/fb.h>

static int fbfd;
static uint8_t *fbp;
static struct fb_var_screeninfo vinfo;
static struct fb_fix_screeninfo finfo;

static lv_color_t *buf;
static lv_disp_draw_buf_t draw_buf;
static lv_disp_drv_t disp_drv;

static void fb_flush(lv_disp_drv_t *disp,const lv_area_t *area,lv_color_t *color_p)
{
    for(int y=area->y1;y<=area->y2;y++)
    {
        for(int x=area->x1;x<=area->x2;x++)
        {
            long location=(x+vinfo.xoffset)*(vinfo.bits_per_pixel/8)+
                          (y+vinfo.yoffset)*finfo.line_length;

            *((uint16_t*)(fbp+location))=color_p->full;
            color_p++;
        }
    }

    lv_disp_flush_ready(disp);
}

void fbdev_init(void)
{
    fbfd=open("/dev/fb0",O_RDWR);

    ioctl(fbfd,FBIOGET_FSCREENINFO,&finfo);
    ioctl(fbfd,FBIOGET_VSCREENINFO,&vinfo);

    long screensize=vinfo.yres_virtual*finfo.line_length;

    fbp=(uint8_t*)mmap(0,screensize,PROT_READ|PROT_WRITE,MAP_SHARED,fbfd,0);

    buf=malloc(vinfo.xres*40*sizeof(lv_color_t));

    lv_disp_draw_buf_init(&draw_buf,buf,NULL,vinfo.xres*40);

    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res=vinfo.xres;
    disp_drv.ver_res=vinfo.yres;
    disp_drv.flush_cb=fb_flush;
    disp_drv.draw_buf=&draw_buf;

    lv_disp_drv_register(&disp_drv);
}

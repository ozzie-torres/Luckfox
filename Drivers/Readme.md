Since the ILI9488 is not in the mainline 5.10 kernel, you need to manually add the source files to your Luckfox SDK. 
Most ILI9488 drivers for Linux are "single-file" drivers that integrate into the fbtft framework, meaning you only need the .c file (the header info is usually contained within it).

1. The Source Code (fb_ili9488.c)
Copy the file named fb_ili9488.c in the directory:


2. Register the Driver in the Kernel
You must tell the Linux build system that this new file exists.
A. Edit the Makefile:
Open <SDK>/sysdrv/source/kernel/drivers/staging/fbtft/Makefile and add this line:
makefile
obj-$(CONFIG_FB_TFT_ILI9488)     += fb_ili9488.o


B. Edit the Kconfig:
Open <SDK>/sysdrv/source/kernel/drivers/staging/fbtft/Kconfig and add this block:
kconfig
config FB_TFT_ILI9488
    tristate "FB driver for the ILI9488 LCD controller"
    depends on FB_TFT
    help
      Generic Framebuffer driver for ILI9488 LCD displays.

3. Enable and Compile
Menuconfig: Run ./build.sh kernelconfig in the SDK root.
Navigate: Device Drivers -> Staging drivers -> Support for small TFT LCD display modules.
Select: Find FB driver for the ILI9488 and set it to <*> (Built-in).
Save and Exit.
Build: Run ./build.sh kernel.

4. Device Tree (DTS) Setup
Add this to your rv1106g-luckfox-pico-pro-max.dts under the &spi0 node:
dts
ili9488@0 {
    compatible = "ilitek,ili9488";
    reg = <0>;
    spi-max-frequency = <24000000>;
    fps = <30>;
    buswidth = <8>;
    reset-gpios = <&gpio1 RK_PC2 GPIO_ACTIVE_LOW>; // Pin 34
    dc-gpios = <&gpio1 RK_PC3 GPIO_ACTIVE_HIGH>;   // Pin 35
    status = "okay";
};


Important Note: The ILI9488 over SPI requires 3 bytes per pixel (RGB666). If the screen looks "shifted" or colors are wrong, you may need to apply a small patch to fbtft-bus.c in the same directory to handle the 24-bit SPI transfer.

To falsh boot.img you can use the SocToolkit from luckfox for the SD card you basically flash the original Ubuntu image provided by luckfox and only flash the new boot.img that contains the new kernel module and the dts for this driver to work in your ili9488 lcd touch screen.

For development we build the driver as a module in the kernel so we only compile once flash it to the luckfox pico device and then only compile the module and copy to the target to test. Here is what we did :
# ILI9488 SPI LCD on Luckfox Pico (RV1106)

Clean reproducible guide to build and run the **ILI9488 framebuffer driver** using the **Luckfox SDK kernel build system**.

This README documents the **exact steps used during bring‑up**, including:

* kernel configuration
* module compilation using the SDK
* where `.ko` files are generated
* how to deploy them to the target
* how to verify the display

The goal is that **any engineer can reproduce the working setup later.**

---

# 1. System Overview

Hardware used:

* Luckfox Pico Pro / Max (RV1106)
* SPI ILI9488 LCD
* Resolution: **320 x 480**

Kernel:

```
Linux 5.10.160
```

Framebuffer driver:

```
fbtft + fb_ili9488
```

Framebuffer format:

```
RGB565 (16bpp)
```

Panel format:

```
18‑bit SPI (ILI9488 COLMOD = 0x66)
```

---

# 2. SDK Build Environment

All work was performed inside the **Luckfox SDK container environment**.

Important paths:

```
SDK root
/home

Kernel source
/home/sysdrv/source/kernel

Kernel build output
/home/sysdrv/source/objs_kernel
```

Driver location:

```
drivers/staging/fbtft
```

Compiled modules appear in the **output tree**, not the source tree.

```
/home/sysdrv/source/objs_kernel/drivers/staging/fbtft/
```

---

# 3. Kernel Configuration

Open the kernel configuration:

```bash
cd /home
./build.sh kernelconfig
```

Enable the following **as modules**:

```
CONFIG_FB_TFT=m
CONFIG_FB_TFT_ILI9488=m
```

These produce:

```
fbtft.ko
fb_ili9488.ko
```

## Required Backlight Options

Some Rockchip drivers require the backlight subsystem to be built‑in.

Set these to **built‑in (y)**:

```
CONFIG_BACKLIGHT_CLASS_DEVICE=y
CONFIG_FB_BACKLIGHT=y
CONFIG_BACKLIGHT_PWM=y
CONFIG_LCD_CLASS_DEVICE=y
```

These fix the linker error:

```
undefined reference to of_find_backlight_by_node
```

---

# 4. Build the Kernel

Run the normal SDK build:

```bash
cd /home
./build.sh kernel
```

This produces the kernel image and device tree.

However, the `.ko` modules are rebuilt separately.

---

# 5. Prepare Kernel Tree for Module Builds

Enter the kernel source directory:

```bash
cd /home/sysdrv/source/kernel
```

Set build environment variables:

```bash
export O=/home/sysdrv/source/objs_kernel
export ARCH=arm
export CROSS_COMPILE=/home/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf/bin/arm-rockchip830-linux-uclibcgnueabihf-
```

Prepare the kernel build tree:

```bash
make O=$O ARCH=$ARCH CROSS_COMPILE=$CROSS_COMPILE prepare
make O=$O ARCH=$ARCH CROSS_COMPILE=$CROSS_COMPILE modules_prepare
```

---

# 6. Compile Only the ILI9488 Modules

Clean and rebuild the fbtft directory:

```bash
make O=$O ARCH=$ARCH CROSS_COMPILE=$CROSS_COMPILE M=drivers/staging/fbtft clean

make O=$O ARCH=$ARCH CROSS_COMPILE=$CROSS_COMPILE M=drivers/staging/fbtft modules
```

---

# 7. Locate Generated Modules

The compiled modules appear in the **kernel output tree**:

```
/home/sysdrv/source/objs_kernel/drivers/staging/fbtft/
```

Expected files:

```
fbtft.ko
fb_ili9488.ko
```

Verify:

```bash
ls -lh /home/sysdrv/source/objs_kernel/drivers/staging/fbtft/*.ko
```

---

# 8. Copy Modules to the Target

From the SDK container:

```bash
scp /home/sysdrv/source/objs_kernel/drivers/staging/fbtft/fbtft.ko pico@DEVICE_IP:/tmp/

scp /home/sysdrv/source/objs_kernel/drivers/staging/fbtft/fb_ili9488.ko pico@DEVICE_IP:/tmp/
```

---

# 9. Load Modules on the Target

SSH into the Luckfox board.

## Disable framebuffer console

```bash
sudo sh -c 'echo 0 > /sys/class/vtconsole/vtcon1/bind'
```

Verify:

```bash
cat /sys/class/vtconsole/vtcon1/bind
```

Expected:

```
0
```

---

## Unload existing modules

```bash
sudo rmmod fb_ili9488 2>/dev/null || true
sudo rmmod fbtft 2>/dev/null || true
```

---

## Load modules

```bash
sudo insmod /tmp/fbtft.ko
sudo insmod /tmp/fb_ili9488.ko
```

---

# 10. Verify Framebuffer

Check framebuffer device:

```bash
ls -l /dev/fb0
```

Check resolution:

```bash
cat /sys/class/graphics/fb0/virtual_size
```

Expected:

```
320,480
```

Check color depth:

```bash
cat /sys/class/graphics/fb0/bits_per_pixel
```

Expected:

```
16
```

---

# 11. Display Test

Use Python to write raw pixels to the framebuffer.

Create `test.py`:

```python
fb = "/dev/fb0"
w = 320
h = 480


def fill565(value):
    data = value.to_bytes(2, "little") * (w * h)
    with open(fb, "wb") as f:
        f.write(data)

print("Black")
fill565(0x0000)
input("Press Enter for RED")

print("Red")
fill565(0xF800)
input("Press Enter for GREEN")

print("Green")
fill565(0x07E0)
input("Press Enter for BLUE")

print("Blue")
fill565(0x001F)
```

Run:

```bash
python3 test.py
```

This confirms:

* framebuffer writes
* correct color mapping
* correct geometry

---

# 12. Common Problems

## Module dependency error

```
Unknown symbol fbtft_probe_common
```

Load modules in correct order:

```
fbtft.ko
fb_ili9488.ko
```

---

## "module PLT section(s) missing"

This usually means the module was not built with the same kernel output tree.

Rebuild using the same SDK kernel build directory.

---

## Missing `.ko` files

Remember:

Modules appear in the **output tree**, not the source tree.

```
objs_kernel/.../fbtft
```

---

## Wrong resolution / white bar

ILI9488 native resolution:

```
320 x 480
```

Incorrect values like:

```
480 x 320
```

will cause partial rendering or white lines.

---

# 13. Recommended Final Driver Settings

Working configuration:

```
WIDTH  = 320
HEIGHT = 480
BPP    = 16
COLMOD = 0x66 (18‑bit SPI)
```

Driver should implement:

```
set_addr_win()
set_var()
write_vmem()
```

And use modern GPIO API:

```
gpiod_set_value()
```

not:

```
gpio_set_value()
```

---

# 14. Result

Working system:

✔ full screen rendering

✔ correct framebuffer geometry

✔ correct RGB colors

✔ reproducible module build

---

# 15. Future Improvements

Possible improvements:

* autoload module at boot
* integrate driver directly into kernel
* device‑tree overlay for SPI display
* support rotation configuration

---

# Author Notes

This document was created during the bring‑up of the ILI9488 SPI LCD on the Luckfox Pico platform and is intended to make the process **fully reproducible for future developers.**

Here is a test script commands in bash 

#!/bin/sh

echo "Testing LCD"

printf '\x00\xf8%.0s' $(seq $((320*480))) > /dev/fb0
sleep 1

printf '\xe0\x07%.0s' $(seq $((320*480))) > /dev/fb0
sleep 1

printf '\x1f\x00%.0s' $(seq $((320*480))) > /dev/fb0
sleep 1

echo "LCD OK"
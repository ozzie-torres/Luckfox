Assumptions

Before starting, it is assumed that you have already followed the official Luckfox documentation to:

Download the Luckfox SDK (container version)
Download the Ubuntu base image for the device
Set up Docker and verified the SDK builds correctly

* SDK Guide:
https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/SDK-Image-Compilation/

* Ubuntu Image compiled:
https://drive.google.com/drive/folders/14kFWY93MZ4Zga4ke2PVQgUs1y9xcMG0S

* Ubuntu Git Source Image:
git clone https://github.com/LuckfoxTECH/luckfox-pico.git

We are NOT rebuilding the full OS image.

Instead, we:

Use the official Ubuntu image as base
Build a custom kernel inside the SDK container
Generate a new boot.img
Replace the original boot.img from the Ubuntu image
Flash the updated image to the SD card

Step 1 — Start the SDK Container
Mount your SDK directory into the container (example):
```
sudo docker run -it   -v $(pwd):/home   luckfoxtech/luckfox_pico:1.0   /bin/bash
```

Step 2 — Apply ILI9488 Driver & DTS Changes
Inside the SDK :

Copy or apply the modified driver:
```
/home/luckfox-pico/sysdrv/source/kernel/drivers/staging/fbtft/fb_ili9488.c
```
Copy - Replace or apply the modified dts and dtsi files in this Repo to the following folder in SDK :
```
/home/luckfox-pico/sysdrv/source/kernel/arch/arm/boot/dts/rv1106g-luckfox-pico-pro-max.dts
/home/luckfox-pico/sysdrv/source/kernel/arch/arm/boot/dts/rv1106-luckfox-pico-pro-max-ipc.dtsi
```
Modify also these 2 files so you can see the ili9488 driver in the kernelconfig menu

At the end add on File 1 nano sysdrv/source/kernel/drivers/staging/fbtft/Kconfig 
```
config FB_TFT_ILI9488
	tristate "FB driver for the ILI9488 LCD Controller"
	depends on FB_TFT
	help
	  Framebuffer support for ILI9488-based SPI displays.
```
At the end add on File 2 nano sysdrv/source/kernel/drivers/staging/fbtft/Makefile   
```
obj-$(CONFIG_FB_TFT_ILI9488) += fb_ili9488.o
```

Step 3 — Configure Build Target
/home/luckfox-pico/ ./build.sh lunch

Select your board:
rv1106_luckfox_pico_pro_max

Select your boot medium:
SD_CARD

Select system version:
buildroot

Step 4 — Configure Kernel with new driver
```
/home/luckfox-pico#  ./build.sh kernelconfig
```
Select * for the ili9488 driver and if you need Touch screen also enable ADS7846 driver
Don't forget to save and exit

Step 5 build the boot.img
```
/home/luckfox-pico# ./build.sh kernel 
```
step 6  Image Flashing SD Card 

Collect the boot.img from the container SDK
```
/home/luckfox-pico/sysdrv/out/image_uclibc_rv1106/boot.img
```

Format the SD Card preferable with the luckfox SD CARD tool
```
https://wiki.luckfox.com/Tools/SDCardFormatter.zip
```
Flash the SD Card with SocToolKit Version: v1.98 luckfox tool
```
https://wiki.luckfox.com/Tools/SocToolKit_v1.98_win.zip
```
Follow their steps and remember to replace their boot.img for the one we just created
```
https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/Flash-image#42-flashing-image-to-tf-card
```

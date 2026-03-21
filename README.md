This Repository is to start working with luckfox development board, the idea is to interact with multiple interfaces and potentially make a carrier board for this luckfox little embedded board.

So far we are using the following:
* Our hardware is luckfox Pico Pro Max.
* We are building drivers and software by using and following the luckfox SDK on this link (https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/SDK) in container version.
* As starting point we are using the ubuntu 22 image provided by luckfox (https://drive.google.com/drive/folders/14kFWY93MZ4Zga4ke2PVQgUs1y9xcMG0S).
* We are Using the luckfox SOCtoolkit to burn it in to an SD card here are the instructions (https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/Flash-image).
* For the fb_ili9488.c driver provided here we are basically including as part of the kernel , building the kernel and burning that change on the boot.img part of the ubuntu image only.
  
   
This repository is a starting point for development with the Luckfox Pico Pro Max. The main goal is to explore the board’s interfaces, build custom drivers and software, and eventually support a custom carrier board for this compact embedded platform.

Current workflow:

- **Hardware:** Luckfox Pico Pro Max
- **SDK / Build System:** Official Luckfox SDK  
  https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/SDK
- **Build Environment:** Containerized Ubuntu 22 SDK image provided by Luckfox  
  https://drive.google.com/drive/folders/14kFWY93MZ4Zga4ke2PVQgUs1y9xcMG0S
- **Flashing Tool:** Luckfox SocToolKit for writing images to SD card  
  https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/Flash-image

At this stage, the repository focuses on integrating the `fb_ili9488.c` driver directly into the kernel, rebuilding the kernel, and replacing only the `boot.img` portion of the Ubuntu image with the updated version.

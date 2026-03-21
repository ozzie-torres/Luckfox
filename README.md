This repository is a starting point for development with the Luckfox Pico Pro Max. The main goal is to explore the board’s interfaces, build custom drivers and software, and eventually support a custom carrier board for this compact embedded platform.

Current workflow:

- **Hardware:** Luckfox Pico Pro Max
- **SDK / Build System:** Official Luckfox SDK  
  https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/SDK
- **Build Environment:** Containerized Ubuntu 22 SDK image provided by Luckfox  
  https://drive.google.com/drive/folders/14kFWY93MZ4Zga4ke2PVQgUs1y9xcMG0S
- **Flashing Tool:** Luckfox SocToolKit for writing images to SD card  
  https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/Flash-image

Stage 1, the repository focuses on integrating the `fb_ili9488.c` driver directly into the kernel, rebuilding the kernel, and replacing only the `boot.img` portion of the Ubuntu image with the updated version.


# LuckFox LVGL HMI Starter

Minimal but scalable project template for building a GUI on LuckFox boards using LVGL and the Linux framebuffer.

## Structure

src/
  main.c
  platform/
      fbdev.c
      fbdev.h
  gui/
      screen_manager.c
      screen_manager.h
      screens/
          screen_home.c
          screen_home.h
          screen_io.c
          screen_io.h
          screen_settings.c
          screen_settings.h
  app/
      app_state.c
      app_state.h

third_party/
    lvgl/     (clone LVGL here)

## Build

Place LVGL in:

third_party/lvgl

Example:

git clone https://github.com/lvgl/lvgl third_party/lvgl

Then build:

make

Run:

./lvgl_app

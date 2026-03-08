
# LuckFox LVGL HMI Starter

Minimal but scalable project template for building a GUI on LuckFox boards using LVGL and the Linux framebuffer.

## Structure

luckfox_lvgl_repo
│
├── README.md
├── Makefile
│
├── src
│   ├── main.c
│   │
│   ├── platform        ← hardware drivers
│   │   ├── fbdev.c
│   │   └── fbdev.h
│   │
│   ├── gui             ← LVGL GUI layer
│   │   ├── screen_manager.c
│   │   ├── screen_manager.h
│   │   └── screens
│   │        ├── screen_home.c
│   │        ├── screen_home.h
│   │        ├── screen_io.c
│   │        ├── screen_io.h
│   │        ├── screen_settings.c
│   │        └── screen_settings.h
│   │
│   └── app             ← application logic
│        ├── app_state.c
│        └── app_state.h
│
└── third_party
    └── lvgl            

## Build

Place LVGL in:

third_party/lvgl

Example:

git clone --branch release/v8.3 https://github.com/lvgl/lvgl.git third_party/lvgl
Then build:

make

Run:

./lvgl_app

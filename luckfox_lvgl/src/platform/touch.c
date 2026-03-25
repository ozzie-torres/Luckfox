#include "touch.h"
#include "lvgl/lvgl.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <linux/input.h>

static int touch_fd = -1;
static int touch_x = 0;
static int touch_y = 0;
static int touch_pressed = 0;

static void touch_read_cb(lv_indev_drv_t *drv, lv_indev_data_t *data)
{
    struct input_event ev;
    ssize_t n;

    (void)drv;

    while ((n = read(touch_fd, &ev, sizeof(ev))) > 0) {
        if (ev.type == EV_ABS) {
            if (ev.code == ABS_X) touch_x = ev.value;
            if (ev.code == ABS_Y) touch_y = ev.value;
        } else if (ev.type == EV_KEY && ev.code == BTN_TOUCH) {
            touch_pressed = ev.value ? 1 : 0;
        }
    }

    data->point.x = touch_x;
    data->point.y = touch_y;
    data->state = touch_pressed ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}

void touch_init(void)
{
    static lv_indev_drv_t indev_drv;

    touch_fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    if (touch_fd < 0) {
        perror("open /dev/input/event0");
        return;
    }

    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = touch_read_cb;
    lv_indev_drv_register(&indev_drv);

    printf("Touch initialized: /dev/input/event0\n");
}

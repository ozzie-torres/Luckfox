
#include "platform/fbdev.h"
#include "gui/screen_manager.h"
#include "app/app_state.h"
#include "lvgl/lvgl.h"

#include <unistd.h>

int main(void)
{
    lv_init();

    fbdev_init();
    screen_manager_init();

    app_state_init();

    while (1)
    {
        lv_timer_handler();
        usleep(5000);
    }

    return 0;
}

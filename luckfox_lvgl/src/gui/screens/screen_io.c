
#include "screen_io.h"
#include "lvgl/lvgl.h"

void screen_io_create(void)
{
    lv_obj_t *scr=lv_scr_act();

    lv_obj_t *title=lv_label_create(scr);
    lv_label_set_text(title,"IO Screen");
    lv_obj_align(title,LV_ALIGN_TOP_MID,0,10);
}

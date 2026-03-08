
#include "screen_settings.h"
#include "lvgl/lvgl.h"

void screen_settings_create(void)
{
    lv_obj_t *scr=lv_scr_act();

    lv_obj_t *title=lv_label_create(scr);
    lv_label_set_text(title,"Settings");
    lv_obj_align(title,LV_ALIGN_TOP_MID,0,10);
}

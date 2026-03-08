
#include "screen_home.h"
#include "lvgl/lvgl.h"

void screen_home_create(void)
{
    lv_obj_t *scr=lv_scr_act();

    lv_obj_t *label=lv_label_create(scr);
    lv_label_set_text(label,"LuckFox HMI");
    lv_obj_align(label,LV_ALIGN_TOP_MID,0,10);

    lv_obj_t *btn=lv_btn_create(scr);
    lv_obj_set_size(btn,120,50);
    lv_obj_align(btn,LV_ALIGN_CENTER,0,0);

    lv_obj_t *lbl=lv_label_create(btn);
    lv_label_set_text(lbl,"Start");
    lv_obj_center(lbl);
}


#include "app_state.h"

app_state_t g_app;

void app_state_init(void)
{
    g_app.system_running=0;
    g_app.io_value=0;
}

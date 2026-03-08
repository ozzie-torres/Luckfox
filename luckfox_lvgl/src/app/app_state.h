
#ifndef APP_STATE_H
#define APP_STATE_H

typedef struct
{
    int system_running;
    int io_value;
}app_state_t;

extern app_state_t g_app;

void app_state_init(void);

#endif

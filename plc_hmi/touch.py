"""Low-level touchscreen input reader.

This module reads raw Linux input events through ``evdev``, applies calibration
and axis inversion, and returns screen-space touch coordinates.
"""

from evdev import InputDevice, ecodes

class TouchReader:
    def __init__(self, device_path, touch_cfg, screen_w, screen_h):
        self.dev = InputDevice(device_path)
        self.min_x = touch_cfg["min_x"]
        self.max_x = touch_cfg["max_x"]
        self.min_y = touch_cfg["min_y"]
        self.max_y = touch_cfg["max_y"]
        self.invert_x = touch_cfg.get("invert_x", False)
        self.invert_y = touch_cfg.get("invert_y", False)
        self.screen_w = screen_w
        self.screen_h = screen_h

        self.raw_x = None
        self.raw_y = None

    def _scale(self, value, vmin, vmax, out_max):
        value = max(vmin, min(vmax, value))
        return int((value - vmin) * out_max / (vmax - vmin))

    def read_touch(self):
        for event in self.dev.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    self.raw_x = event.value
                elif event.code == ecodes.ABS_Y:
                    self.raw_y = event.value

            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                if event.value == 0 and self.raw_x is not None and self.raw_y is not None:
                    x = self._scale(self.raw_x, self.min_x, self.max_x, self.screen_w - 1)
                    y = self._scale(self.raw_y, self.min_y, self.max_y, self.screen_h - 1)

                    if self.invert_x:
                        x = (self.screen_w - 1) - x
                    if self.invert_y:
                        y = (self.screen_h - 1) - y

                    return x, y

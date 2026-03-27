"""Touch calibration helper for the Luckfox Pico HMI example."""

import json
import os
import time
from pathlib import Path

from evdev import InputDevice, ecodes


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TOUCH_DEVICE = os.environ.get("TOUCH_DEVICE", "/dev/input/event0")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class TouchCalibrator:
    def __init__(self, device_path, touch_cfg, screen_w, screen_h):
        self.device = InputDevice(device_path)
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
        self.pending_release = False
        self.last_emit_time = 0.0

    def _scale(self, value, vmin, vmax, out_max):
        value = max(vmin, min(vmax, value))
        return int((value - vmin) * out_max / (vmax - vmin))

    def _build_point(self):
        x = self._scale(self.raw_x, self.min_x, self.max_x, self.screen_w - 1)
        y = self._scale(self.raw_y, self.min_y, self.max_y, self.screen_h - 1)

        if self.invert_x:
            x = (self.screen_w - 1) - x
        if self.invert_y:
            y = (self.screen_h - 1) - y

        return x, y

    def read_touch(self):
        for event in self.device.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                    self.raw_x = event.value
                elif event.code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                    self.raw_y = event.value
                elif event.code == ecodes.ABS_PRESSURE and event.value == 0:
                    self.pending_release = True
                elif event.code == ecodes.ABS_MT_TRACKING_ID and event.value == -1:
                    self.pending_release = True

            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                if event.value == 0:
                    self.pending_release = True

            elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                if self.pending_release and self.raw_x is not None and self.raw_y is not None:
                    now = time.monotonic()
                    if now - self.last_emit_time < 0.12:
                        self.pending_release = False
                        continue

                    self.last_emit_time = now
                    point = self._build_point()
                    sample = {
                        "raw_x": self.raw_x,
                        "raw_y": self.raw_y,
                        "scaled_x": point[0],
                        "scaled_y": point[1],
                    }
                    self.raw_x = None
                    self.raw_y = None
                    self.pending_release = False
                    return sample


def main():
    cfg = load_config()
    width = cfg["screen"]["width"]
    height = cfg["screen"]["height"]
    calibrator = TouchCalibrator(TOUCH_DEVICE, cfg["touch"], width, height)

    print("Touch calibration helper")
    print(f"Device: {TOUCH_DEVICE}")
    print("Touch each corner and the center.")
    print("Use the raw values to update min_x, max_x, min_y, max_y in config.json.")
    print("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            sample = calibrator.read_touch()
            print(
                "raw=({raw_x}, {raw_y}) scaled=({scaled_x}, {scaled_y})".format(
                    **sample
                ),
                flush=True,
            )
    except KeyboardInterrupt:
        print("\nCalibration stopped")


if __name__ == "__main__":
    main()

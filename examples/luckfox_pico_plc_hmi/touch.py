"""Low-level touchscreen input reader.

This module reads raw Linux input events through ``evdev``, applies calibration
and axis inversion, and returns screen-space touch coordinates.
"""

import os
import select
import statistics
import time

from evdev import InputDevice, ecodes


class TouchReader:
    def __init__(self, device_path, touch_cfg, screen_w, screen_h):
        self.device_path = device_path
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
        self.touch_active = False
        self.pending_release = False
        self.last_emit_time = 0.0
        self.last_emit_point = None
        self.touch_samples = []
        self.min_emit_interval = touch_cfg.get("min_emit_interval_ms", 180) / 1000.0
        self.duplicate_radius = touch_cfg.get("duplicate_radius", 22)
        self.max_samples = touch_cfg.get("max_samples", 32)
        self.debug = os.environ.get("TOUCH_DEBUG", "").lower() in ("1", "true", "yes")

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

    def reopen(self):
        try:
            self.dev.close()
        except OSError:
            pass

        time.sleep(0.1)
        self.dev = InputDevice(self.device_path)
        self.raw_x = None
        self.raw_y = None
        self.touch_active = False
        self.pending_release = False
        self.touch_samples = []

    def read_touch(self):
        while True:
            ready, _, _ = select.select([self.dev.fd], [], [], 0.5)
            if not ready:
                continue

            try:
                for event in self.dev.read():
                    if self.debug:
                        print(
                            f"RAW type={event.type} code={event.code} value={event.value}",
                            flush=True,
                        )

                    if event.type == ecodes.EV_ABS:
                        if event.code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                            self.raw_x = event.value
                        elif event.code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                            self.raw_y = event.value
                        elif event.code == ecodes.ABS_PRESSURE and event.value == 0:
                            self.pending_release = True
                            self.touch_active = False
                        elif event.code == ecodes.ABS_MT_TRACKING_ID and event.value == -1:
                            self.pending_release = True
                            self.touch_active = False

                    elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                        if event.value == 1:
                            self.touch_active = True
                            self.pending_release = False
                            self.touch_samples = []
                        elif event.value == 0:
                            self.pending_release = True
                            self.touch_active = False

                    elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_DROPPED:
                        self.raw_x = None
                        self.raw_y = None
                        self.touch_active = False
                        self.pending_release = False
                        self.touch_samples = []

                    elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                        if self.touch_active and self.raw_x is not None and self.raw_y is not None:
                            self.touch_samples.append((self.raw_x, self.raw_y))
                            if len(self.touch_samples) > self.max_samples:
                                self.touch_samples = self.touch_samples[-self.max_samples:]

                        if self.pending_release:
                            point = self._finalize_touch()
                            if point is not None:
                                return point
            except BlockingIOError:
                continue

    def _finalize_touch(self):
        now = time.monotonic()
        if now - self.last_emit_time < self.min_emit_interval:
            self._reset_touch_state()
            return None

        if self.touch_samples:
            raw_x = int(statistics.median(sample[0] for sample in self.touch_samples))
            raw_y = int(statistics.median(sample[1] for sample in self.touch_samples))
        elif self.raw_x is not None and self.raw_y is not None:
            raw_x = self.raw_x
            raw_y = self.raw_y
        else:
            self._reset_touch_state()
            return None

        self.raw_x = raw_x
        self.raw_y = raw_y
        point = self._build_point()

        if self.last_emit_point is not None:
            dx = abs(point[0] - self.last_emit_point[0])
            dy = abs(point[1] - self.last_emit_point[1])
            if dx <= self.duplicate_radius and dy <= self.duplicate_radius:
                self._reset_touch_state()
                return None

        self.last_emit_time = now
        self.last_emit_point = point
        self._reset_touch_state()
        return point

    def _reset_touch_state(self):
        self.raw_x = None
        self.raw_y = None
        self.touch_active = False
        self.pending_release = False
        self.touch_samples = []

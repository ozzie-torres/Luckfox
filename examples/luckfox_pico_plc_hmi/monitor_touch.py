"""Standalone touch monitor for diagnosing the Luckfox touch device."""

import os
import select
import time

from evdev import InputDevice, ecodes


TOUCH_DEVICE = os.environ.get("TOUCH_DEVICE", "/dev/input/event0")


class TouchMonitor:
    def __init__(self, device_path):
        self.device_path = device_path
        self.dev = InputDevice(device_path)
        self.raw_x = None
        self.raw_y = None
        self.last_event_time = time.monotonic()

    def reopen(self):
        try:
            self.dev.close()
        except OSError:
            pass

        time.sleep(0.1)
        self.dev = InputDevice(self.device_path)
        self.raw_x = None
        self.raw_y = None
        self.last_event_time = time.monotonic()
        print("Reopened touch device", flush=True)

    def run(self):
        print(f"Monitoring: {self.device_path}", flush=True)
        print("Touch the screen repeatedly. Press Ctrl+C to stop.", flush=True)

        while True:
            ready, _, _ = select.select([self.dev.fd], [], [], 1.0)
            now = time.monotonic()

            if not ready:
                idle = now - self.last_event_time
                print(f"idle for {idle:.1f}s", flush=True)
                continue

            try:
                for event in self.dev.read():
                    self.last_event_time = time.monotonic()
                    self._handle_event(event)
            except BlockingIOError:
                continue
            except OSError as exc:
                print(f"Touch device error: {exc}", flush=True)
                self.reopen()

    def _handle_event(self, event):
        if event.type == ecodes.EV_ABS:
            if event.code in (ecodes.ABS_X, ecodes.ABS_MT_POSITION_X):
                self.raw_x = event.value
            elif event.code in (ecodes.ABS_Y, ecodes.ABS_MT_POSITION_Y):
                self.raw_y = event.value

        if event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
            state = "DOWN" if event.value else "UP"
            print(
                f"BTN_TOUCH {state} raw=({self.raw_x}, {self.raw_y})",
                flush=True,
            )
            return

        if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_DROPPED:
            print("SYN_DROPPED", flush=True)
            return

        if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            if self.raw_x is not None and self.raw_y is not None:
                print(f"SYN_REPORT raw=({self.raw_x}, {self.raw_y})", flush=True)


def main():
    monitor = TouchMonitor(TOUCH_DEVICE)
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nTouch monitor stopped", flush=True)


if __name__ == "__main__":
    main()

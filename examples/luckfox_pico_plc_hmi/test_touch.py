"""Touch-only test for the Luckfox Pico HMI example.

Uses the same TouchReader as main.py but does not render anything.
"""

import json
import os
import time
from pathlib import Path

from touch import TouchReader


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TOUCH_DEVICE = os.environ.get("TOUCH_DEVICE", "/dev/input/event0")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_config()
    width = cfg["screen"]["width"]
    height = cfg["screen"]["height"]

    touch = TouchReader(
        TOUCH_DEVICE,
        cfg["touch"],
        width,
        height,
    )

    count = 0
    print(f"Touch test running on {TOUCH_DEVICE}. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            point = touch.read_touch()
            if point:
                count += 1
                x, y = point
                print(f"touch #{count}: ({x}, {y})", flush=True)
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("Stopping touch test", flush=True)


if __name__ == "__main__":
    main()

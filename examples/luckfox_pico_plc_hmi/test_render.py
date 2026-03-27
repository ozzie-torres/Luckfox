"""Simple framebuffer render stress test for the Luckfox Pico HMI example."""

import json
import time
from pathlib import Path

from gui import GUIRenderer
from hardware import HardwareDriver


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_config()
    width = cfg["screen"]["width"]
    height = cfg["screen"]["height"]

    hardware = HardwareDriver(cfg["inputs"], cfg["outputs"])
    gui = GUIRenderer(
        width,
        height,
        cfg["screens"],
        cfg["buttons"],
        hardware,
        display_cfg=cfg.get("display", {}),
        debug_cfg=cfg.get("debug", {}),
        initial_screen=cfg.get("initial_screen"),
    )

    sequence = ["outputs.out1", "outputs.out2", "outputs.out3", "outputs.out4"]
    index = 0
    last_flip = time.monotonic()

    print("Render test running. Press Ctrl+C to stop.")

    try:
        gui.request_redraw()
        while True:
            now = time.monotonic()
            if now - last_flip >= 0.5:
                for ref in sequence:
                    hardware.set_tag(ref, False)

                active_ref = sequence[index % len(sequence)]
                hardware.set_tag(active_ref, True)
                print(f"Active -> {active_ref}", flush=True)

                index += 1
                last_flip = now
                gui.request_redraw()

            gui.draw()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Stopping render test")
    finally:
        gui.close()


if __name__ == "__main__":
    main()

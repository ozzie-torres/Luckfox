"""Generic JSON-driven HMI engine entry point."""

import json
import multiprocessing
import os
import queue
import time
from pathlib import Path

from gui import GUIRenderer
from hardware import HardwareDriver
from rules import RuleEngine
from touch import TouchReader


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
TOUCH_DEVICE = os.environ.get("TOUCH_DEVICE", "/dev/input/event0")


def touch_worker_fn(device_path, touch_cfg, width, height, event_queue):
    touch = TouchReader(device_path, touch_cfg, width, height)
    while True:
        try:
            point = touch.read_touch()
            if point:
                event_queue.put(point)
        except OSError as exc:
            print(f"Touch reader error: {exc}. Reopening touch device.")
            touch.reopen()
        except Exception as exc:
            print(f"Unexpected touch reader error: {exc}. Reopening touch device.")
            touch.reopen()


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_effects(gui, effects):
    changed = False
    for effect in effects:
        if effect.get("type") == "navigate":
            gui.set_screen(effect["screen"])
            changed = True
    return changed


def main():
    cfg = load_config()

    width = cfg["screen"]["width"]
    height = cfg["screen"]["height"]
    render_idle_ms = cfg.get("display", {}).get("render_after_touch_idle_ms", 180)
    render_idle_s = render_idle_ms / 1000.0
    touch_watchdog_enabled = cfg.get("touch", {}).get("watchdog_enabled", False)
    touch_watchdog_ms = cfg.get("touch", {}).get("watchdog_restart_ms", 2500)
    touch_watchdog_s = touch_watchdog_ms / 1000.0

    mp_ctx = multiprocessing.get_context("spawn")
    event_queue = mp_ctx.Queue()

    def start_touch_process():
        process = mp_ctx.Process(
            target=touch_worker_fn,
            args=(TOUCH_DEVICE, cfg["touch"], width, height, event_queue),
            daemon=True,
        )
        process.start()
        return process

    touch_process = start_touch_process()

    hardware = HardwareDriver(cfg["inputs"], cfg["outputs"])
    rules = RuleEngine(hardware, cfg["rules"])
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
    print(f"Renderer enabled: {gui.render_enabled}")

    try:
        gui.request_redraw(full=True)
        pending_render = True
        last_touch_time = 0.0
        touch_count = 0
        last_watchdog_restart = 0.0
        while True:
            state_changed = False

            if not touch_process.is_alive():
                print("Touch worker stopped unexpectedly. Restarting.")
                touch_process = start_touch_process()
                last_watchdog_restart = time.monotonic()

            while True:
                try:
                    x, y = event_queue.get_nowait()
                except queue.Empty:
                    break

                last_touch_time = time.monotonic()
                touch_count += 1
                touch_event = gui.handle_touch(x, y)
                if not touch_event:
                    print(f"Touch -> no button hit at ({x}, {y})")
                    continue

                print(f"Touch -> {touch_event}")
                effects = rules.run_event(touch_event)
                if effects:
                    state_changed = apply_effects(gui, effects) or state_changed
                else:
                    state_changed = True

            if state_changed:
                gui.request_redraw()
                pending_render = True

            now = time.monotonic()
            if (
                touch_watchdog_enabled
                and touch_count > 0
                and touch_process.is_alive()
                and now - last_touch_time >= touch_watchdog_s
                and now - last_watchdog_restart >= touch_watchdog_s
            ):
                print("Touch watchdog: no events received, restarting touch worker.")
                touch_process.terminate()
                touch_process.join(timeout=1.0)
                touch_process = start_touch_process()
                last_watchdog_restart = now

            if pending_render and (now - last_touch_time >= render_idle_s):
                gui.draw()
                pending_render = False

            if not state_changed and event_queue.empty():
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("Stopping HMI")
    finally:
        touch_process.terminate()
        touch_process.join(timeout=1.0)
        gui.close()


if __name__ == "__main__":
    main()

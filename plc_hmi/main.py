"""Application entry point for the PLC HMI demo.

This module wires the whole system together:
- loads screen, touch, and button settings from ``config.json``
- creates the hardware state model, rule engine, GUI, and touch reader
- runs a background thread that captures touch events
- processes touches in the main pygame loop and dispatches actions
"""

import json
import threading
import queue
import pygame

from hardware import Hardware
from rules import RuleEngine
from touch import TouchReader
from gui import GUI

TOUCH_DEVICE = "/dev/input/event0"

def touch_thread_fn(touch, q):
    while True:
        point = touch.read_touch()
        if point:
            q.put(point)

def main():
    with open("config.json", "r") as f:
        cfg = json.load(f)

    width = cfg["screen"]["width"]
    height = cfg["screen"]["height"]

    hardware = Hardware()
    rules = RuleEngine(hardware)
    gui = GUI(width, height, cfg["buttons"], hardware)

    touch = TouchReader(
        TOUCH_DEVICE,
        cfg["touch"],
        width,
        height
    )

    q = queue.Queue()
    t = threading.Thread(target=touch_thread_fn, args=(touch, q), daemon=True)
    t.start()

    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        while not q.empty():
            x, y = q.get()
            print(f"Touch: {x}, {y}")
            action = gui.handle_touch(x, y)
            if action:
                rules.run_action(action)

        gui.draw()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main()

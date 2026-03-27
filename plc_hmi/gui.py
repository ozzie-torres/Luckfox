"""Pygame-based user interface for the PLC HMI.

This module is responsible for drawing the on-screen buttons and translating
touch coordinates into configured button actions.
"""

import pygame

class GUI:
    def __init__(self, width, height, buttons, hardware):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        self.font = pygame.font.Font(None, 32)
        self.buttons = buttons
        self.hardware = hardware
        self.width = width
        self.height = height

    def draw(self):
        self.screen.fill((30, 30, 30))

        for b in self.buttons:
            state = self.hardware.get_output(b["id"])
            color = (0, 180, 0) if state else (100, 100, 100)
            rect = pygame.Rect(b["x"], b["y"], b["w"], b["h"])
            pygame.draw.rect(self.screen, color, rect, border_radius=10)

            label = self.font.render(b["label"], True, (255, 255, 255))
            label_rect = label.get_rect(center=rect.center)
            self.screen.blit(label, label_rect)

        pygame.display.flip()

    def handle_touch(self, x, y):
        for b in self.buttons:
            if (b["x"] <= x <= b["x"] + b["w"] and
                b["y"] <= y <= b["y"] + b["h"]):
                return b["action"]
        return None

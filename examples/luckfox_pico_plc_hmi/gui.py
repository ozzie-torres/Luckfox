"""Generic framebuffer GUI renderer driven by JSON screens and buttons."""

import mmap
import os


FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


FONT_5X7 = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00001", "00001", "00001", "00001", "10001", "10001", "01110"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "10001", "11001", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


class GUIRenderer:
    def __init__(
        self,
        width,
        height,
        screens,
        buttons,
        hardware,
        display_cfg=None,
        debug_cfg=None,
        initial_screen=None,
    ):
        self.display_cfg = display_cfg or {}
        self.debug_cfg = debug_cfg or {}
        self.hardware = hardware
        self.width = width
        self.height = height
        self.screens = {screen["id"]: screen for screen in screens}
        self.buttons = {button["id"]: button for button in buttons}
        self.current_screen = initial_screen or screens[0]["id"]
        self.fb_path = os.environ.get(
            "FRAMEBUFFER",
            self.display_cfg.get("framebuffer", "/dev/fb0"),
        )
        self.render_enabled = os.environ.get("DISABLE_RENDER", "").lower() not in (
            "1",
            "true",
            "yes",
        )
        self.line_length = width * 2
        self._fb_fd = None
        self._fb_map = None
        self._needs_redraw = True
        self._full_redraw_needed = True
        self._last_touch = None
        if self.render_enabled:
            self._open_framebuffer()

    def set_screen(self, screen_id):
        if screen_id in self.screens:
            self.current_screen = screen_id
            self.request_redraw(full=True)
            print(f"Screen -> {screen_id}")

    def draw(self):
        if not self._needs_redraw:
            return
        if not self.render_enabled:
            self._needs_redraw = False
            return

        screen_cfg = self.screens[self.current_screen]
        if self._full_redraw_needed:
            background = tuple(screen_cfg.get("background", [30, 30, 30]))
            self._fill_rect(0, 0, self.width, self.height, background)

        for button in self._buttons_for_current_screen():
            color = self._button_color(button)
            self._fill_rect(button["x"], button["y"], button["w"], button["h"], color)
            if self.debug_cfg.get("show_button_bounds", False):
                self._stroke_rect(
                    button["x"],
                    button["y"],
                    button["w"],
                    button["h"],
                    tuple(self.debug_cfg.get("button_bounds_color", [255, 255, 0])),
                    2,
                )

            text_color = tuple(button.get("text_color", [255, 255, 255]))
            self._draw_label_centered(
                button["label"],
                button["x"],
                button["y"],
                button["w"],
                button["h"],
                text_color,
            )

        if self.debug_cfg.get("show_touch_marker", True):
            self._draw_touch_marker()

        self._fb_map.flush()
        self._needs_redraw = False
        self._full_redraw_needed = False

    def handle_touch(self, x, y):
        hit_button = None
        for button in self._buttons_for_current_screen():
            if (
                button["x"] <= x <= button["x"] + button["w"]
                and button["y"] <= y <= button["y"] + button["h"]
            ):
                hit_button = button["id"]
                event = {
                    "type": "button_press",
                    "button": button["id"],
                    "screen": self.current_screen,
                    "x": x,
                    "y": y,
                }
                self.set_touch_feedback(x, y, hit_button)
                return event

        self.set_touch_feedback(x, y, hit_button)
        return None

    def request_redraw(self, full=False):
        self._needs_redraw = True
        if full:
            self._full_redraw_needed = True

    def set_touch_feedback(self, x, y, hit_button):
        self._last_touch = {
            "x": x,
            "y": y,
            "button": hit_button,
        }
        if self.debug_cfg.get("show_touch_marker", False) or self.debug_cfg.get("show_touch_text", False):
            self.request_redraw(full=True)

    def close(self):
        if not self.render_enabled:
            return
        if self._fb_map is not None:
            self._fb_map.flush()
            self._fb_map.close()
            self._fb_map = None
        if self._fb_fd is not None:
            os.close(self._fb_fd)
            self._fb_fd = None

    def _buttons_for_current_screen(self):
        screen_cfg = self.screens[self.current_screen]
        return [self.buttons[button_id] for button_id in screen_cfg.get("buttons", [])]

    def _button_color(self, button):
        indicator = button.get("indicator")
        if not indicator:
            return tuple(button.get("color", [100, 100, 100]))

        state = bool(self.hardware.get_tag(indicator["state_ref"]))
        if state:
            return tuple(indicator.get("true_color", [0, 180, 0]))
        return tuple(indicator.get("false_color", [100, 100, 100]))

    def _open_framebuffer(self):
        self._fb_fd = os.open(self.fb_path, os.O_RDWR)
        framebuffer_size = self._read_line_length() * self.height
        self._fb_map = mmap.mmap(
            self._fb_fd,
            framebuffer_size,
            mmap.MAP_SHARED,
            mmap.PROT_WRITE | mmap.PROT_READ,
        )

    def _read_line_length(self):
        try:
            import array
            import fcntl

            fix_info = array.array("B", [0] * 80)
            fcntl.ioctl(self._fb_fd, FBIOGET_FSCREENINFO, fix_info, True)
            line_length = int.from_bytes(fix_info[48:52], byteorder="little")
            if line_length > 0:
                self.line_length = line_length
        except OSError:
            self.line_length = self.width * 2
        return self.line_length

    def _fill_rect(self, x, y, w, h, color):
        start_x = max(0, x)
        start_y = max(0, y)
        end_x = min(self.width, x + w)
        end_y = min(self.height, y + h)
        if start_x >= end_x or start_y >= end_y:
            return

        pixel = self._rgb888_to_rgb565(color).to_bytes(2, byteorder="little")
        row_bytes = pixel * (end_x - start_x)

        for row in range(start_y, end_y):
            row_start = row * self.line_length
            offset = row_start + (start_x * 2)
            self._fb_map[offset:offset + len(row_bytes)] = row_bytes

    def _stroke_rect(self, x, y, w, h, color, thickness=1):
        self._fill_rect(x, y, w, thickness, color)
        self._fill_rect(x, y + h - thickness, w, thickness, color)
        self._fill_rect(x, y, thickness, h, color)
        self._fill_rect(x + w - thickness, y, thickness, h, color)

    def _draw_label_centered(self, text, x, y, w, h, color):
        scale = 3
        text = text.upper()
        text_width = self._measure_text_width(text, scale)
        text_height = 7 * scale
        start_x = x + max(0, (w - text_width) // 2)
        start_y = y + max(0, (h - text_height) // 2)
        cursor_x = start_x

        for char in text:
            self._draw_char(cursor_x, start_y, char, color, scale)
            cursor_x += (5 * scale) + scale

    def _measure_text_width(self, text, scale):
        if not text:
            return 0
        return (len(text) * (5 * scale)) + ((len(text) - 1) * scale)

    def _draw_char(self, x, y, char, color, scale):
        pattern = FONT_5X7.get(char, FONT_5X7["?"])
        for row_index, row in enumerate(pattern):
            for col_index, pixel in enumerate(row):
                if pixel == "1":
                    self._fill_rect(
                        x + (col_index * scale),
                        y + (row_index * scale),
                        scale,
                        scale,
                        color,
                    )

    def _draw_touch_marker(self):
        if not self._last_touch:
            return

        x = self._last_touch["x"]
        y = self._last_touch["y"]
        hit_button = self._last_touch["button"]
        cross_color = (255, 64, 64) if hit_button is None else (64, 200, 255)

        self._fill_rect(max(0, x - 8), max(0, y - 1), 17, 3, cross_color)
        self._fill_rect(max(0, x - 1), max(0, y - 8), 3, 17, cross_color)

        if self.debug_cfg.get("show_touch_text", True):
            label = f"{x},{y}"
            if hit_button:
                label = f"{label} {hit_button}"
            else:
                label = f"{label} no-hit"

            text_x = min(self.width - self._measure_text_width(label.upper(), 2) - 2, x + 10)
            text_y = max(2, y - 10)
            self._fill_rect(text_x - 2, text_y - 2, self._measure_text_width(label.upper(), 2) + 4, 18, (0, 0, 0))
            cursor_x = text_x
            for char in label.upper():
                self._draw_char(cursor_x, text_y, char, (255, 255, 255), 2)
                cursor_x += (5 * 2) + 2

    def _rgb888_to_rgb565(self, color):
        red, green, blue = color
        return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)

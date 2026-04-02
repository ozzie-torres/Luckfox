"""Generic hardware state driver for inputs and outputs.

The runtime engine talks only to PLC-style tags such as ``inputs.start`` or
``outputs.out1``. This module binds those tags to backend drivers so the rest
of the application can remain JSON-driven and hardware-agnostic.

Currently supported drivers:

- ``memory``: in-process state storage
- ``gpio``: Linux sysfs GPIO bindings for simple digital I/O
"""

from __future__ import annotations

import os
import queue
import select
import threading
import time
from pathlib import Path


class BaseTagBinding:
    def __init__(self, area, cfg):
        self.area = area
        self.cfg = cfg
        self.tag_id = cfg["id"]
        self.type = cfg.get("type", "bool")

    def get_value(self):
        raise NotImplementedError

    def set_value(self, value) -> None:
        raise NotImplementedError

    def supports_events(self):
        return False

    def event_setup(self) -> None:
        return None

    def wait_for_event(self, timeout_ms):
        return None

    def close(self) -> None:
        return None


class MemoryTagBinding(BaseTagBinding):
    def __init__(self, area, cfg):
        super().__init__(area, cfg)
        self.value = cfg.get("initial", False)

    def get_value(self):
        return self.value

    def set_value(self, value) -> None:
        self.value = value


class GPIOTagBinding(BaseTagBinding):
    def __init__(self, area, cfg):
        super().__init__(area, cfg)
        self.gpio_id = cfg.get("gpio")
        if self.gpio_id is None:
            raise ValueError(f"{area}.{self.tag_id} uses driver=gpio but has no gpio field")

        gpio_root = Path(cfg.get("gpio_root", os.environ.get("GPIO_SYSFS_ROOT", "/sys/class/gpio")))
        self.gpio_root = gpio_root
        self.gpio_dir = gpio_root / f"gpio{self.gpio_id}"
        self.value_path = self.gpio_dir / "value"
        self.direction_path = self.gpio_dir / "direction"
        self.active_low_path = self.gpio_dir / "active_low"
        self.edge_path = self.gpio_dir / "edge"
        self.active_low = bool(cfg.get("active_low", False))
        self.direction = cfg.get("direction", "out" if area == "outputs" else "in")
        self.edge = cfg.get("edge", "both" if area == "inputs" else "none")
        self._event_fd = None
        self._poller = None
        self._last_value = None

        self._ensure_exported()
        self._configure_direction()
        self._configure_active_low()
        self._configure_edge()

        if area == "outputs":
            self.set_value(cfg.get("initial", False))
        else:
            self._last_value = self.get_value()

    def get_value(self):
        raw = self.value_path.read_text(encoding="utf-8").strip()
        if self.type == "bool":
            return raw == "1"
        return raw

    def set_value(self, value) -> None:
        if self.area != "outputs" and self.direction == "in":
            raise PermissionError(f"Cannot write to input GPIO tag: {self.area}.{self.tag_id}")

        normalized = self._normalize_value(value)
        self.value_path.write_text(normalized, encoding="utf-8")

    def supports_events(self):
        return self.area == "inputs" and self.edge != "none"

    def event_setup(self) -> None:
        if not self.supports_events() or self._event_fd is not None:
            return

        self._event_fd = os.open(self.value_path, os.O_RDONLY | os.O_NONBLOCK)
        self._poller = select.poll()
        self._poller.register(self._event_fd, select.POLLPRI | select.POLLERR)
        self._clear_pending_edge()
        self._last_value = self.get_value()

    def wait_for_event(self, timeout_ms):
        if self._poller is None:
            return None

        events = self._poller.poll(timeout_ms)
        if not events:
            return None

        self._clear_pending_edge()
        new_value = self.get_value()
        if new_value == self._last_value:
            return None

        self._last_value = new_value
        return {
            "type": "input_change",
            "input": self.tag_id,
            "ref": f"{self.area}.{self.tag_id}",
            "value": new_value,
        }

    def close(self) -> None:
        if self._event_fd is not None:
            os.close(self._event_fd)
            self._event_fd = None
            self._poller = None

    def _normalize_value(self, value):
        if self.type == "bool":
            return "1" if bool(value) else "0"
        return str(value)

    def _ensure_exported(self):
        if self.gpio_dir.exists():
            return

        export_path = self.gpio_root / "export"
        if not export_path.exists():
            raise FileNotFoundError(
                f"GPIO sysfs export path not found for {self.area}.{self.tag_id}: {export_path}"
            )

        export_path.write_text(str(self.gpio_id), encoding="utf-8")

        for _ in range(20):
            if self.gpio_dir.exists():
                return
            time.sleep(0.02)

        raise FileNotFoundError(
            f"GPIO directory was not created for {self.area}.{self.tag_id}: {self.gpio_dir}"
        )

    def _configure_direction(self):
        if self.direction_path.exists():
            self.direction_path.write_text(self.direction, encoding="utf-8")

    def _configure_active_low(self):
        if self.active_low_path.exists():
            self.active_low_path.write_text("1" if self.active_low else "0", encoding="utf-8")

    def _configure_edge(self):
        if self.edge_path.exists():
            self.edge_path.write_text(self.edge, encoding="utf-8")

    def _clear_pending_edge(self):
        if self._event_fd is None:
            return
        os.lseek(self._event_fd, 0, os.SEEK_SET)
        try:
            os.read(self._event_fd, 8)
        except BlockingIOError:
            pass
        os.lseek(self._event_fd, 0, os.SEEK_SET)


class HardwareDriver:
    def __init__(self, inputs_cfg, outputs_cfg):
        self.inputs = self._build_binding_map("inputs", inputs_cfg)
        self.outputs = self._build_binding_map("outputs", outputs_cfg)
        self._event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._monitor_threads = []
        self._start_input_monitors()

    def _build_binding_map(self, area, items):
        bindings = {}
        for item in items:
            bindings[item["id"]] = self._create_binding(area, item)
        return bindings

    def _create_binding(self, area, cfg):
        driver = cfg.get("driver", "memory")
        if driver == "memory":
            return MemoryTagBinding(area, cfg)
        if driver == "gpio":
            return GPIOTagBinding(area, cfg)
        raise ValueError(f"Unsupported driver for {area}.{cfg['id']}: {driver}")

    def get_tag(self, ref: str):
        binding = self._get_binding(ref)
        return binding.get_value()

    def set_tag(self, ref: str, value) -> None:
        binding = self._get_binding(ref)
        binding.set_value(value)

    def toggle_tag(self, ref: str) -> None:
        value = bool(self.get_tag(ref))
        self.set_tag(ref, not value)
        print(f"{ref} -> {not value}")

    def poll_events(self):
        events = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def close(self) -> None:
        self._stop_event.set()
        for thread in self._monitor_threads:
            thread.join(timeout=0.5)

        for binding in list(self.inputs.values()) + list(self.outputs.values()):
            binding.close()

    def _start_input_monitors(self):
        for tag_id, binding in self.inputs.items():
            if not binding.supports_events():
                continue

            binding.event_setup()
            thread = threading.Thread(
                target=self._monitor_input_binding,
                args=(tag_id, binding),
                daemon=True,
            )
            thread.start()
            self._monitor_threads.append(thread)

    def _monitor_input_binding(self, tag_id, binding):
        while not self._stop_event.is_set():
            event = binding.wait_for_event(250)
            if event is None:
                continue

            print(f"Input event: {event['ref']} -> {event['value']}")
            self._event_queue.put(event)

    def _get_binding(self, ref: str):
        area, tag_id = self._split_ref(ref)
        if area == "inputs":
            if tag_id not in self.inputs:
                raise KeyError(f"Unknown input tag: {ref}")
            return self.inputs[tag_id]
        if area == "outputs":
            if tag_id not in self.outputs:
                raise KeyError(f"Unknown output tag: {ref}")
            return self.outputs[tag_id]
        raise KeyError(f"Unsupported tag area: {area}")

    def _split_ref(self, ref: str):
        parts = ref.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Tag reference must look like 'outputs.out1': {ref}")
        return parts[0], parts[1]

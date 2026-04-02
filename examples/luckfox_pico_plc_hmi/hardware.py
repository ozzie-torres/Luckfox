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
        self.active_low = bool(cfg.get("active_low", False))
        self.direction = cfg.get("direction", "out" if area == "outputs" else "in")

        self._ensure_exported()
        self._configure_direction()
        self._configure_active_low()

        if area == "outputs":
            self.set_value(cfg.get("initial", False))

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


class HardwareDriver:
    def __init__(self, inputs_cfg, outputs_cfg):
        self.inputs = self._build_binding_map("inputs", inputs_cfg)
        self.outputs = self._build_binding_map("outputs", outputs_cfg)

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

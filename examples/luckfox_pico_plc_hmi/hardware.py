"""Generic hardware state driver for inputs and outputs.

The runtime engine talks only to PLC-style tags such as ``inputs.start`` or
``outputs.out1``. This module binds those tags to backend drivers so the rest
of the application can remain JSON-driven and hardware-agnostic.

Currently supported drivers:

- ``memory``: in-process state storage
- ``gpio``: Linux sysfs GPIO bindings for simple digital I/O
- ``mcp23017``: I2C GPIO expander with interrupt-driven input support
"""

from __future__ import annotations

import os
import queue
import select
import threading
import time
from pathlib import Path


I2C_SLAVE = 0x0703

MCP23017_IODIRA = 0x00
MCP23017_IODIRB = 0x01
MCP23017_IPOLA = 0x02
MCP23017_IPOLB = 0x03
MCP23017_GPINTENA = 0x04
MCP23017_GPINTENB = 0x05
MCP23017_DEFVALA = 0x06
MCP23017_DEFVALB = 0x07
MCP23017_INTCONA = 0x08
MCP23017_INTCONB = 0x09
MCP23017_IOCONA = 0x0A
MCP23017_IOCONB = 0x0B
MCP23017_GPPUA = 0x0C
MCP23017_GPPUB = 0x0D
MCP23017_INTFA = 0x0E
MCP23017_INTFB = 0x0F
MCP23017_INTCAPA = 0x10
MCP23017_INTCAPB = 0x11
MCP23017_GPIOA = 0x12
MCP23017_GPIOB = 0x13

MCP23017_IOCON_MIRROR = 1 << 6
MCP23017_IOCON_ODR = 1 << 2


def _parse_int(value, field_name):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"Unsupported {field_name} value: {value}")


class SysfsGPIOEdgeMonitor:
    def __init__(
        self,
        gpio_id,
        edge="both",
        gpio_root=None,
        active_low=False,
        direction="in",
    ):
        self.gpio_id = _parse_int(gpio_id, "gpio")
        self.gpio_root = Path(gpio_root or os.environ.get("GPIO_SYSFS_ROOT", "/sys/class/gpio"))
        self.gpio_dir = self.gpio_root / f"gpio{self.gpio_id}"
        self.value_path = self.gpio_dir / "value"
        self.direction_path = self.gpio_dir / "direction"
        self.active_low_path = self.gpio_dir / "active_low"
        self.edge_path = self.gpio_dir / "edge"
        self.edge = edge
        self.direction = direction
        self.active_low = active_low
        self._fd = None
        self._poller = None

    def setup(self):
        self._ensure_exported()
        if self.direction_path.exists():
            self.direction_path.write_text(self.direction, encoding="utf-8")
        if self.active_low_path.exists():
            self.active_low_path.write_text("1" if self.active_low else "0", encoding="utf-8")
        if self.edge_path.exists():
            self.edge_path.write_text(self.edge, encoding="utf-8")

        self._fd = os.open(self.value_path, os.O_RDONLY | os.O_NONBLOCK)
        self._poller = select.poll()
        self._poller.register(self._fd, select.POLLPRI | select.POLLERR)
        self._clear_pending_edge()

    def wait(self, timeout_ms):
        if self._poller is None:
            return False

        events = self._poller.poll(timeout_ms)
        if not events:
            return False

        self._clear_pending_edge()
        return True

    def read_value(self):
        return self.value_path.read_text(encoding="utf-8").strip() == "1"

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
            self._poller = None

    def _ensure_exported(self):
        if self.gpio_dir.exists():
            return

        export_path = self.gpio_root / "export"
        if not export_path.exists():
            raise FileNotFoundError(f"GPIO sysfs export path not found: {export_path}")

        export_path.write_text(str(self.gpio_id), encoding="utf-8")
        for _ in range(20):
            if self.gpio_dir.exists():
                return
            time.sleep(0.02)

        raise FileNotFoundError(f"GPIO directory was not created: {self.gpio_dir}")

    def _clear_pending_edge(self):
        if self._fd is None:
            return

        os.lseek(self._fd, 0, os.SEEK_SET)
        try:
            os.read(self._fd, 8)
        except BlockingIOError:
            pass
        os.lseek(self._fd, 0, os.SEEK_SET)


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
        self.gpio_id = _parse_int(cfg.get("gpio"), "gpio")
        self.gpio_root = Path(cfg.get("gpio_root", os.environ.get("GPIO_SYSFS_ROOT", "/sys/class/gpio")))
        self.gpio_dir = self.gpio_root / f"gpio{self.gpio_id}"
        self.value_path = self.gpio_dir / "value"
        self.direction_path = self.gpio_dir / "direction"
        self.active_low_path = self.gpio_dir / "active_low"
        self.edge_path = self.gpio_dir / "edge"
        self.active_low = bool(cfg.get("active_low", False))
        self.direction = cfg.get("direction", "out" if area == "outputs" else "in")
        self.edge = cfg.get("edge", "both" if area == "inputs" else "none")
        self.debounce_s = cfg.get("debounce_ms", 0) / 1000.0
        self._event_fd = None
        self._poller = None
        self._last_value = None
        self._last_event_time = 0.0

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

        normalized = "1" if bool(value) else "0" if self.type == "bool" else str(value)
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

        now = time.monotonic()
        if self.debounce_s > 0 and now - self._last_event_time < self.debounce_s:
            self._last_value = new_value
            return None

        self._last_value = new_value
        self._last_event_time = now
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


class MCP23017Device:
    def __init__(self, bus, address, interrupt_gpio=None, interrupt_edge="falling", gpio_root=None):
        self.bus = _parse_int(bus, "bus")
        self.address = _parse_int(address, "address")
        self.interrupt_gpio = None if interrupt_gpio is None else _parse_int(interrupt_gpio, "interrupt_gpio")
        self.interrupt_edge = interrupt_edge
        self.gpio_root = gpio_root
        self._fd = None
        self._lock = threading.Lock()
        self._pin_bindings = {}
        self._interrupt_monitor = None
        self._input_event_enabled = False
        self._open()
        self._configure_iocon()

    def register_binding(self, binding):
        if binding.pin in self._pin_bindings:
            raise ValueError(
                f"MCP23017 bus {self.bus} address {hex(self.address)} pin {binding.pin} is already assigned"
            )

        self._pin_bindings[binding.pin] = binding
        self._configure_pin(binding)
        if binding.area == "inputs" and binding.interrupt_enabled:
            self._input_event_enabled = True

    def supports_events(self):
        return self._input_event_enabled and self.interrupt_gpio is not None

    def event_setup(self):
        if not self.supports_events() or self._interrupt_monitor is not None:
            return

        self._interrupt_monitor = SysfsGPIOEdgeMonitor(
            self.interrupt_gpio,
            edge=self.interrupt_edge,
            gpio_root=self.gpio_root,
            active_low=False,
            direction="in",
        )
        self._interrupt_monitor.setup()
        self._clear_pending_interrupts()

    def wait_for_events(self, timeout_ms):
        if self._interrupt_monitor is None:
            return []

        interrupt_seen = self._interrupt_monitor.wait(timeout_ms)
        if not interrupt_seen and self._interrupt_monitor.read_value():
            return []

        intf_a, intf_b, cap_a, cap_b = self._read_interrupt_snapshot()

        events = []
        for pin, binding in self._pin_bindings.items():
            if binding.area != "inputs" or not binding.interrupt_enabled:
                continue

            bank, mask = self._bank_mask(pin)
            intf = intf_a if bank == 0 else intf_b
            if not (intf & mask):
                continue

            captured = bool((cap_a if bank == 0 else cap_b) & mask)
            new_value = binding.settled_value(captured)
            event = binding.build_input_change_event(new_value)
            if event is not None:
                events.append(event)

        return events

    def _clear_pending_interrupts(self):
        self._read_interrupt_snapshot()

    def _read_interrupt_snapshot(self):
        with self._lock:
            intf_a = self._read_reg(MCP23017_INTFA)
            intf_b = self._read_reg(MCP23017_INTFB)
            cap_a = self._read_reg(MCP23017_INTCAPA)
            cap_b = self._read_reg(MCP23017_INTCAPB)
        return intf_a, intf_b, cap_a, cap_b

    def read_pin(self, pin):
        gpio_reg = MCP23017_GPIOA if pin < 8 else MCP23017_GPIOB
        mask = 1 << (pin % 8)
        with self._lock:
            value = self._read_reg(gpio_reg)
        return bool(value & mask)

    def write_pin(self, pin, value):
        gpio_reg = MCP23017_GPIOA if pin < 8 else MCP23017_GPIOB
        mask = 1 << (pin % 8)
        with self._lock:
            self._update_reg_bit(gpio_reg, mask, bool(value))

    def close(self):
        if self._interrupt_monitor is not None:
            self._interrupt_monitor.close()
            self._interrupt_monitor = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def _configure_iocon(self):
        iocon = MCP23017_IOCON_MIRROR | MCP23017_IOCON_ODR
        with self._lock:
            self._write_reg(MCP23017_IOCONA, iocon)
            self._write_reg(MCP23017_IOCONB, iocon)

    def _configure_pin(self, binding):
        bank_reg = self._bank_registers(binding.pin)
        mask = 1 << (binding.pin % 8)

        with self._lock:
            self._update_reg_bit(bank_reg["iodir"], mask, binding.area == "inputs")
            self._update_reg_bit(bank_reg["ipol"], mask, binding.invert)
            self._update_reg_bit(bank_reg["gppu"], mask, binding.pullup)
            self._update_reg_bit(bank_reg["intcon"], mask, False)
            self._update_reg_bit(bank_reg["defval"], mask, False)
            self._update_reg_bit(
                bank_reg["gpinten"],
                mask,
                binding.area == "inputs" and binding.interrupt_enabled,
            )

        if binding.area == "outputs":
            binding.set_value(binding.cfg.get("initial", False))
        else:
            binding.last_value = self.read_pin(binding.pin)

    def _open(self):
        device_path = f"/dev/i2c-{self.bus}"
        self._fd = os.open(device_path, os.O_RDWR)
        import fcntl

        fcntl.ioctl(self._fd, I2C_SLAVE, self.address)

    def _read_reg(self, reg):
        os.write(self._fd, bytes([reg]))
        return os.read(self._fd, 1)[0]

    def _write_reg(self, reg, value):
        os.write(self._fd, bytes([reg, value & 0xFF]))

    def _update_reg_bit(self, reg, mask, enabled):
        current = self._read_reg(reg)
        new_value = (current | mask) if enabled else (current & ~mask)
        if new_value != current:
            self._write_reg(reg, new_value)

    def _bank_mask(self, pin):
        return (0 if pin < 8 else 1), 1 << (pin % 8)

    def _bank_registers(self, pin):
        if pin < 8:
            return {
                "iodir": MCP23017_IODIRA,
                "ipol": MCP23017_IPOLA,
                "gpinten": MCP23017_GPINTENA,
                "defval": MCP23017_DEFVALA,
                "intcon": MCP23017_INTCONA,
                "gppu": MCP23017_GPPUA,
            }
        return {
            "iodir": MCP23017_IODIRB,
            "ipol": MCP23017_IPOLB,
            "gpinten": MCP23017_GPINTENB,
            "defval": MCP23017_DEFVALB,
            "intcon": MCP23017_INTCONB,
            "gppu": MCP23017_GPPUB,
        }


class MCPPinBinding(BaseTagBinding):
    def __init__(self, area, cfg, device):
        super().__init__(area, cfg)
        self.device = device
        self.pin = _parse_int(cfg.get("pin"), "pin")
        if not 0 <= self.pin <= 15:
            raise ValueError(f"{area}.{self.tag_id} uses invalid MCP23017 pin: {self.pin}")

        self.pullup = bool(cfg.get("pullup", False))
        self.invert = bool(cfg.get("invert", False))
        self.active_low = bool(cfg.get("active_low", False))
        self.interrupt_enabled = bool(cfg.get("interrupt", True)) if area == "inputs" else False
        self.debounce_s = cfg.get("debounce_ms", 0) / 1000.0
        self.last_value = None
        self.last_event_time = 0.0
        self.device.register_binding(self)

    def get_value(self):
        value = self.device.read_pin(self.pin)
        if self.area == "outputs" and self.active_low:
            return not value
        return value

    def set_value(self, value) -> None:
        if self.area != "outputs":
            raise PermissionError(f"Cannot write to input MCP23017 tag: {self.area}.{self.tag_id}")
        physical_value = bool(value)
        if self.active_low:
            physical_value = not physical_value
        self.device.write_pin(self.pin, physical_value)

    def settled_value(self, captured_value):
        if self.debounce_s <= 0:
            return bool(captured_value)

        time.sleep(self.debounce_s)
        return bool(self.device.read_pin(self.pin))

    def build_input_change_event(self, new_value):
        if new_value == self.last_value:
            return None

        self.last_value = new_value
        self.last_event_time = time.monotonic()
        return {
            "type": "input_change",
            "input": self.tag_id,
            "ref": f"{self.area}.{self.tag_id}",
            "value": new_value,
        }


class HardwareDriver:
    def __init__(self, inputs_cfg, outputs_cfg):
        self._event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._monitor_threads = []
        self._mcp_devices = {}
        self.inputs = self._build_binding_map("inputs", inputs_cfg)
        self.outputs = self._build_binding_map("outputs", outputs_cfg)
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
        if driver == "mcp23017":
            return self._create_mcp_binding(area, cfg)
        raise ValueError(f"Unsupported driver for {area}.{cfg['id']}: {driver}")

    def _create_mcp_binding(self, area, cfg):
        bus = _parse_int(cfg.get("bus"), "bus")
        address = _parse_int(cfg.get("address", "0x20"), "address")
        key = (bus, address)
        if key not in self._mcp_devices:
            self._mcp_devices[key] = MCP23017Device(
                bus=bus,
                address=address,
                interrupt_gpio=cfg.get("interrupt_gpio"),
                interrupt_edge=cfg.get("interrupt_edge", "falling"),
                gpio_root=cfg.get("gpio_root"),
            )
        else:
            self._validate_mcp_config(self._mcp_devices[key], area, cfg)

        return MCPPinBinding(area, cfg, self._mcp_devices[key])

    def _validate_mcp_config(self, device, area, cfg):
        interrupt_gpio = cfg.get("interrupt_gpio")
        if interrupt_gpio is not None and device.interrupt_gpio is not None:
            if _parse_int(interrupt_gpio, "interrupt_gpio") != device.interrupt_gpio:
                raise ValueError(
                    f"MCP23017 bus {device.bus} address {hex(device.address)} uses conflicting interrupt_gpio values"
                )
        interrupt_edge = cfg.get("interrupt_edge")
        if interrupt_edge is not None and interrupt_edge != device.interrupt_edge:
            raise ValueError(
                f"MCP23017 bus {device.bus} address {hex(device.address)} uses conflicting interrupt_edge values"
            )

        if area == "inputs" and device.interrupt_gpio is None and interrupt_gpio is not None:
            device.interrupt_gpio = _parse_int(interrupt_gpio, "interrupt_gpio")
            device.interrupt_edge = cfg.get("interrupt_edge", "falling")

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
        for device in self._mcp_devices.values():
            device.close()

    def _start_input_monitors(self):
        for binding in self.inputs.values():
            if not binding.supports_events():
                continue

            binding.event_setup()
            thread = threading.Thread(
                target=self._monitor_gpio_binding,
                args=(binding,),
                daemon=True,
            )
            thread.start()
            self._monitor_threads.append(thread)

        for device in self._mcp_devices.values():
            if not device.supports_events():
                continue

            device.event_setup()
            thread = threading.Thread(
                target=self._monitor_mcp_device,
                args=(device,),
                daemon=True,
            )
            thread.start()
            self._monitor_threads.append(thread)

    def _monitor_gpio_binding(self, binding):
        while not self._stop_event.is_set():
            event = binding.wait_for_event(250)
            if event is None:
                continue

            print(f"Input event: {event['ref']} -> {event['value']}")
            self._event_queue.put(event)

    def _monitor_mcp_device(self, device):
        while not self._stop_event.is_set():
            events = device.wait_for_events(250)
            if not events:
                continue

            for event in events:
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

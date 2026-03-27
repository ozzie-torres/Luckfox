"""Generic hardware state driver for inputs and outputs.

The current implementation stores PLC-style tags in memory so the rest of the
engine can be driven from JSON. It can later be replaced with real GPIO or PLC
communication code without changing the GUI or rules configuration format.
"""


class HardwareDriver:
    def __init__(self, inputs_cfg, outputs_cfg):
        self.inputs = self._build_state_map(inputs_cfg)
        self.outputs = self._build_state_map(outputs_cfg)

    def _build_state_map(self, items):
        state = {}
        for item in items:
            state[item["id"]] = item.get("initial", False)
        return state

    def get_tag(self, ref: str):
        area, tag_id = self._split_ref(ref)
        if area == "inputs":
            return self.inputs.get(tag_id)
        if area == "outputs":
            return self.outputs.get(tag_id)
        raise KeyError(f"Unsupported tag area: {area}")

    def set_tag(self, ref: str, value) -> None:
        area, tag_id = self._split_ref(ref)
        if area == "inputs":
            self.inputs[tag_id] = value
            return
        if area == "outputs":
            self.outputs[tag_id] = value
            return
        raise KeyError(f"Unsupported tag area: {area}")

    def toggle_tag(self, ref: str) -> None:
        value = bool(self.get_tag(ref))
        self.set_tag(ref, not value)
        print(f"{ref} -> {not value}")

    def _split_ref(self, ref: str):
        parts = ref.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Tag reference must look like 'outputs.out1': {ref}")
        return parts[0], parts[1]

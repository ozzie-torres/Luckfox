"""Action-to-hardware rule mapping.

This module acts like a small rule engine: it receives an action name from the
GUI layer and decides which hardware operation should run.
"""

class RuleEngine:
    def __init__(self, hardware):
        self.hardware = hardware

    def run_action(self, action: str) -> None:
        mapping = {
            "toggle_out1": lambda: self.hardware.toggle("out1"),
            "toggle_out2": lambda: self.hardware.toggle("out2"),
            "toggle_out3": lambda: self.hardware.toggle("out3"),
            "toggle_out4": lambda: self.hardware.toggle("out4"),
        }

        fn = mapping.get(action)
        if fn:
            fn()
        else:
            print(f"Unknown action: {action}")

"""Simple in-memory hardware abstraction.

This module simulates PLC outputs so the rest of the application can read and
toggle output states without talking to real hardware yet.
"""

import time

class Hardware:
    def __init__(self):
        self.outputs = {
            "out1": False,
            "out2": False,
            "out3": False,
            "out4": False,
        }

    def toggle(self, output_name: str) -> None:
        if output_name in self.outputs:
            self.outputs[output_name] = not self.outputs[output_name]
            print(f"{output_name} -> {self.outputs[output_name]}")

    def get_output(self, output_name: str) -> bool:
        return self.outputs.get(output_name, False)

"""Generic JSON-driven rule evaluator.

Rules react to events such as button presses, optionally check conditions
against inputs, outputs, or event fields, and then execute actions.
"""


class RuleEngine:
    def __init__(self, hardware, rules):
        self.hardware = hardware
        self.rules = rules

    def run_event(self, event):
        effects = []

        for rule in self.rules:
            if not self._event_matches(rule.get("when", {}), event):
                continue
            if not self._conditions_match(rule.get("if", []), event):
                continue

            print(f"Rule matched: {rule.get('id', 'unnamed_rule')}")
            effects.extend(self._run_actions(rule.get("actions", []), event))

        return effects

    def _event_matches(self, when_cfg, event):
        for key, expected in when_cfg.items():
            if event.get(key) != expected:
                return False
        return True

    def _conditions_match(self, conditions, event):
        for condition in conditions:
            left = self._resolve_value(condition.get("ref"), event)
            right = condition.get("value")
            op = condition.get("op", "==")

            if op == "==" and left != right:
                return False
            if op == "!=" and left == right:
                return False
            if op == "truthy" and not left:
                return False
            if op == "falsy" and left:
                return False

        return True

    def _run_actions(self, actions, event):
        effects = []

        for action in actions:
            action_type = action.get("type")

            if action_type == "toggle":
                self.hardware.toggle_tag(action["target"])
            elif action_type == "set":
                self.hardware.set_tag(action["target"], action["value"])
                print(f"{action['target']} -> {action['value']}")
            elif action_type == "copy":
                value = self._resolve_value(action["source"], event)
                self.hardware.set_tag(action["target"], value)
                print(f"{action['target']} -> {value}")
            elif action_type == "log":
                print(action.get("message", "Rule log action"))
            elif action_type == "navigate":
                effects.append({"type": "navigate", "screen": action["screen"]})
            else:
                print(f"Unknown action type: {action_type}")

        return effects

    def _resolve_value(self, ref, event):
        if ref is None:
            return None
        if ref.startswith("inputs.") or ref.startswith("outputs."):
            return self.hardware.get_tag(ref)
        if ref.startswith("event."):
            return event.get(ref.split(".", 1)[1])
        return ref

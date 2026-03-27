# `plc_hmi` File Guide

This folder contains a small touchscreen HMI application for a PLC-style
control panel. The project is split into focused modules so input handling,
screen rendering, business rules, and hardware state stay separate.

## Files

### `main.py`

Main application entry point.

What it does:
- Loads `config.json`.
- Reads the configured screen size.
- Creates the `Hardware`, `RuleEngine`, `GUI`, and `TouchReader` objects.
- Starts a background thread that waits for touch events.
- Runs the main `pygame` loop.
- Sends button actions from the GUI to the rule engine.

Why it exists:
- Keeps startup and runtime coordination in one place.
- Connects all other modules together.

### `gui.py`

Graphical user interface layer built with `pygame`.

What it does:
- Opens the display window.
- Draws each configured button from `config.json`.
- Colors buttons based on the current hardware output state.
- Detects which button was pressed from `(x, y)` touch coordinates.

Why it exists:
- Keeps rendering and button hit detection separate from hardware logic.

### `hardware.py`

Simple hardware abstraction layer.

What it does:
- Stores the current ON/OFF state of outputs like `out1` to `out4`.
- Toggles an output when asked.
- Lets other modules read the current output state.

Why it exists:
- Gives the app a clean place to manage output state.
- Can later be replaced with real GPIO/PLC communication code.

### `rules.py`

Small rule engine for action dispatch.

What it does:
- Receives an action string such as `toggle_out1`.
- Maps that action to the correct hardware method call.
- Prints a message for unknown actions.

Why it exists:
- Separates UI button actions from hardware implementation details.
- Makes it easier to grow from simple toggles into more advanced control rules.

### `touch.py`

Touchscreen input reader using `evdev`.

What it does:
- Opens the Linux input device (for example `/dev/input/event0`).
- Reads raw touch events from the touchscreen driver.
- Applies min/max calibration values from `config.json`.
- Converts raw touch values into screen coordinates.
- Optionally inverts the X or Y axis.

Why it exists:
- Isolates device-specific touch handling from the rest of the application.
- Makes calibration changes possible without touching the GUI code.

### `config.json`

Runtime configuration file.

What it controls:
- Screen width and height.
- Touch calibration values (`min_x`, `max_x`, `min_y`, `max_y`).
- Axis inversion flags.
- Button labels, positions, sizes, IDs, and actions.

Why it exists:
- Lets you change layout and calibration without editing Python code.

## How Data Flows Through The App

1. `main.py` loads `config.json` and creates all objects.
2. `touch.py` reads a raw touch and returns a screen coordinate.
3. `gui.py` checks whether that coordinate hits a button.
4. `gui.py` returns the button's configured action.
5. `rules.py` translates that action into a hardware call.
6. `hardware.py` updates the output state.
7. `gui.py` redraws the screen using the updated state.

## Quick Mental Model

- `config.json` = what the system should look like
- `touch.py` = where the user touched
- `gui.py` = what button that touch means
- `rules.py` = what action should happen
- `hardware.py` = what state changed
- `main.py` = how everything is coordinated

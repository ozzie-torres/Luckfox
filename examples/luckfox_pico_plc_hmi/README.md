# Generic JSON-Driven Luckfox Pico PLC HMI

This example has been refactored into a generic engine where:

- `config.json` defines the UI
- `config.json` defines the logic
- `config.json` defines the runtime behavior
- Python reads the configuration and acts as the execution engine

## Flow Diagram

```text
Touchscreen
    |
    v
touch.py
Reads raw Linux input events
    |
    v
gui.py
Converts touch coordinates into a UI event
Draws directly to /dev/fb0
Example: { type: "button_press", button: "btn_out1" }
    |
    v
rules.py
Finds matching rules in config.json
Checks conditions
Runs actions
    |
    v
hardware.py
Updates inputs.* or outputs.* tag state
    |
    v
gui.py
Reads the updated state_ref values
Redraws buttons with the new visual state
```

## Runtime Flow Description

1. `touch.py` listens to the Linux touch input device such as `/dev/input/event0`.
2. When the user touches the screen, `touch.py` scales the raw coordinates into screen coordinates.
3. `gui.py` checks whether those coordinates hit a button on the current screen.
4. If a button is hit, `gui.py` creates a generic event like `button_press`.
5. `rules.py` scans the JSON rules and looks for rules whose `when` block matches that event.
6. Each matching rule checks its `if` conditions.
7. If the conditions pass, the rule executes its `actions`.
8. Some actions update hardware tags such as `outputs.out1`; some can request screen navigation.
9. `gui.py` redraws the current screen and uses tag values to decide button colors or other states.

## Config Structure

`config.json` now contains:

- `display`: framebuffer device settings
- `screens`: what screens exist and which buttons belong to each screen
- `buttons`: button layout, labels, and visual state bindings
- `inputs`: PLC-style input tags and initial values
- `outputs`: PLC-style output tags and initial values
- `rules`: event-driven logic that reacts to UI actions

## Python Engine

The Python code is now split into generic engine parts:

- `main.py`: loads the JSON config and runs the app loop
- `gui.py`: renders screens and buttons directly to the Linux framebuffer
- `touch.py`: reads touchscreen coordinates from Linux input events
- `rules.py`: evaluates conditions and executes actions from `rules`
- `hardware.py`: binds generic `inputs.*` and `outputs.*` tags to runtime drivers

## Hardware Binding Layer

The runtime engine still talks only to generic tags such as `inputs.start` or
`outputs.out1`. The hardware-specific part now lives inside `hardware.py`.

Currently supported tag drivers:

- `memory`: keeps the tag value in Python memory
- `gpio`: binds the tag to Linux sysfs GPIO

If no driver is provided, the tag uses `memory`.

Example mixed configuration:

```json
"inputs": [
  { "id": "touch_enabled", "type": "bool", "initial": true },
  { "id": "di_start", "type": "bool", "driver": "gpio", "gpio": 34 }
],
"outputs": [
  { "id": "out1", "type": "bool", "driver": "gpio", "gpio": 23, "initial": false },
  { "id": "sim_out2", "type": "bool", "driver": "memory", "initial": false }
]
```

For `gpio` tags:

- `gpio`: Linux GPIO number used under `/sys/class/gpio`
- `direction`: optional; defaults to `in` for inputs and `out` for outputs
- `active_low`: optional boolean; defaults to `false`
- `gpio_root`: optional override for the sysfs GPIO root

This keeps the runtime small on the Luckfox:

- the GUI stays JSON-driven
- the rules stay generic
- only `hardware.py` knows how to talk to real I/O

## Display Backend Notes

This example no longer uses `pygame`. It writes pixels directly to the Linux
framebuffer, which is a better fit for the Luckfox Pico LCD you tested.

The display startup is driven by the `display` section in `config.json`:

```json
"display": {
  "backend": "framebuffer",
  "framebuffer": "/dev/fb0",
  "render_after_touch_idle_ms": 280
}
```

What these fields mean:

- `backend`: renderer type; this example uses the direct framebuffer backend
- `framebuffer`: the Linux framebuffer device to open for drawing
- `render_after_touch_idle_ms`: wait this long after the last touch before
  updating the LCD

If your display is exposed on a different framebuffer, update the JSON or run:

```bash
FRAMEBUFFER=/dev/fb1 python3 main.py
```

Current note:
- the renderer assumes a 16-bit RGB565 framebuffer, which matches the current
  `fb_ili9488` device you reported from `/proc/fb`
- button labels are rendered with a built-in 5x7 bitmap font to avoid extra
  GUI dependencies on the target
- delaying redraws after touch can help when the LCD and touchscreen appear to
  interfere with each other on the same SPI-connected setup

The touch section can also include:

```json
"watchdog_enabled": false,
"watchdog_restart_ms": 2500
```

When `watchdog_enabled` is `true`, if the combined app stops receiving touch
events for longer than this timeout, `main.py` restarts the touch worker
automatically.

## Supported Rule Concepts

### Events

Rules currently react to events like:

- `button_press`

### Conditions

Rules can check:

- `inputs.some_tag`
- `outputs.some_tag`
- `event.some_field`

Supported operators:

- `==`
- `!=`
- `truthy`
- `falsy`

### Actions

Rules currently support:

- `toggle`
- `set`
- `copy`
- `log`
- `navigate`

## Rule Action Reference

### `toggle`

Flips a boolean tag from `true` to `false` or from `false` to `true`.

Example:

```json
{ "type": "toggle", "target": "outputs.out1" }
```

What it does:
- Reads the current value of `outputs.out1`
- Inverts it
- Stores the new value back into the hardware state

Typical use:
- Start/stop buttons
- Manual ON/OFF controls

### `set`

Writes a fixed value into a tag.

Example:

```json
{ "type": "set", "target": "outputs.out1", "value": true }
```

What it does:
- Sets the target tag directly to the provided value
- Does not care what the previous value was

Typical use:
- Force a motor ON
- Force an alarm reset flag to `false`
- Write a known state during navigation or startup

### `copy`

Copies a value from one reference to another.

Example:

```json
{ "type": "copy", "source": "inputs.start_request", "target": "outputs.out1" }
```

What it does:
- Reads the value from `source`
- Writes that same value into `target`

Supported sources:
- `inputs.some_tag`
- `outputs.some_tag`
- `event.some_field`

Typical use:
- Mirror an input into an output
- Save an event field into a runtime tag

### `log`

Prints a message to the Python console.

Example:

```json
{ "type": "log", "message": "OUT1 button pressed" }
```

What it does:
- Sends a debug message to standard output
- Does not change state by itself

Typical use:
- Troubleshooting
- Verifying that a rule is matching
- Watching operator actions during testing

### `navigate`

Requests that the GUI switch to another screen.

Example:

```json
{ "type": "navigate", "screen": "settings" }
```

What it does:
- Tells the engine to change `gui.py` to the named screen
- Does not automatically change outputs unless combined with other actions

Typical use:
- Main menu to settings page
- Alarm page navigation
- Multi-screen HMIs

## How Rules Are Evaluated

Each rule has three logical parts:

- `when`: the event pattern that must match
- `if`: optional condition checks that must all pass
- `actions`: the operations to run when the rule matches

Example:

```json
{
  "id": "toggle_out1",
  "when": { "type": "button_press", "button": "btn_out1" },
  "if": [
    { "ref": "inputs.touch_enabled", "op": "==", "value": true }
  ],
  "actions": [
    { "type": "toggle", "target": "outputs.out1" },
    { "type": "log", "message": "OUT1 toggled" }
  ]
}
```

This means:

1. Wait for a `button_press` event.
2. Only continue if the pressed button is `btn_out1`.
3. Check that `inputs.touch_enabled == true`.
4. If all checks pass, toggle `outputs.out1`.
5. Print `OUT1 toggled` to the console.

## Example Rule

This rule toggles `outputs.out1` when button `btn_out1` is pressed and touch
input is enabled:

```json
{
  "id": "toggle_out1",
  "when": { "type": "button_press", "button": "btn_out1" },
  "if": [
    { "ref": "inputs.touch_enabled", "op": "==", "value": true }
  ],
  "actions": [
    { "type": "toggle", "target": "outputs.out1" }
  ]
}
```

## Run On The Device

```bash
cd /root/luckfox_pico_plc_hmi
python3 -m pip install -r requirements.txt
python3 main.py
```

If your touch device is different:

```bash
TOUCH_DEVICE=/dev/input/event1 python3 main.py
```

If you need a different framebuffer device:

```bash
FRAMEBUFFER=/dev/fb1 python3 main.py
```

## Touch Calibration

Use the calibration helper to capture raw touch values from your device:

```bash
cd /root/luckfox_pico_plc_hmi
sudo python3 calibrate_touch.py
```

If your touch device is different:

```bash
sudo TOUCH_DEVICE=/dev/input/event1 python3 calibrate_touch.py
```

Suggested process:

1. Touch the top-left corner and note the `raw=(x, y)` values.
2. Touch the top-right corner and note the `raw=(x, y)` values.
3. Touch the bottom-left corner and note the `raw=(x, y)` values.
4. Touch the bottom-right corner and note the `raw=(x, y)` values.
5. Update `config.json`:

- `min_x` = leftmost raw X
- `max_x` = rightmost raw X
- `min_y` = top raw Y
- `max_y` = bottom raw Y

If the scaled coordinates move in the wrong direction, flip:

- `invert_x`
- `invert_y`

Calibration goal:

- top-left should scale close to `(0, 0)`
- top-right should scale close to `(319, 0)`
- bottom-left should scale close to `(0, 479)`
- bottom-right should scale close to `(319, 479)`

## Touch Debugging

The example now includes extra visual debugging to help track touch problems:

- yellow outlines around button hitboxes
- a crosshair where the last touch was detected
- a small text label showing `(x, y)` and the matched button or `no-hit`

The settings live in `config.json` under `debug`:

```json
"debug": {
  "show_touch_marker": true,
  "show_touch_text": true,
  "show_button_bounds": true,
  "button_bounds_color": [255, 255, 0]
}
```

The console also now prints touches that do not hit any button:

```text
Touch -> no button hit at (154, 302)
```

This helps separate:

- touch input stopped completely
- touch still works but lands outside the button
- touch is mapped to the wrong button area

If you want to test whether framebuffer drawing is the source of touch freezes,
run the app with rendering disabled:

```bash
sudo DISABLE_RENDER=1 python3 main.py
```

In that mode the rule engine and touch handling still run, but nothing is drawn
to the LCD. If touch becomes stable in this mode, the framebuffer updates are
the likely source of the problem.

## Render Test

To test the LCD refresh path without any touch input, run:

```bash
cd /root/luckfox_pico_plc_hmi
sudo python3 test_render.py
```

What it does:

- cycles the active state across `OUT1` to `OUT4`
- redraws the screen every time the active output changes
- prints the active output to the console

This helps answer a different question from touch testing:

- if `test_render.py` runs smoothly for a long time, framebuffer refresh is
  probably fine and the instability is more likely in touch/input handling
- if `test_render.py` also stalls or the screen stops updating, the framebuffer
  render path is likely part of the problem

## Touch Test

To test only the HMI touch parser without rendering, run:

```bash
cd /root/luckfox_pico_plc_hmi
sudo python3 test_touch.py
```

What it does:

- uses the same `TouchReader` class as `main.py`
- applies the same calibration from `config.json`
- prints one calibrated touch point at a time

This is different from `monitor_touch.py`:

- `monitor_touch.py` shows the raw Linux input stream
- `test_touch.py` shows what the HMI touch parser thinks a real touch is

That helps isolate where a problem lives:

- if `monitor_touch.py` is stable but `test_touch.py` is not, the parser logic
  in `touch.py` still needs work
- if both are stable, the remaining issue is likely in how `main.py` consumes
  touch events

## Dependency Notes

The only Python package required by this example is `evdev`.

If you need to install it directly, the version confirmed to work here is:

```bash
python3 -m pip install evdev==1.6.1
```

If you run the app with `sudo`, install it for root too:

```bash
sudo python3 -m pip install evdev==1.6.1
```

## Pivot Summary

This example originally used `pygame`, but the Luckfox Pico image reported:

- `/dev/fb0` exists and maps to `fb_ili9488`
- `/dev/dri` does not exist
- SDL backends such as `fbcon` and `kmsdrm` were not available

Because of that, the renderer was changed to draw directly to `/dev/fb0`
instead of relying on SDL video drivers.

## Next Step Ideas

- replace `hardware.py` with real GPIO or PLC writes
- add multiple screens and `navigate` actions
- add timer or polling events
- add more rule operators such as `>`, `<`, `>=`, `<=`

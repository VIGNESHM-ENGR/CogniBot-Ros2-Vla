---
name: CogniBot Operator Pendant
description: The robot operator console as a handheld teach pendant — key switch, mushroom stop, a live screen that never leaves, and a control panel beside the stop.
colors:
  room: "#070808"
  housing: "#1d2022"
  housing-highlight: "#2e3336"
  housing-shadow: "#111314"
  seam: "#0a0b0c"
  key: "#33383b"
  key-highlight: "#454b4f"
  key-shadow: "#1a1d1f"
  key-dead: "#26292b"
  well: "#0a0d0e"
  screen: "#0e1214"
  screen-rule: "#1f272b"
  screen-rule-strong: "#2f3a3f"
  ink: "#ebe8e1"
  ink-secondary: "#b4bab7"
  ink-tertiary: "#87908c"
  ink-dead: "#5c6461"
  safety-yellow: "#f4c20d"
  safety-yellow-ink: "#1a1500"
  stop-red: "#d7261e"
  stop-red-light: "#ef4a3f"
  stop-red-deep: "#7d130e"
  led-on: "#5ee08f"
  led-off: "#2b3134"
  fault: "#ff6b5e"
typography:
  display:
    fontFamily: "Barlow Condensed, Barlow, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    letterSpacing: "0.06em"
  legend:
    fontFamily: "Barlow Condensed, Barlow, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.07em"
  label:
    fontFamily: "Barlow Condensed, Barlow, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "0.08em"
  body:
    fontFamily: "Barlow, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.35
    fontFeature: '"tnum"'
  data:
    fontFamily: "ui-monospace, SFMono-Regular, DejaVu Sans Mono, monospace"
    fontSize: "12px"
rounded:
  key: "7px"
  well: "12px"
  housing: "28px"
  pill: "999px"
spacing:
  gutter: "12px"
  grip: "16px"
  housing: "18px"
  key: "8px"
components:
  membrane-key:
    backgroundColor: "{colors.key}"
    textColor: "{colors.ink}"
    typography: "{typography.legend}"
    rounded: "{rounded.key}"
    padding: "8px 10px"
    height: "44px"
  membrane-key-dead:
    backgroundColor: "{colors.key-dead}"
    textColor: "{colors.ink-dead}"
  soft-key-current:
    backgroundColor: "#3d4347"
    textColor: "{colors.ink}"
  key-cap:
    backgroundColor: "{colors.key-shadow}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.label}"
    rounded: "4px"
  stop-plate:
    backgroundColor: "{colors.safety-yellow}"
    textColor: "{colors.safety-yellow-ink}"
    rounded: "12px"
  stop-mushroom:
    backgroundColor: "{colors.stop-red}"
    textColor: "{colors.ink}"
    size: "112px"
  screen-well:
    backgroundColor: "{colors.screen}"
    textColor: "{colors.ink}"
    rounded: "{rounded.well}"
  field:
    backgroundColor: "{colors.well}"
    textColor: "{colors.ink}"
    rounded: "6px"
    height: "36px"
---

# Design System: CogniBot Operator Pendant

## Overview

**Creative North Star: "The Operator's Pendant"**

The console is the handheld instrument every industrial robot operator already trusts: a matte graphite housing with a key switch and the robot's joint and GPU readouts in the left grip, a recessed screen in the middle that always shows the robot, and a red mushroom stop on a yellow plate in the right grip with the controls for the current job beneath it. Everything the robot reports lives inside the screen well; everything the operator does is a physical-looking key with a silkscreen legend and an LED. It is dense but calm: dark graphite, one safety yellow, one stop red, and flat LEDs, with no glow and no decoration that does not carry state.

The pendant is honest hardware. A key that cannot act is visibly dead, a subsystem that is not running says so in the screen, and a number only appears when a topic sent it. It reads on a screen recording from across the room: the mode, the stop state and the running program are large, labelled and never color-only.

**Key Characteristics:**

- Three-part housing: left grip (mode key, joints, GPU), centre screen well (status, viewport, program) with soft keys beneath, right grip (stop, then the control panel F2–F6 chose).
- Condensed uppercase silkscreen legends on raised membrane keys, each with a key-cap hint and an LED pip.
- Safety yellow and stop red are reserved signals, never decoration.
- Mechanical motion: short detent snaps and 2 px key depress; no fades or glow.

## Colors

A graphite instrument palette with two reserved safety signals and a flat LED green.

### Primary

- **Safety Yellow** (`safety-yellow`): the key-switch collar, the stop's backplate, the current soft key's lower edge, caution flags ("NEAR LIMIT"), focus rings, text selection. It marks what the operator must find instantly.
- **Stop Red** (`stop-red`, with `stop-red-deep` as the collar ring and `stop-red-light` for the link-lost LED): only the mushroom stop and loss of link.

### Secondary

- **LED Green** (`led-on`): a lit LED — the selected mode, an active controller, a key being pressed, a succeeded program. Off LEDs are `led-off`.
- **Fault Coral** (`fault`): fault text on the dark screen (link lost, stopped arm, at-limit joints, failed or canceled program), where Stop Red would not reach contrast.

### Neutral

- **Room Black** (`room`): the space around the housing.
- **Graphite Housing** (`housing`, lit edge `housing-highlight`, lower lip `housing-shadow`): the moulded body and its bevel.
- **Membrane Key Grey** (`key`, `key-highlight`, `key-shadow`; dead `key-dead`): every pressable key.
- **Screen Black** (`screen`, deeper `well` behind video and fields): everything the robot reports.
- **Screen Rules** (`screen-rule`, `screen-rule-strong`): hairline dividers and bar tracks inside the screen.
- **Silkscreen Ink** (`ink`, `ink-secondary`, `ink-tertiary`, `ink-dead`): values, supporting text, labels, and dead legends.

### Named Rules

**The Two Signals Rule.** Yellow means find this or be careful; red means stop. Neither ever decorates a surface that carries no safety meaning.

**The Lit LED Rule.** A state is shown by an LED and a word together; color alone never carries state, because the console must read on a recording.

## Typography

**Display / Legend Font:** Barlow Condensed (self-hosted via Fontsource, fallback Barlow, system-ui)
**Body Font:** Barlow (fallback system-ui)
**Data Font:** the platform monospace stack, only for topic names, endpoints and controller types.

**Character:** a DIN-like engineering sans pairing — condensed uppercase for anything printed on the housing, the regular width for anything the screen reports.

### Hierarchy

- **Display** (600, 28px, 0.06em, uppercase): the one heading of a not-running view.
- **Legend** (600, 14px, 0.07em, uppercase): key legends and mode names.
- **Label** (600, 11–12px, 0.08em, uppercase): group titles on the housing and field labels in the status strip and tables.
- **Body** (400/500, 13–14px, 1.35 line height, tabular numerals): values, notes, descriptions; prose capped at 62ch.
- **Data** (monospace, 12px): ROS names and types only.

### Named Rules

**The Silkscreen Rule.** Uppercase condensed type is for what is printed on the device; what the robot says is set in regular Barlow with tabular numerals.

## Layout

The housing fills the viewport inside a 12 px room gutter as a three-column grid: left grip 264 px, screen column flexible, right grip 432 px, with 18 px gaps and padding (216 / 344 px and 14 px below 1440 px wide). The screen well stacks a wrapping status strip, the viewport and the program line; the viewport is never replaced, so the operator watches the robot while operating it. The soft-key row sits on the housing below it: the viewport key F1 takes a 1.3× column because it names a source, F2–F6 share the rest, and below 1440 px the key icons drop so legends and caps keep one line. The left grip is a grid — plate and mode key at their height, joints taking what is left (scrolling inside their well if the window is short), GPU always visible at the bottom. The right grip is a grid whose first row is the stop and whose second row is the control panel; only the panel scrolls, so the stop never moves. Below 960 px tall the mode dial shrinks to 100 px. Jogging is keyboard-only (W/S, A/D, ↑/↓, Q/E, ←/→, G); the TELEOP help under the mode key names the keys. The housing keeps a 1024 × 640 px minimum; below 1024 px the page scrolls and a compact stop is pinned to the top-right corner so stop stays reachable at any width.

## Elevation & Depth

Depth is physical and structural: the housing is raised from the room, keys are raised from the housing, and wells are recessed into it. Shadows always have offset and blur; nothing glows.

### Shadow Vocabulary

- **Housing lift** (`inset 0 1px 0 #2e3336, inset 0 -3px 0 #111314, 0 18px 40px rgba(0,0,0,0.55)`): the moulded body.
- **Key raise** (`inset 0 1px 0 #454b4f, 0 2px 0 #1a1d1f, 0 3px 6px rgba(0,0,0,0.45)`): membrane keys at rest; pressed keys drop 2 px and lose the lower edge.
- **Well recess** (`inset 0 0 0 1px #0a0b0c, inset 0 3px 10px rgba(0,0,0,0.75)`): screen and mini-wells.
- **Stop mount** (`inset 0 0 0 6px #7d130e, 0 0 0 8px #151718, 0 10px 16px rgba(0,0,0,0.55)`): the mushroom's collar and black mount.

### Named Rules

**The Raised or Recessed Rule.** Controls are raised, information is recessed. A control never sits in a well; a readout never sits on a key.

## Shapes

Moulded, softly rounded forms: the housing at 28 px, wells at 12 px (mini-wells 10 px), keys at 7 px, key caps at 4 px, fields at 6 px. Circles are reserved for the mode key dial (132 px, face inset 14 px), LED pips (8 px) and the stop mushroom (112 px). No card shells: the housing and its wells are the only containers.

## Components

### Membrane key

Tactile and plain. Legend left, key-cap hint right, optional LED pip first. Hover lightens the key; active and keyboard-pressed states move it down 2 px in 80 ms; dead keys drop to `key-dead` with `ink-dead` legends and a not-allowed cursor.

### Soft keys (F1–F6)

Six keys under the screen with a 16 px line icon, legend and F-key cap. **F1 is the viewport key**: momentary, never "current", its legend is the source now on screen (Free look → Front → Wrist → Free look; V does the same). **F2–F6 choose the control panel** — Motion, Agent, VLA, RLCD, System — and the current one gets a lighter key and a 3 px safety-yellow lower edge.

### Control panel

A screen well under the stop: a title row (panel name in legend type, its F-key cap at the right, a hairline beneath) and a scrolling body. Every view renders here as a single column — two-column view layouts collapse, inner panel borders and padding drop — so one panel works at 344 or 432 px. Motion and Agent no longer carry their own camera: the viewport is the camera, and the agent's grounded detection is drawn on the front feed there.

### Mode key switch

The signature control: a 132 px safety-yellow collar around a black face with a key bar that snaps between five detents from −60° to +60° in 110 ms (`cubic-bezier(0.16, 1, 0.3, 1)`). Below it, a radio list of the five modes, each with an LED, its number key and its name; arrow keys and 1–5 turn it.

### Mushroom stop

A flat stop-red dome (112 px) with a deep-red collar on a black mount, on a safety-yellow plate, with the state word (RUN / STOPPED), the Esc hint and a Release key while latched. Pressing scales it to 94%.

### Status strip and readouts

Label/value pairs in the screen's top strip, joint rows with a 3 px limit marker on an 8 px track (yellow near a limit, fault coral at it, always with the text flag), and a filled VRAM bar.

### Fields

Deep `well` background, 1 px strong screen rule, safety-yellow border and caret on focus, tabular numerals.

### Viewport sources

The Camera view shows one source full size — Free look (default), Front RGB-D or Wrist — and the other two as clickable insets stacked at the lower right (24% wide, 4:3, 8 px radius, strong screen-rule ring). `V` cycles the main source; a small label at the lower left names it. Free look is a three.js mirror of the simulator's own MJCF on the screen-black ground with a hairline grid, robot shell in the recolored red; it renders only when state or the orbit changes, and its View key resets the camera.

### VLA view

Two `system`-style columns: the Policy stream heading, an LED status line (green + "STREAMING · <requester>" while commands flow, yellow while VLA is held without commands, dim "No policy client connected" otherwise), a joint table of target / actual / Δ in tabular degrees, and a Stream table (command rate, mode holder, reason). Idle shows the same `offline` block as the Motion view with the start command.

### Policy run

Above the stream status: an Instruction field, Start policy (LED lit and flashing while a run is active) and Stop policy (cap C) keys, and a note that reads the run's elapsed time and rate. Offline shows the `offline` block with `make vla`.

### Spawn cube

Five colour swatches as a radio group (18 px chip with an inset hairline, name below, safety-yellow ring on the checked one), x/y fields, a fixed "floor" z, and a full-width Spawn key; the pick-and-place note names the selected cube.

### Agent view

The Task section (Instruction field, Run task with a flashing LED while active, Cancel with cap C, a status note) above a Trace list of the model's steps — step number, kind or tool name (safety yellow for tool calls, fault for errors), compact `key=value` arguments and results, and the model or tool time. Grounded detections draw a safety-yellow rectangle and label on the viewport's front feed through an SVG that shares the image's contain box.

### RLCD view

Two columns, the wider one first: the decision run (a two-key Track selector — Skills / Primitives, each with an LED, the pressed one carrying the safety-yellow lower edge that marks the current soft key — a Task field, Run decisions with a flashing LED, Stop with cap C) above the decision list, with a Model table and the step trace on the right.

Each decision row shows the step number, the question id, the calibrated confidence with an LED and the word ACTED or ESCALATED, and beneath it the four highest-scoring options as name, bar and percentage. The chosen option's bar is LED green, every other option sits on a screen rule, and a row that fell under the confidence gate turns its chosen bar safety yellow and takes a 2 px yellow inset edge. This is the one place in the console where a model's uncertainty is the content, so the distribution is drawn rather than summarised: a confident wrong answer and an unsure one must not look alike.

### Offline block

Every view that depends on a service shows the same `offline` block when it is absent: a legend-style name of the missing service and the exact `make` command that starts it.

## Do's and Don'ts

### Do:

- **Do** pair every state color with an LED and a word ("NEAR LIMIT", "stopped", "active").
- **Do** keep the mushroom stop and Esc reachable in every view and at every window size.
- **Do** show subsystems that are not running as not running, naming the service and the command that starts it.
- **Do** use Barlow Condensed uppercase for housing legends and Barlow with tabular numerals for live values.

### Don't:

- **Don't** use safety yellow or stop red on anything without safety meaning.
- **Don't** add glow, fades or bouncy easing; motion is detent snaps and key presses.
- **Don't** put a label or eyebrow above a heading; the heading carries itself.
- **Don't** render placeholder numbers when a topic is silent.

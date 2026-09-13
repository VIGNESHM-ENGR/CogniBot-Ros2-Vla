---
version: 1
slug: "dashboard"
primary_target: "dashboard"
related_targets: []
---

# Surface brief: operator console (dashboard/)

## Scope
- Surface: the CogniBot operator console SPA (`dashboard/`), single screen app, laptop 1280–1920 px; works down to 1024 px.
- Mode: Operate. Build path: code-led (no image generation in this harness).
- Audience/job: the owner operating the stack (watch, drive, demo, instruct) and watchers of recordings.
- Constraints: live data only (roslibjs over rosbridge 127.0.0.1:9090, MJPEG 127.0.0.1:8080); unfinished services show an honest not-connected state; keyboard-first; persistent emergency stop.

## Chosen direction
Teach Pendant (IMPECCABLE’S PICK, chosen by the owner over the rolled Drawing Sheet). Memorable moment: turning the mode key.

## Direction contract

THESIS: The console is the operator's teach pendant, one handheld instrument with a mushroom stop, a mode key switch and jog keys around a live screen. It refuses the dockable dark panel-grid robotics dashboard.

OWN-WORLD: Matte graphite moulded housing with bevelled edges; a recessed near-black screen well holds everything the robot reports. Safety yellow only for the key-switch collar, dead-man and caution; signal red only for the mushroom stop and faults. Membrane keys are raised rectangles with condensed uppercase silkscreen legends and an LED pip plus a text state, never colour alone. Screen content uses a pendant status strip, tabular numerals and hairline gauges.

STORY: The operator sees what the robot sees and who holds the arm, jogs, moves, runs the demo and instructs the agent, and can stop from anywhere with Esc. A watcher reads mode, motion and stop from the recording without narration.

FIRST VIEWPORT: At 1440×900 the housing fills the viewport. The left grip holds the mode key dial (IDLE, TELEOP, MOTION, VLA, TWIN) over the jog key block (W/S, A/D, ↑/↓, G). The centre screen well, about 60% wide, has a status strip on top, the front camera large with the wrist camera inset, a program line with progress and cancel, and a soft-key row F1–F5 below. The right grip holds a 112 px red mushroom STOP at top right, then joint readouts with limit bars and the VRAM gauge.

FORM: Teach pendant, position 1 of the ordered grounded list, seed key 623f7fa6. Signature interaction: turning the mode key snaps through detents, lights its LED, and wakes only the keys that mode allows (jog keys stay dead outside TELEOP). Motion grammar is mechanical: 80–120 ms detent snaps, 1 px key depress with LED flash, no fades or glow.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved
- Mode switching requires `mode_manager` (P2-T04); until then the key shows the requested mode as NOT AVAILABLE and does not pretend to switch controllers.
- Teleop requires `mink_teleop` (P2-T06); jog keys render but report NOT CONNECTED.
- Agent chat (P4) and VLA panel (P5) are soft-key views with not-running states.

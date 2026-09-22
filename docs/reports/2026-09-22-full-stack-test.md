# Full-stack control-path test — 2026-09-22

A clean `make down` → `make full` start, then every way of driving the arm through the same ROS 2
actions the dashboard uses, with the scene reset between tests. **Every verdict is read from the
green cube's final pose in the simulator**, not from the action's own success flag.

Commit under test: `b3a63c8` (images rebuilt from it). Hardware: RTX 3060 Laptop, 6 GB.

## Summary

| # | Control path | Verdict | Time | What happened | Root cause | Fix |
|---|---|---|---|---|---|---|
| 1 | **VLM agent** (Qwen3-VL-4B via llama-swap) | ❌ **FAIL** (full profile) · ✅ pass on retry | 11.8 s · 27.3 s | `Error code: 502`; the arm never moved. With the `laya` container stopped, the same task **placed the cube** | **GPU out of memory**: llama-server exited while loading (~3.6 GB) on top of the simulator + Laya (2.4 GB); VRAM peaked at 5779 / 6144 MiB | [F1](#f1-laya-and-the-vlm-do-not-fit-together-on-6-gb) |
| 2 | **VLA policy** (SmolVLA `smolvla_arena_multitask`) | ⚠️ **pipeline PASS, task FAIL** | 61.7 s | 894 joint commands at a median 30 Hz, mode VLA → IDLE handled cleanly; the cube moved **0.2 cm** | The checkpoint does not solve this scene (camera viewpoint mismatch, known) **and** 17.4 s of the 60 s budget went to loading the policy onto the GPU | [F2](#f2-the-policy-cannot-solve-this-scene-and-loses-a-third-of-its-budget-to-loading) |
| 3 | **RLCD Primitives** (Laya, Track B) | ✅ **PASS** | 15.1 s | Placed at (0.290, 0.157, 0.012), inside the frame; 16 decisions | — | minor: [F4](#f4-minor-the-first-primitive-after-entering-teleop-is-lost) |
| 4 | **RLCD Skills** (Laya, Track A) | ❌ **FAIL** | 0.2 s | Escalated at the first decision: `skill confidence 0.08 below 0.35` | The model cannot choose `fetch` with an empty gripper zero-shot (measured 1/4 before today) | [F3](#f3-track-a-cannot-decide-fetch-zero-shot) |

**Passed 1 of 4 as started** (RLCD Primitives), **2 of 4 once the memory conflict is removed** (the VLM
agent passes too). The VLA pipeline works end to end but its checkpoint does not do this task.

## How the test ran

- Start: `make down`, then `make full` → nine containers up in 32 s, all ready (`vlm_agent ready`,
  `skill_executor ready`, `decision model ready in 15.3 s on cuda`, `pick_place_server ready`).
- Driver: one Python script (`rclpy`) running in the `laya` image, calling
  `/cognibot/agent/run_task`, `/cognibot/vla/execute_skill` and `/cognibot/rlcd/run_task` in turn,
  with `/cognibot/sim/reset_objects` before each test. It records the action result, every
  `AgentEvent`, the control-mode changes, the `/cognibot/joint_command` count and the cube's pose.
- Pass criterion (all tests): green cube inside the black rectangle — x 0.227–0.387, y 0.141–0.253,
  z < 0.03 — after the action ends.
- Task given to the VLM agent and both RLCD tracks: *"Pick up the green cube and place it inside the
  black rectangle."* The VLA got its checkpoint's own instruction: *"Pick and place each of the five
  cubes inside the black boundary."*, 60 s.
- GPU sampled every 2 s on the host.

### GPU during the session

| Phase | VRAM max | Temp max | Util max |
|---|---|---|---|
| Idle, all services up | 2432 MiB | 64 °C | 41 % |
| 1 VLM agent (crashed) | **5779 MiB** | 73 °C | 41 % |
| 2 VLA policy | 3525 MiB | **83 °C** | 58 % |
| 3 RLCD primitives | 4357 MiB | 74 °C | 33 % |
| 4 RLCD skills | 4389 MiB | 72 °C | 6 % |
| 1 VLM retry, `laya` stopped | 5401 MiB | 77 °C | 64 % |

Resident after the VLA test: policy server **1088 MiB** (SmolVLA stays loaded), laya **1826 MiB**.

---

## Test 1 — VLM agent

**Result:** `{'success': False, 'summary': 'Error code: 502'}` after 11.8 s; no mode change, no joint
commands, cube unmoved.

```text
# llm (llama-swap)
[WARN] <qwen3-vl-4b-gpu> proxy error: EOF
[INFO] Request 127.0.0.1 "POST /v1/chat/completions HTTP/1.1" 502 0 "OpenAI/Python 3.13.0" 6.718808578s
[WARN] <qwen3-vl-4b-gpu> upstream process exited unexpectedly
[WARN] <qwen3-vl-4b-gpu> proxy error: EOF
[INFO] Request 127.0.0.1 "POST /v1/chat/completions HTTP/1.1" 502 0 "OpenAI/Python 3.13.0" 3.679996104s
[WARN] <qwen3-vl-4b-gpu> upstream process exited unexpectedly
# vlm-agent
[vlm_agent-1] [ERROR] [1790064319.590942102] [vlm_agent]: agent task failed: Error code: 502
```

VRAM went 2432 → **5779 MiB** in the two seconds the server was loading, then dropped when it exited.

**Retry to confirm the cause:** `docker stop cognibot-laya-1` (frees Laya's 1.8 GB), same task, same
driver → **PLACED** at (0.323, 0.209, 0.012) in 27.3 s, VRAM peak 5401 MiB, four `200` completions
from llama-swap (4.8 s, 1.2 s, 1.1 s, 0.4 s).

**Root cause:** today's switch of the `laya` service to the GPU (commit `b3a63c8`) added a resident
~1.8 GB process. The full profile's steady demand is now simulator ~0.6 + Laya ~1.8 + Qwen3-VL ~3.6
+ SmolVLA ~1.1 ≈ **7.1 GB on a 6 GB card**. `docs/VRAM_BUDGET.md` planned the VLM and the policy to
take turns (the skill executor unloads the VLM first); nothing makes Laya take a turn.

## Test 2 — VLA policy

**Result:** `{'success': True, 'message': 'max_duration_s 60 reached after 62 s (894 commands)',
'actions_executed': 894, 'mean_rate_hz': 14.5}`; stream rate median **30 Hz** over 59 feedback
samples; modes `VLA by lerobot_robot_cognibot` → `IDLE by lerobot_robot_cognibot`. The cube moved
0.2 cm.

```text
# vla-client
[skill_executor]: starting robot_client: task='Pick and place each of the five cubes inside the black boundary.' checkpoint=/hf_cache/cognibot/smolvla_arena_multitask
[skill_executor]: VLM unloaded (http://127.0.0.1:8082/api/models/unload)
08:05:35 CognibotSO101 connected: 6 joints, cameras ['camera1', 'camera2']
08:05:53 Control loop thread starting
08:06:25 Client stopped
# policy-server
08:05:35 Receiving policy instructions ... Policy type: smolvla | Pretrained name or path: /hf_cache/cognibot/smolvla_arena_multitask
08:05:53 Time taken to put policy on cuda: 17.3725 seconds
```

No `StreamActions` / `observation.images` key errors — camera keys and units are right. The
traceback at the end of the client log is the expected `KeyboardInterrupt` from the executor's SIGINT
at `max_duration_s`.

**Root causes (task):**
1. The checkpoint was trained with the camera on the other side of the table; none of the community
   checkpoints completes this scene (P5-T05, README "Honest limits"). This is not new.
2. **The 60 s budget includes 17.4 s of policy loading**, and the client only started acting at
   08:05:53, so the policy streamed for ~32 s. `mean_rate_hz` 14.5 is the same effect: 894 commands
   over 62 s of wall clock, not 30 Hz of streaming.

## Test 3 — RLCD Primitives ✅

**Result:** `green cube placed on the black rectangle at (0.290, 0.157, 0.012)`, 16 decisions, 15.1 s;
modes MOTION (ready pose) → IDLE → TELEOP.

```text
[ 0.7s] target: green cube (named in the task)
[ 4.1s] green cube: on the table
[ 4.1s] stage: move above the green cube
[ 4.2s] back · go to 2 cm right          <- wrong direction
[ 4.5s] back blocked                     <- and the jog did not move the arm
[ 4.5s] right · go to 2 cm right
[ 5.0s] stage: lower onto the green cube
[ 5.1s] down · go to 6 cm down
[ 5.7s] down · go to 3 cm down
[ 6.3s] grasp (only legal move)
[ 7.3s] green cube: in the gripper
[ 7.3s] stage: lift the green cube
...     carry, lower, release (only legal move), move up, done
```

## Test 4 — RLCD Skills ❌

**Result:** `skill confidence 0.08 below 0.35`, one decision, 0.2 s. The object was bound from the task
("green cube (named in the task)"); the skill question with an empty gripper did not reach the gate.

```text
[0.0s] track skills: Pick up the green cube and place it inside the black rectangle.
[0.1s] object: green cube (named in the task)
[0.1s] escalate: skill confidence 0.08 below 0.35
[0.1s] error: skill confidence 0.08 below 0.35
```

**Root cause:** the known Track A weakness — offered `fetch / home / vla_skill / done / ask_human`
with an empty gripper, the model prefers `done` (measured 1/4 correct on 2026-09-22, four phrasings,
both checkpoints). The gate did its job: it escalated instead of reporting a false success.

---

## Fixes, in the order to do them

### F1. Laya and the VLM do not fit together on 6 GB
The blocker for the full profile. Options, cheapest first:
1. **Run Laya on the CPU in the full profile, the GPU in the `rlcd` profile.** `make full` passes
   `LAYA_DEVICE=cpu` (0 MiB; ~0.8 s per decision, which Track B tolerates — it passed on CPU before
   today). `make rlcd` keeps CUDA.
2. **Make Laya take turns like the VLM**: unload its checkpoint (`Router.unload()`) when a VLM or
   VLA goal starts and reload (~13 s) on the next RLCD goal.
3. Lower llama-swap to the hybrid profile while Laya is resident (slower agent).

Acceptance: `make full`, VLM task places the cube with Laya running; VRAM stays under ~5.6 GB.

### F2. The policy cannot solve this scene, and loses a third of its budget to loading
1. **Start the budget when the first action arrives**, not when the goal is accepted (the executor
   already watches `/cognibot/joint_command`), or pre-load the policy on the server when the VLA
   panel opens.
2. The task itself needs a checkpoint trained on this viewpoint: a fine-tune on scripted episodes
   (`record_scripted_episodes.py` exists) or a second camera matching the community datasets. Off
   this laptop.
3. Report `mean_rate_hz` over the streaming window only; 14.5 Hz reads as a problem it is not.

### F3. Track A cannot decide `fetch` zero-shot
No phrasing fixed it (DEVLOG 2026-09-22). Options: fine-tune `typed-decisions` on scripted-rollout
states (Track C1, off this laptop), or give Track A the same treatment as Track B — the stage from
physics, the model choosing among what that stage allows.

### F4. (minor) The first primitive after entering TELEOP is lost
`back blocked` on the very first jog: `mink_teleop` engages (seeds its target from `/joint_states`)
on its first tick in TELEOP, so a jog sent immediately after the mode switch is absorbed. Wait for
`/cognibot/teleop/ee_target` to publish before the first decision. It cost one step here.

## Log noise that is not a fault
- `move_group`: `No 3D sensor plugin(s) defined for octomap updates` — no octomap in this stack.
- `sim`: `Failed to initialize GLFW. Attempting EGL` and `OpenGL error 0x502 in or before
  mjr_makeContext` — headless rendering falls back to EGL as intended.
- `sim`: `Could not enable FIFO RT scheduling policy` — containers run without RT privileges.
- `vla-client`: `KeyboardInterrupt` traceback — the executor's SIGINT at `max_duration_s`.
- `policy-server`: `unauthenticated requests to the HF Hub` — no `HF_TOKEN` set; not needed for
  local checkpoints.

## Reproduce
```bash
make down && make full
# wait for "decision model ready" in `docker logs cognibot-laya-1`
docker cp driver.py cognibot-laya-1:/tmp/driver.py
docker exec cognibot-laya-1 bash -lc 'source /ws/install/setup.bash && python3 /tmp/driver.py'
make down
```
The driver resets the scene before each test and judges by the cube's pose; it is kept out of the
repository (session tooling) — say if it should become `scripts/fullstack_check.py`.

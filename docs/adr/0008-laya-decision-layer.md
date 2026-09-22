# ADR-0008: Laya as a System-1 decision layer, not a control policy

- **Status:** Proposed
- **Date:** 2026-09-22

## Context

[Laya](https://github.com/NandhaKishorM/laya) ([weights](https://huggingface.co/convaiinnovations/laya), Apache-2.0) was proposed as a fourth way to drive the arm, next to teleop (ADR-0003), the Qwen3-VL agent (ADR-0005, ADR-0007) and SmolVLA inference. The name and the "decision model" framing invite the assumption that it is a VLA. It is not.

Measured from the published artefacts on 2026-09-22 (`laya` 0.3.5 on PyPI, HF repo revision `1c5edc17a7acd8701df6fc341c0d179f1c62c982`):

| Property | Value |
|---|---|
| HF `pipeline_tag` | `text-classification`, `transformersInfo.auto_model: AutoModel` |
| English / typed-decisions checkpoints | ModernBERT-large encoder (395M) + decision head (2 transformer layers, option-marker scorer, act/escalate head) = 421,293,830 params, fp16 |
| Multilingual checkpoint | mmBERT-base, 322M, 1024 tokens, 100+ languages |
| Input | one string; `laya.common.serialize_state` flattens str/dict/list into text (512 tok English, 1024 multilingual) |
| Output | per question `choice` (per-option probabilities), `score` (ordinal expectation), `noul` (P(true)), each with a calibrated confidence and an `act_probability` (act vs escalate) |
| Latency | 33–40 ms/question on a T4; 193–464 ms on CPU (upstream figures) |
| Calibration | ECE 0.081 on the typed-decisions suite (vs 0.246 for the compared baseline) |
| Zero-shot on unseen typed workflows | 0.36 accuracy against a 0.461 majority baseline (upstream's own limitation note) |

There is no image encoder, no proprioception input and no action head anywhere in the package: `Agent.system_one(state, questions)` tokenises a string, scores `[MASK]` markers per option and softmaxes within a question group. The weights cannot emit joint angles, and the checkpoints were never trained on spatial or numeric reasoning.

What the stack does already produce, and what Laya can consume, is a **symbolic scene state**: grounded object labels and positions (`cognibot_vlm/grounding.py`), `/joint_states`, gripper state, held object, control mode, last tool result. The decisions currently taken over that state are taken by a 4B generative model at ≈3.0 s/turn with occasional malformed tool JSON.

## Decision

Adopt Laya as a **System-1 decision layer over the symbolic state**, in a new `cognibot_laya` package and a new `laya` Compose service, with three jobs:

1. **Symbolic control loop.** A `choice` question over the existing action set (`fetch`, `place`, `stack`, `home`, `open`, `close`, `run_vla_skill`, `ask_human`) plus a `choice` over the labels present in the scene; the executor calls the matching action (`/cognibot/fetch_object`, `/cognibot/place_object`, `/cognibot/vla/execute_skill` …), re-grounds, and decides again. This is the fourth control option: a symbolic closed loop at tens of milliseconds per decision instead of seconds per turn.
2. **Guardrail and escalation gate.** `noul` questions in front of `RunAgentTask` and `ExecuteSkill` ("unsafe", "out of workspace", "needs a human"), gated on the calibrated confidence and `act_probability`. Calibration is the one axis on which Laya is clearly stronger than the 4B model.
3. **Multilingual command entry.** Dashboard chat in a non-English language routed to the multilingual checkpoint and mapped to the same typed decision. The router's own numbers show the English checkpoint collapses off English (0.100 on Hindi 20-option intent, at high confidence), so the language route is mandatory, not optional.

Grounding stays with Qwen3-VL and depth — Laya never sees an image. Laya never emits joint angles.

Both the skill loop (**Track A**) and a primitive-level control loop (**Track B**) ship, selectable from one `RLCD` dashboard tab placed after `VLA`:

- **Track A — skill decisions.** The loop above: one decision picks a skill and its object label, the scripted action executes it, the scene is re-grounded.
- **Track B — primitive decisions.** State is serialised as JSON (end-effector pose, target, delta, joint angles, gripper) and one `choice` question offers motion primitives (`x+`, `x-`, `y±`, `z±`, `grasp`, `release`, `done`). The chosen primitive becomes a Cartesian delta for the existing mink integrator, which publishes joint targets on `/cognibot/joint_command` through the safety filter — Laya never emits radians. A per-joint variant (`shoulder_pan ±2°`, …) is the same loop with a different option set.

Track B is expected to be weak: the zero-shot numbers above, plus float coordinates through a BERT tokeniser, predict something close to a random walk. It ships anyway, with its measured success rate published in `benchmarks/rlcd/` and shown in the tab, because the comparison against Track A on the same scenes is the point.

## Consequences

- No new `ControlMode`: Track A drives existing actions, and Track B reuses VLA mode plus the existing IK and safety path. `modes.yaml` is untouched.
- A new `laya` service (torch base image) keeps `transformers`/`torch` away from the LeRobot pins in the `vla` image. PyPI metadata for `laya` 0.3.5 is permissive (`torch>=2.0.0`, `transformers>=4.48.0`) while the upstream README asks for transformers 5.x / torch 2.14+; the package patches tokenizer configs at load time for exactly this reason, so the versions get pinned once, measured, and recorded in `docs/INTEGRATIONS.md`.
- Default device is CPU (0 MiB VRAM, 193–464 ms/question), which fits the 6 GB budget beside the sim and the VLM; `LAYA_DEVICE=cuda` (≈0.85 GB fp16) is available and measured into `docs/VRAM_BUDGET.md`.
- Decision quality is bounded by the zero-shot numbers above. If either track is not good enough on our action set, the next step is a fine-tune on scripted-rollout data (Track C1), not a prompt change; the `RLCD` tab is named for that training method (reinforcement learning from calibrated decisions) because it is where a fine-tuned checkpoint would land.
- `AgentEvent` carries Laya's steps, so the existing dashboard trace panel works without a new event type.

## Alternatives considered

- **Laya as the VLA (a policy that outputs joint targets).** Rejected: no vision, no action head, no state encoder. Reaching joint output means discarding the decision head and keeping only the ModernBERT trunk, at which point the honest baseline is a small MLP over the same state vector, and the "Laya" contribution is nil. Revisit only with a measured MLP baseline to compare against.
- **Shipping only Track A.** Rejected by the owner: both tracks ship as selectable modes so the primitive loop's real performance is measured and visible rather than argued about. The weakness is handled by labelling the mode and publishing its success rate, not by hiding it.
- **Fine-tuning `typed-decisions` on scripted rollouts (Track C1).** Deferred, not rejected: ~10k (state, action) pairs are free from `record_scripted_episodes.py`, but training is 4–5 h on 2×T4 and must run off this laptop (heat, 6 GB). Revisit once P8-T06 measures how far the zero-shot router falls short.
- **Replacing the Qwen agent with Laya.** Rejected: Laya cannot ground objects or read the scene. The two are complementary — Qwen for perception, Laya for the typed decision over the result.

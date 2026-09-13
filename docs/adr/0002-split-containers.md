# ADR-0002: One container per concern, grouped by Compose profiles

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

The stack mixes very different runtimes: a C++ simulator with EGL, MoveIt, a Node-built SPA, a llama.cpp server, a PyTorch policy server and a Python ROS client. Their dependencies conflict: CUDA runtimes, numpy versions, torch. Users need different subsets. Digital-twin or teleop users want only the simulator; others want the VLM, the VLA, or both.

## Decision

Build separate services and enable them with Compose **profiles**:

| Profile | Services |
|---|---|
| *(none / core)* | `sim`, `motion`, `bridge`, `dashboard` |
| `vlm` | + `llm`, `vlm-agent` |
| `vla` | + `policy-server`, `vla-client` |
| `twin` | + `twin` |
| `full` | `vlm` + `vla` |

Our images (`core`, `vlm`, `vla`) come from one multi-stage Dockerfile. An `interfaces` stage builds `cognibot_interfaces` and `cognibot_common` once and copies the install tree into each image. Upstream images (`llama-swap`, `lerobot-gpu`) are used as-is.

## Consequences

- Each image carries only what it needs. The GPU is reserved only by `sim` (EGL), `llm` and `policy-server`.
- Model servers (llama-swap, LeRobot policy_server) can be restarted, swapped or moved to another machine without touching ROS nodes.
- Every ROS image must share the same interface definitions, which the `interfaces` stage guarantees.
- More services to orchestrate. Healthchecks and `depends_on` conditions handle ordering.

## Alternatives considered

- **Single monolithic image.** Dependency conflicts (torch vs apt numpy), a huge image, and no way to run just the sim.
- **Kubernetes / Helm.** Overkill for a single laptop.

# Architecture Decision Records

Each ADR records one significant decision: its context, the decision itself and its consequences. ADRs are immutable once accepted. To change a decision, write a new ADR that supersedes the old one.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-jazzy-over-humble.md) | ROS 2 Jazzy instead of Humble | Accepted |
| [0002](0002-split-containers.md) | One container per concern, grouped by Compose profiles | Accepted |
| [0003](0003-mink-plus-moveit.md) | Two-tier motion: mink for teleop, MoveIt 2 + pick_ik for planning | Accepted |
| [0004](0004-cyclonedds-host-network.md) | CycloneDDS over host networking, localhost-only discovery | Accepted |
| [0005](0005-llamacpp-llamaswap-qwen3vl.md) | Qwen3-VL-4B on llama.cpp behind llama-swap, with RAM offload profiles | Accepted |
| [0006](0006-integrate-dont-invent.md) | Integrate maintained components; write only glue | Accepted |

Template: copy `0000-template.md`.

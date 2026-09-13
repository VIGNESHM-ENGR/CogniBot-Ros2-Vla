"""Pure control-mode arbitration: which controllers to switch and which transitions are legal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from cognibot_interfaces.msg import ControlMode

MODE_NAMES: dict[int, str] = {
    ControlMode.IDLE: "IDLE",
    ControlMode.TELEOP: "TELEOP",
    ControlMode.MOTION: "MOTION",
    ControlMode.VLA: "VLA",
    ControlMode.TWIN: "TWIN",
}
MODE_IDS: dict[str, int] = {name: mode for mode, name in MODE_NAMES.items()}


class ModeError(ValueError):
    """Unknown mode or forbidden transition."""


@dataclass(frozen=True)
class ModeTable:
    active: dict[int, tuple[str, ...]]
    transitions: frozenset[tuple[int, int]]

    @property
    def managed(self) -> tuple[str, ...]:
        seen: list[str] = []
        for controllers in self.active.values():
            seen.extend(c for c in controllers if c not in seen)
        return tuple(seen)

    def allowed(self, current: int, target: int) -> bool:
        return (
            current == target
            or target == ControlMode.IDLE
            or current == ControlMode.IDLE
            or (current, target) in self.transitions
        )

    def switch(self, current: int, target: int) -> tuple[list[str], list[str]]:
        """Return (activate, deactivate) controller lists for a STRICT switch_controller call."""
        if target not in self.active:
            raise ModeError(f"unknown mode {target}")
        if not self.allowed(current, target):
            raise ModeError(
                f"transition {MODE_NAMES.get(current, current)} → {MODE_NAMES[target]} not allowed"
            )
        wanted = set(self.active[target])
        have = set(self.active.get(current, ()))
        activate = [c for c in self.active[target] if c not in have]
        deactivate = [c for c in self.managed if c in have and c not in wanted]
        return activate, deactivate


def load_mode_table(path: Path | str) -> ModeTable:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    active: dict[int, tuple[str, ...]] = {}
    for name, spec in data["modes"].items():
        if name not in MODE_IDS:
            raise ModeError(f"unknown mode '{name}' in {path}")
        active[MODE_IDS[name]] = tuple(spec["active"])
    missing = set(MODE_IDS) - {MODE_NAMES[m] for m in active}
    if missing:
        raise ModeError(f"modes.yaml lacks {sorted(missing)}")
    transitions = frozenset((MODE_IDS[a], MODE_IDS[b]) for a, b in data.get("transitions", []))
    return ModeTable(active=active, transitions=transitions)

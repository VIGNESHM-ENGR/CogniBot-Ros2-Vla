"""The decision model behind a two-method protocol, so everything else is testable without torch.

`LayaModel` wraps `laya.Router`: one forward pass answers every question in the set, and the
router picks the checkpoint by script and language (the English checkpoint scores 0.100 on Hindi
20-option intent while reporting high confidence, so routing is not optional).
"""

from __future__ import annotations

import time
from typing import Any, Protocol


class DecisionModel(Protocol):
    def predict(self, state: dict, questions: dict) -> dict[str, Any]: ...


class LayaModel:
    """`laya.Router` loaded once, queried per decision."""

    def __init__(
        self,
        model: str = "auto",
        device: str = "cpu",
        preload: bool = True,
        max_loaded: int = 2,
        snapshot_dir: str = "",
    ) -> None:
        from laya import Router  # torch import: keep it out of module import time

        # `auto` lets the router pick by script and language; a name pins one checkpoint.
        self.model = None if model in ("", "auto") else model
        # With a snapshot directory the three checkpoints are read straight off the mounted cache:
        # the container runs offline, and a repo id would send the hub a request for `main` that
        # offline mode refuses even when the pinned revision is already downloaded.
        models = (
            {
                "english": (snapshot_dir, None),
                "multilingual": (snapshot_dir, "multilingual"),
                "typed-decisions": (snapshot_dir, "typed-decisions"),
            }
            if snapshot_dir
            else None
        )
        self._router = Router(models=models, device=device, preload=preload, max_loaded=max_loaded)
        self.last_latency_ms = 0.0

    def predict(self, state: dict, questions: dict) -> dict[str, Any]:
        started = time.perf_counter()
        payload = self._router.predict(state, questions, model=self.model)
        self.last_latency_ms = (time.perf_counter() - started) * 1000.0
        return payload

    def describe(self) -> str:
        return f"laya router (loaded: {getattr(self._router, 'loaded', '?')})"

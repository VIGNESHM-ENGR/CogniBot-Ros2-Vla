"""The decision model behind a two-method protocol, so everything else is testable without torch.

`LayaModel` wraps `laya.Router`: one forward pass answers every question in the set, and the
router picks the checkpoint by script and language (the English checkpoint scores 0.100 on Hindi
20-option intent while reporting high confidence, so routing is not optional).
"""

from __future__ import annotations

import time
from typing import Any, Protocol


class DecisionModel(Protocol):
    def unload(self) -> None: ...

    def reload(self) -> None: ...

    @property
    def loaded(self) -> bool: ...

    def predict(self, state: dict, questions: dict, route_text: str = "") -> dict[str, Any]: ...


class LayaModel:
    """`laya.Router` loaded once, queried per decision."""

    def __init__(
        self,
        model: str = "auto",
        device: str = "cuda",
        preload: bool = True,
        max_loaded: int = 1,
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
        # `Router(preload=True)` builds all three checkpoints and raises `max_loaded` to fit them
        # (~2.3 GB of VRAM on the GPU). Preload only the English one every English task uses; the
        # others load on first use and share the `max_loaded` budget.
        self._router = Router(models=models, device=device, preload=False, max_loaded=max_loaded)
        if preload:
            self._router.preload(["english"])
        self.last_latency_ms = 0.0

    def unload(self) -> None:
        """Free every checkpoint (and the CUDA cache) so another model can use the GPU."""
        self._router.unload()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:  # pragma: no cover - torch is always present in the laya image
            pass

    def reload(self) -> None:
        """Load the English checkpoint again after `unload` (~13 s on the GPU)."""
        self._router.preload(["english"])

    @property
    def loaded(self) -> bool:
        return bool(getattr(self._router, "loaded", []))

    def predict(self, state: dict, questions: dict, route_text: str = "") -> dict[str, Any]:
        """Answer every question in one pass, routing on `route_text` when it is given.

        Routing has to see the operator's sentence, not the serialised state: the state is mostly
        English keys and object labels, so a Hindi or Tamil task inside it still looks Latin to the
        script detector and lands on the English checkpoint, which collapses off English.
        """
        started = time.perf_counter()
        model = self.model
        if model is None and route_text:
            model = self._router.route(route_text, questions)["model"]
        payload = self._router.predict(state, questions, model=model)
        self.last_latency_ms = (time.perf_counter() - started) * 1000.0
        return payload

    def describe(self) -> str:
        return f"laya router (loaded: {getattr(self._router, 'loaded', '?')})"

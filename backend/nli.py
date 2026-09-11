"""Phase 2 — Dedicated Natural Language Inference verification.

The existing verifier combines a deterministic fast-path with an LLM
"logical support" judge. That judge is useful but is not a dedicated NLI
system. This module adds a real entailment model so a claim is classified as
one of:

    ENTAILMENT | NEUTRAL | CONTRADICTION

with a model confidence. Like the reranker, model loading is lazy and cached,
and a model that cannot load degrades gracefully to ``None`` so the caller can
fall back to the existing LLM verifier.

The default model is a small, CPU-friendly cross-encoder NLI model suitable
for an M-series Mac. Swap it via ``HALLUFIX_NLI_MODEL`` (e.g. the larger
``microsoft/deberta-v3-large-mnli`` or ``cross-encoder/nli-deberta-v3-base``).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from .config import get_settings

logger = logging.getLogger(__name__)

LABEL_ENTAILMENT = "ENTAILMENT"
LABEL_NEUTRAL = "NEUTRAL"
LABEL_CONTRADICTION = "CONTRADICTION"

# Default label order expected from a sentence-transformers cross-encoder NLI
# model (index 0 = contradiction, 1 = entailment, 2 = neutral).
DEFAULT_LABELS = [LABEL_CONTRADICTION, LABEL_ENTAILMENT, LABEL_NEUTRAL]

# Singleton + lock for lazy, one-time loading.
_lock = threading.Lock()
_model = None
_model_name = None
_model_failed: bool = False


class NLIError(RuntimeError):
    """Raised when the NLI model is unavailable."""


@dataclass(frozen=True)
class NLIResult:
    label: str
    confidence: float
    scores: dict[str, float]
    model: str
    method: str = "nli"


def _model_choice() -> str:
    return get_settings().nli_model


def _labels() -> list[str]:
    env = getattr(get_settings(), "_nli_labels", None)
    if env:
        return list(env)
    return list(DEFAULT_LABELS)


def load_model():
    """Lazily build and cache the cross-encoder NLI model (thread-safe)."""
    global _model, _model_name, _model_failed
    selected = _model_choice()
    if _model is not None and _model_name == selected:
        return _model
    with _lock:
        if _model is not None and _model_name == selected:
            return _model
        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading NLI cross-encoder: %s", selected)
            _model = CrossEncoder(selected, device="cpu")
            _model_name = selected
            _model_failed = False
        except Exception as exc:  # noqa: BLE001
            _model_failed = True
            raise NLIError(f"Could not load NLI model {selected}: {exc}") from exc
    return _model


def classify(claim: str, evidence: str) -> NLIResult | None:
    """Classify ``claim`` against ``evidence``.

    Returns an ``NLIResult`` or ``None`` when the model is disabled /
    unavailable (caller should then fall back to the LLM verifier).
    """
    if not get_settings().nli_enabled:
        return None
    if not claim.strip() or not evidence.strip():
        return None
    try:
        model = load_model()
    except NLIError as exc:
        logger.warning("NLI unavailable; skipping NLI stage. %s", exc)
        return None
    if model is None:
        return None

    try:
        logits = model.predict([(claim, evidence)])
        logits = list(logits[0]) if hasattr(logits[0], "__iter__") else [logits]
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLI predict failed for a claim: %s", exc)
        return None

    labels = _labels()
    k = min(len(labels), len(logits))
    if k == 0:
        return None

    import numpy as np

    scores = {labels[i]: float(np.exp(logits[i])) for i in range(k)}
    total = sum(scores.values()) or 1.0
    probs = {label: (value / total) for label, value in scores.items()}
    label = max(probs, key=probs.get)
    return NLIResult(
        label=label,
        confidence=float(probs[label]),
        scores=probs,
        model=_model_choice(),
        method="nli",
    )


def label_means_supported(label: str) -> bool:
    """Map an NLI label to the boolean ``supported`` used by the pipeline."""
    return label == LABEL_ENTAILMENT


def threshold(label: str) -> float:
    """Return the configurable confidence threshold for a given label."""
    cfg = get_settings()
    if label == LABEL_ENTAILMENT:
        return cfg.nli_entailment_threshold
    if label == LABEL_CONTRADICTION:
        return cfg.nli_contradiction_threshold
    return 0.0
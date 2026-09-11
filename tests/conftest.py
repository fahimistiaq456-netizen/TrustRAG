"""Shared pytest fixtures that isolate global state between tests.

``get_settings`` is an LRU-cached process-wide singleton (intended for the
long-running server). Under pytest that same singleton leaks config changes
between tests — e.g. enabling NLI in one test would make a later test actually
load a real model. This autouse fixture:

  * clears the settings cache,
  * resets the lazy model singletons in reranker/nli,
  * ensures the default (disabled) state for every optional feature.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_optional_features():
    from backend import config

    config.get_settings.cache_clear()
    settings = config.get_settings()
    # Defaults: optional ML/security features are OFF unless a test opts in.
    settings.reranker_enabled = False
    settings.nli_enabled = False
    settings.graph_enabled = False
    settings.auth_enabled = False

    import backend.reranker as rr
    import backend.nli as nli

    rr._model = None
    rr._model_failed = False
    nli._model = None
    nli._model_name = None
    nli._model_failed = False
    yield
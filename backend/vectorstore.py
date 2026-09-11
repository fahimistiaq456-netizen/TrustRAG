"""Local, CPU-friendly FAISS persistence for handbook chunks."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from .ingest import Chunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

logger = logging.getLogger(__name__)


def load_embedding_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    """Load the embedding model deterministically, self-healing corrupted caches.

    Newer transformers piles can load models on the ``meta`` device (via the
    ``low_cpu_mem_usage`` path), which then crashes with
    ``NotImplementedError: Cannot copy out of meta tensor`` when moved to a real
    device. We therefore disable that path explicitly.

    A corrupted Hugging Face cache (partial download, bad safetensors blob) can
    also break model loading and make the whole API 500. When the first load
    fails we clear *only that model's* cache entry and retry once, so sources,
    ingest, RAG and hybrid keep working after a transient/corrupt download.
    """
    _imports_supported = True
    try:
        from huggingface_hub import scan_cache_dir  # noqa: F401
    except ImportError:
        _imports_supported = False

    def _load() -> SentenceTransformer:
        return SentenceTransformer(model_name, model_kwargs={"low_cpu_mem_usage": False})

    try:
        return _load()
    except Exception as first_exc:  # noqa: BLE001 - any load failure may be cache corruption
        logger.warning("Embedding model load failed (%s); attempting cache self-heal.", first_exc)
        if not _imports_supported:
            raise
        try:
            cache_scanned = scan_cache_dir()
        except Exception:  # noqa: BLE001
            cache_scanned = None
        removed = _clear_model_cache(model_name, cache_scanned)
        if removed:
            logger.info("Cleared corrupted cache entries for %s (%s); retrying model load.", model_name, removed)
            try:
                return _load()
            except Exception as retry_exc:  # noqa: BLE001
                raise RuntimeError(
                    f"Failed to load the embedding model '{model_name}' "
                    f"even after clearing its cache entry ({removed}). "
                    "Check your network connection to Hugging Face and try again."
                ) from retry_exc
        raise RuntimeError(
            f"Failed to load the embedding model '{model_name}' ({first_exc}). "
            "The Hugging Face model cache may be corrupted; deleting the local HF cache "
            "(`rm -rf ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2`) "
            "and restarting usually fixes this."
        ) from first_exc


def _clear_model_cache(model_name: str, scanned) -> list[str]:
    """Delete the HF hub cache entry(ies) for ``model_name``; return removed paths."""
    removed: list[str] = []
    if scanned is None:
        return removed
    model_dir = f"models--{model_name.replace('/', '--')}"
    for repo in getattr(scanned, "repos", []):
        if repo.repo_id == model_name:
            try:
                shutil.rmtree(str(repo.repo_path), ignore_errors=True)
                removed.append(str(repo.repo_path))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not clear HF cache for %s: %s", model_name, exc)
    if removed:
        return removed
    # Fallback: remove the well-known layout if scan failed.
    for base in (Path.home() / ".cache" / "huggingface" / "hub" / model_dir,):
        if base.exists():
            try:
                shutil.rmtree(str(base), ignore_errors=True)
                removed.append(str(base))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not remove %s: %s", base, exc)
    return removed


class LocalVectorStore:
    def __init__(self, index_dir: str | Path, model_name: str = MODEL_NAME) -> None:
        self.index_dir = Path(index_dir)
        self.model = load_embedding_model(model_name)
        self.index: faiss.Index | None = None
        self.chunks: list[dict[str, object]] = []

    def build(self, chunks: list[Chunk]) -> None:
        vectors = self.model.encode([c.text for c in chunks], normalize_embeddings=True, show_progress_bar=False)
        self.index = faiss.IndexFlatIP(vectors.shape[1])  # normalized inner product = cosine similarity
        self.index.add(np.asarray(vectors, dtype=np.float32))
        self.chunks = [{"text": c.text, **c.metadata()} for c in chunks]

    def save(self) -> None:
        if self.index is None:
            raise RuntimeError("Build or load an index before saving.")
        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_dir / "handbook.faiss"))
        (self.index_dir / "metadata.json").write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")

    def load(self) -> None:
        index_path, metadata_path = self.index_dir / "handbook.faiss", self.index_dir / "metadata.json"
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Index not found. Run `python -m backend.ingest` or use build_index first.")
        self.index = faiss.read_index(str(index_path))
        self.chunks = json.loads(metadata_path.read_text(encoding="utf-8"))

    def search(self, question: str, k: int = 5) -> list[dict[str, object]]:
        if self.index is None:
            raise RuntimeError("Index has not been loaded.")
        vector = self.model.encode([question], normalize_embeddings=True)
        scores, ids = self.index.search(np.asarray(vector, dtype=np.float32), min(k, len(self.chunks)))
        return [{**self.chunks[idx], "similarity_score": float(score)} for score, idx in zip(scores[0], ids[0]) if idx >= 0]

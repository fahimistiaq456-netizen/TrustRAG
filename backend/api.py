"""Local-only FastAPI orchestration for baseline and Hallufix chat."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .abstention import ABSTENTION_MESSAGE, should_abstain
from .decision_engine import MODE_RAG
from .generator import generate_answer
from .hybrid import NORMAL_SYSTEM_PROMPT, run_hybrid
from .ingest import ingest_paths
from .local_llm import LocalLLMError, available_models, chat, model_name
from .reranker import rerank_candidates
from .graph_retriever import build_graph, graph_retrieve
from .retriever import best_source_sentence, citation, evidence_text, retrieve
from .vectorstore import LocalVectorStore
from .verifier import verification_summary, verify_answer
from .auth import database as auth_db
from .auth.dependencies import get_current_user, require_role
from .auth.routes import router as auth_router
from .admin_routes import router as admin_router
from .evaluation_routes import router as evaluation_router


def _empty_verification_summary() -> dict[str, object]:
    return {"supported_claims": 0, "unsupported_claims": 0, "claims_checked": 0, "claims_supported": 0, "support_rate": 1.0}

load_dotenv()
app = FastAPI(title="TrustRAG Local API", version="2.1.0")
logger = logging.getLogger(__name__)
SOURCES_DIR = Path("data/sources")

# Browser access for the local Next.js frontend (`npm run dev` on port 3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("HALLUFIX_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount auth, evaluation and admin route groups.
app.include_router(auth_router)
app.include_router(evaluation_router)
app.include_router(admin_router)

# Create auth tables / default admin at startup (auth may be disabled later).
try:
    auth_db.init_db()
except Exception as exc:  # noqa: BLE001 - startup must not crash the app
    logger.warning("Auth DB init skipped: %s", exc)

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=12)

def _log(record: dict[str, object]) -> None:
    path = Path("logs") / f"answer_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")

def _history_messages(history: list[Message]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in history]

def _load_store() -> LocalVectorStore:
    store = LocalVectorStore(os.getenv("HALLUFIX_INDEX_DIR", "data/index"))
    store.load()
    return store

@app.get("/health")
def health() -> dict[str, object]:
    models = available_models()
    return {"ollama_running": bool(models), "selected_model": model_name(), "selected_model_available": model_name() in models, "available_models": models}

@app.post("/chat/normal")
def normal_chat(request: ChatRequest) -> dict[str, object]:
    started = time.perf_counter()
    messages = [{"role": "system", "content": NORMAL_SYSTEM_PROMPT}, *_history_messages(request.history), {"role": "user", "content": request.question}]
    try:
        answer = chat(messages, temperature=0.7)
    except LocalLLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"answer": answer, "latency_ms": round((time.perf_counter() - started) * 1000), "model": model_name()}

def _run_rag(question: str, started: float, trigger: str | None = None, current_user: object | None = None) -> dict[str, object]:
    """Run the full RAG pipeline: retrieve, abstain-gate, generate, verify.

    Returns a display payload identical to ``POST /ask``. When ``trigger`` is
    provided (e.g. ``"llm_fallback"``) it is recorded in the audit log so the
    reason the RAG path ran stays traceable.
    """
    cands = retrieve(_load_store(), question)
    graph_used = False
    if cands:
        cands, graph_used = graph_retrieve(question, cands)
        cands, reranked = rerank_candidates(question, cands)
    else:
        reranked = False
    chunks = cands
    elapsed = round((time.perf_counter() - started) * 1000)
    if not chunks:
        return {
            "answer": ABSTENTION_MESSAGE,
            "mode": MODE_RAG,
            "sources": [],
            "verification": [],
            "verification_summary": _empty_verification_summary(),
            "confidence": 0.0,
            "abstained": True,
            "stats": {"latency_ms": elapsed, "claims_checked": 0, "claims_supported": 0, "support_rate": 0.0, "model": model_name()},
            "latency_ms": elapsed,
            "model": model_name(),
            "graph_used": graph_used,
            "reranked": reranked,
        }

    abstained, confidence = should_abstain(chunks, float(os.getenv("HALLUFIX_ABSTENTION_THRESHOLD", "0.25")))
    generated, verified, verification = "", "", []
    if abstained:
        # Low retrieval confidence: still let the strict extractive generator
        # answer. It returns a verbatim source sentence only when it actually
        # answers the question, and abstains otherwise (e.g. for an aspect the
        # source does not state). Retrieval confidence and answer support are
        # deliberately kept separate.
        verified = generate_answer(question, chunks)
        if verified != ABSTENTION_MESSAGE:
            verification.append({
                "claim": verified,
                "supported": True,
                "confidence": 1.0,
                "label": "ENTAILMENT",
                "method": "extractive",
                "evidence": evidence_text(chunks),
                "reason": "Verbatim source sentence selected despite low overall retrieval confidence.",
            })
    else:
        generated = generate_answer(question, chunks)
        if generated == ABSTENTION_MESSAGE:
            # The generator deliberately abstained (no relevant evidence, or the
            # question asks for an aspect the source does not state). Do not
            # verify an abstention and do not override it with a guessed answer.
            verified, verification = generated, []
        else:
            verified, verification = verify_answer(generated, chunks)
            # Only salvage a *generated* answer that verification rejected. If
            # the generator itself abstained, respect that instead of overriding.
            if verified == ABSTENTION_MESSAGE:
                fallback = best_source_sentence(question, chunks)
                if fallback:
                    verified = fallback
                    verification.append({
                        "claim": fallback,
                        "supported": True,
                        "confidence": 1.0,
                        "reason": "Returned verbatim from the highest-matching retrieved source sentence after generated wording was rejected.",
                    })
    supported = sum(1 for item in verification if item["supported"])
    payload = {
        "answer": verified,
        "mode": MODE_RAG,
        "sources": [{"file": c["document_name"], "page": c.get("page_number"), "citation": citation(c), "similarity_score": c.get("similarity_score", 0.0), "reranker_score": c.get("reranker_score"), "text": c["text"], "from_graph": c.get("from_graph", False)} for c in chunks[:5]],  # Show top 5 sources
        "verification": verification,
        "verification_summary": verification_summary(verification),
        "confidence": confidence, "abstained": verified == ABSTENTION_MESSAGE,
        "graph_used": graph_used,
        "reranked": reranked,
        "graph_neighbors": len([c for c in chunks if c.get("from_graph")]),
        "stats": {"latency_ms": round((time.perf_counter() - started) * 1000), "claims_checked": len(verification), "claims_supported": supported, "support_rate": round(supported / len(verification), 2) if verification else 1.0, "model": model_name()},
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "model": model_name(),
    }
    log_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": getattr(current_user, "id", None),
        "question": question,
        "retrieved_chunks": chunks,
        "retrieval_mode": "faiss+graph" if graph_used else "faiss",
        "reranked": reranked,
        "generated_answer": generated,
        "verified_answer": verified,
        "verification_results": verification,
        "confidence_score": confidence,
        "abstained": abstained,
    }
    if trigger:
        log_record["trigger"] = trigger
    _log(log_record)
    return payload


@app.post("/chat/hybrid")
def hybrid_chat(request: ChatRequest) -> dict[str, object]:
    """Hybrid intelligence: local answer, judge, then LLM / RAG / abstain.

    The pipeline is handled by ``hybrid.run_hybrid``. The payload reports the
    selected ``mode`` ("LLM", "RAG", or "ABSTAIN"); RAG answers include
    sources, verification, and confidence.
    """
    started = time.perf_counter()
    try:
        payload = run_hybrid(request.question, load_store=_load_store)
    except FileNotFoundError as exc:
        raise HTTPException(503, "No index exists. Upload sources in the Data tab or run `python -m backend.build_index data`.") from exc
    except LocalLLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Hybrid pipeline failed while answering a question")
        raise HTTPException(500, "Unable to process the question. Check the Uvicorn terminal for details.") from exc
    payload.setdefault("stats", {})
    payload["latency_ms"] = round((time.perf_counter() - started) * 1000)
    payload["model"] = model_name()
    return payload


@app.post("/ask")
def ask(request: ChatRequest, current_user: object = Depends(get_current_user)) -> dict[str, object]:
    started = time.perf_counter()
    try:
        return _run_rag(request.question, started, current_user=current_user)
    except FileNotFoundError as exc:
        raise HTTPException(503, "No index exists. Upload sources in the Data tab or run `python -m backend.build_index data`.") from exc
    except LocalLLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Hallufix failed while answering a question")
        raise HTTPException(500, "Unable to process the question. Check the Uvicorn terminal for details.") from exc

@app.get("/sources")
def sources() -> dict[str, object]:
    """Return the local source library state for the frontend Sources view."""
    files = sorted(p.name for p in SOURCES_DIR.iterdir() if p.suffix.lower() in {".txt", ".pdf"})
    index_ready, chunk_count = False, 0
    try:
        store = _load_store()
        chunk_count = len(store.chunks)
        index_ready = True
    except FileNotFoundError:
        pass
    return {"files": files, "chunk_count": chunk_count, "index_ready": index_ready}

@app.post("/ingest")
async def ingest(files: list[UploadFile] = File(...), _: object = Depends(require_role("ADMIN"))) -> dict[str, object]:
    """Save multiple TXT/PDF sources, then rebuild one ranked local index + graph."""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for file in files:
        name = Path(file.filename or "").name
        target = SOURCES_DIR / name
        if not name or target.suffix.lower() not in {".txt", ".pdf"}:
            raise HTTPException(400, "Only .txt and .pdf files are supported.")
        target.write_bytes(await file.read())
        saved.append(target)
    try:
        chunks = ingest_paths(sorted(p for p in SOURCES_DIR.iterdir() if p.suffix.lower() in {".txt", ".pdf"}))
        store = LocalVectorStore(os.getenv("HALLUFIX_INDEX_DIR", "data/index")); store.build(chunks); store.save()
        # Phase 4: build the local knowledge graph from the fresh index.
        try:
            build_graph(store.chunks, path="data/index/graph.json")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph build skipped during ingest: %s", exc)
        return {"files": [path.name for path in saved], "source_count": len({chunk.document_name for chunk in chunks}), "chunk_count": len(chunks)}
    except Exception as exc:
        logger.exception("Source ingestion failed")
        raise HTTPException(500, f"Unable to build the local index: {exc}") from exc

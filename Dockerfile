# ── TrustRAG Backend – Production Dockerfile ──────────────────────────────
# Multi-stage build: smaller final image, no build-time deps in production layer.
# Compatible with Render, Railway, Fly.io and any Docker-based host.
# ---------------------------------------------------------------------------

# ── 1. Builder stage – install Python dependencies ─────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools needed by some Python C extensions (faiss, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 2. Runtime stage – lean final image ────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source and pre-built index / sources
COPY backend/ ./backend/
COPY data/ ./data/
COPY .env.example .env.example

# Create data and log directories expected at runtime
RUN mkdir -p data/index data/sources logs

# Expose the FastAPI port
EXPOSE 8000

# Health-check so hosting platforms mark the container healthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Launch Uvicorn – PORT env var is respected by Render / Railway automatically
CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

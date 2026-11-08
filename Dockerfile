# ── TrustRAG Backend – Lightweight Production Dockerfile ───────────────────
# Optimized for Render Free Tier (512 MB RAM limit).
# Uses CPU-only PyTorch to prevent Out-Of-Memory (OOM) build crashes.
# ---------------------------------------------------------------------------

FROM python:3.11-slim

WORKDIR /app

# Install minimal system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install CPU-only PyTorch (~160 MB instead of 2 GB CUDA package)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, pre-built index and handbook documents
COPY backend/ ./backend/
COPY data/ ./data/
COPY .env.example .env.example

# Ensure runtime directories exist
RUN mkdir -p data/index data/sources logs

# Expose standard port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start Uvicorn bound to 0.0.0.0 and PORT (Render assigns dynamic PORT)
CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

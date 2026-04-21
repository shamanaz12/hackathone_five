# ============================================================
# TaskFlow AI Support Agent — Dockerfile
# CRM Digital FTE Factory Final Hackathon 5
#
# Usage:
#   docker build -t taskflow-agent:latest .
#   docker run -p 8000:8000 taskflow-agent:latest
# ============================================================

FROM python:3.11-slim

# ── System Dependencies ──────────────────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# ── Working Directory ────────────────────────────────────
WORKDIR /app

# ── Python Dependencies ──────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application Code ─────────────────────────────────────
COPY . .

# ── Environment ──────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app

# ── Health Check ─────────────────────────────────────────
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Port ─────────────────────────────────────────────────
EXPOSE 8000

# ── Default Command (override in docker-compose for worker) ──
CMD ["python", "-m", "uvicorn", "production.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

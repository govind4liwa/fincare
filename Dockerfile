# ============================================================
# FinCare — Multi-stage Dockerfile
# ============================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --upgrade pip && \
    pip wheel --wheel-dir /wheels -r requirements/prod.txt

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=fincare.settings.prod \
    PATH="/home/fincare/.local/bin:$PATH"

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libffi8 \
        curl \
        # WeasyPrint runtime deps
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r fincare && \
    useradd -r -g fincare -d /home/fincare -m -s /sbin/nologin fincare

WORKDIR /app

# Install wheels from builder
COPY --from=builder /wheels /wheels
COPY requirements/ requirements/
RUN pip install --no-index --find-links=/wheels -r requirements/prod.txt && \
    rm -rf /wheels

# Copy application
COPY --chown=fincare:fincare . /app/

# Collect static will be run at deploy time, not build time
USER fincare

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/ || exit 1

CMD ["gunicorn", "fincare.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# --- Stage 3: Dev (local development image) ---
# Extends runtime with dev/test/profiling tooling (pytest, ruff, debug_toolbar,
# silk, etc.) so DJANGO_SETTINGS_MODULE=fincare.settings.dev can import its apps.
# Used by docker compose for local dev only; production uses the runtime stage.
FROM runtime AS dev

USER root
RUN pip install --no-cache-dir -r requirements/dev.txt
ENV DJANGO_SETTINGS_MODULE=fincare.settings.dev
USER fincare

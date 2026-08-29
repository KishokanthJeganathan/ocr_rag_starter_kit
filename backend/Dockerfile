FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # venv lives outside /app so the source bind-mount can't shadow it.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# curl: compose healthcheck.  libmagic1: python-magic file-type detection.
RUN apt-get update && apt-get install -y --no-install-recommends curl libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

WORKDIR /app

# Build context is the repo root. The backend has an editable path dependency
# on ../generator, so that source must be present before `uv sync`.
COPY generator /generator

# Install dependencies first for layer caching.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY backend/ .
RUN uv sync --frozen

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

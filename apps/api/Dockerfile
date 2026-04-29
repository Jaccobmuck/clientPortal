FROM python:3.12-slim AS base

# System deps for WeasyPrint + asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 \
    libffi-dev libssl-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── Dependencies layer ────────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Final image ───────────────────────────────────────────────────────────
FROM base AS runner
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

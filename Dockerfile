# Backend image for the FastAPI + LangGraph app.
# Slim Python base: major-map extraction (Playwright/Chromium) is disabled by default
# (MAJOR_MAP_ENABLED=false), so no browser is needed here. To re-enable it, switch to
# mcr.microsoft.com/playwright/python and add `RUN uv run playwright install chromium`.
FROM python:3.12-slim

WORKDIR /app

# uv for fast, lockfile-faithful installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies first (cached layer), then the project itself
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project
COPY src ./src
COPY README.md ./
RUN uv sync --no-dev --frozen

# Hosts (Render) inject $PORT; default to 8000 locally
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn collagent.api.main:app --host 0.0.0.0 --port ${PORT}"]

FROM ghcr.io/astral-sh/uv:0.12.1 AS uv
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/src/.venv/bin:${PATH}
WORKDIR /src
COPY --from=uv /uv /uvx /bin/
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --extra lab --no-install-project

WORKDIR /workspace/backend

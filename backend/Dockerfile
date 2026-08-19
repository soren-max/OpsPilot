FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim AS runtime

ARG APP_VERSION=0.1.0
LABEL org.opencontainers.image.title="OpsPilot Backend" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/src/.venv/bin:${PATH} \
    OPSPILOT_SERVER_HOST=0.0.0.0 \
    OPSPILOT_SERVER_PORT=8000

WORKDIR /app
COPY --from=builder /src/.venv /src/.venv
RUN apt-get update \
    && apt-get install --yes --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 opspilot \
    && useradd --uid 10001 --gid opspilot --create-home opspilot \
    && install -d -o opspilot -g opspilot /var/log/opspilot /var/lib/opspilot
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000
USER 10001:10001
CMD ["python", "-m", "app.server"]

FROM builder AS development-builder

RUN uv sync --frozen --extra dev --no-editable

FROM runtime AS development

USER root
COPY --from=development-builder /src/.venv /src/.venv
USER 10001:10001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

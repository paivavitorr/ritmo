FROM ghcr.io/astral-sh/uv:0.9.5 AS uv

# --- build: resolve as dependências em um venv isolado ---
FROM python:3.13-slim AS build

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- runtime: só o venv e o código, usuário não-root ---
FROM python:3.13-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 1001 ritmo \
    && useradd --system --uid 1001 --gid ritmo --no-create-home ritmo

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=ritmo:ritmo . .

USER ritmo

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=3)"]

# Migrations NÃO rodam aqui: use o serviço `migrate` (prod) ou o `command` do compose (dev).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

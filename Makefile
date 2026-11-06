.PHONY: install run run-detached down down-clean db run-api run-front migrate migration types test lint format typecheck check

# Instalar dependências de todos os sub-projetos
install:
	cd backend && uv sync
	cd frontend && pnpm install

# Rodar tudo via Docker (com hot reload)
run:
	docker compose up --build --watch

run-detached:
	docker compose up -d --build

down:
	docker compose down

# Para e apaga o volume do banco
down-clean:
	docker compose down -v

# Só o Postgres (para rodar API/front localmente)
db:
	docker compose up -d postgres

run-api:
	cd backend && DATABASE_URL=postgresql+asyncpg://ritmo:ritmo@localhost:5433/ritmo uv run uvicorn app.main:app --reload

run-front:
	cd frontend && pnpm dev

migrate:
	cd backend && uv run alembic upgrade head

# Uso: make migration m="cria usuario"
migration:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

# Gera tipos TypeScript a partir do OpenAPI do FastAPI (sem precisar subir servidor)
types:
	mkdir -p frontend/app/types
	cd backend && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))" > ../frontend/app/types/openapi.json
	cd frontend && pnpm exec openapi-typescript app/types/openapi.json -o app/types/api.d.ts && rm -f app/types/openapi.json
	cd frontend && pnpm lint:fix

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm lint:fix

typecheck:
	cd backend && uv run mypy app
	cd frontend && pnpm typecheck

# Tudo que o CI roda
check: lint typecheck test

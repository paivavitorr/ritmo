# Ritmo — Contexto do Projeto

## Visão Geral

Cronograma inteligente de rotina pessoal: blocos de tempo (time blocking), cálculo de
horas líquidas por categoria, aderência ao planejado e lembretes via Web Push. PWA
offline-first. Blueprint completo nas decisões abaixo.

## Estrutura

```
ritmo/
├── backend/    # FastAPI + SQLAlchemy 2 async + Alembic (Python 3.13, uv)
├── frontend/   # Nuxt 4 (SPA, ssr: false) + Pinia + Tailwind v4
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Stack

- **Backend:** Python 3.13, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 (asyncpg), Alembic (template async)
- **Frontend:** Nuxt 4, Vue 3 `<script setup>` + TS strict, Pinia, Tailwind CSS v4 (`@tailwindcss/vite`), `@nuxt/fonts` (Figtree)
- **Banco:** PostgreSQL 16 (Docker, porta host **5433**) — também no dev
- **Qualidade:** ruff, mypy strict, pytest-asyncio; ESLint (`@nuxt/eslint`), `nuxt typecheck`

## Comandos

```bash
make install     # uv sync + pnpm install
make run         # docker compose up --build --watch (postgres, backend :8000, frontend :3000)
make db          # só o Postgres
make run-api     # API local contra o Postgres do compose
make run-front   # Nuxt dev local
make migrate     # alembic upgrade head
make migration m="descricao"   # autogenerate
make types       # gera frontend/app/types/api.d.ts a partir do OpenAPI do FastAPI
make check       # lint + typecheck + testes (o mesmo que o CI)
```

## Convenções

- Código, comentários e commits em **português**; commits em **Conventional Commits**.
- Backend: rotas `async`, dependências via `Annotated` (`app/dependencies.py`, ex.: `SessionDep`),
  schemas Create/Update/Read separados, regras de cálculo em `services/` **puras** (sem I/O).
- Todo horário em `timestamptz` UTC; o "dia" é calculado no fuso IANA do usuário.
- IDs UUIDv7 gerados no cliente; soft delete com `excluido_em`; `versao` para controle otimista.
- Frontend: cores de categoria sempre por **token** (`ardosia`, `glicinia`, `salvia`, `ceu`,
  `manteiga`, `rosa-cha`, `pessego` × `50/200/700`), definidos em `app/assets/css/main.css`.
  Use classes completas e estáticas (o Tailwind não detecta classes montadas por string).
- Números de hora/duração com a utility `tabular`; durações no formato `3h 40min`.

## Decisões

- Recorrência: modelo semanal materializado em blocos por data (sem RRULE).
- Offline completo no MVP (Dexie + outbox + `/sync`).
- Execução: "Fiz como planejado" como ação principal + cronômetro opcional.
- TypeScript fixado em **^6** — typescript-eslint e vue-tsc ainda não suportam TS 7.

## Roadmap

F0 Setup inicial ✅ · F1 Auth ✅ · F2 Domínio API ✅ · F3 Shell + DS ✅ · F4 Timeline ✅ · F5 Execução ✅ ·
F6 Resumo ✅ · F7 PWA offline ✅ · F8 Lembretes push · F9 MVP

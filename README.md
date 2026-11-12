# Ritmo — Cronograma Inteligente de Rotina Pessoal

> Planeje sua rotina em blocos de tempo, acompanhe horas líquidas reais, meça a aderência ao planejado e receba lembretes via Web Push. PWA moderno e offline-first.

---

## 🌟 Recursos Principais

- **Time Blocking Visual**: timeline interativa de 24 horas com suporte a drag & drop (mouse e touch), pausas planejadas e categorização com paleta pastel suave.
- **Horas Líquidas & Aderência**: cálculo proporcional de pausas e fatiamento automático de blocos e execuções que cruzam a meia-noite no fuso IANA do usuário.
- **Execução Real**: registro via ação direta *"Fiz como planejado"* (1 toque) ou cronômetro em tempo real com controle de concorrência (`FOR UPDATE SKIP LOCKED`).
- **Resumo & Métricas**: indicadores de aderência volumétrica e temporal, comparativo planejado vs. executado e agregação de execuções espontâneas.
- **Offline-First Real (Dexie + Outbox)**: cache local de blocos, modelos, categorias e execuções, fila de mutações otimistas com reconciliação Last-Write-Wins (LWW) e endpoint de sincronização incremental (`/sync/mudancas`).
- **PWA & Web Push**: aplicação instalável (Service Worker com Workbox precache), ícones adaptativos maskable e notificações push via protocolo VAPID com worker despachante em segundo plano.

---

## 🏗️ Stack Tecnológica

| Camada | Tecnologias |
|---|---|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2 (asyncpg), Alembic, Pydantic v2, PyWebPush, argon2-cffi |
| **Frontend** | Nuxt 4 (SPA), Vue 3 (`<script setup>`), Pinia, Tailwind CSS v4, Dexie.js (IndexedDB), Vitest |
| **Banco de Dados** | PostgreSQL 16 (porta 5433 em desenvolvimento) |
| **Infraestrutura** | Docker & Docker Compose multi-stage com separação de API, Worker e Frontend Nginx |
| **Qualidade** | Ruff, Mypy (strict), Pytest (108 testes), ESLint, Nuxt Typecheck, Vitest (63 testes) |

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Docker e Docker Compose instalados
- [uv](https://docs.astral.sh/uv/) (Python 3.13)
- [pnpm](https://pnpm.io/) e Node.js 22+

### 2. Desenvolvimento Local

#### Configuração inicial
```bash
# Copia variáveis de ambiente de desenvolvimento
cp .env.example .env

# Instala dependências do backend e frontend
make install
```

#### Rodando com Docker (tudo em containers com hot-reload)
```bash
make run
```
- Frontend: `http://localhost:3000`
- API FastAPI: `http://localhost:8000` (docs em `http://localhost:8000/docs`)
- Healthcheck: `http://localhost:8000/saude`

#### Rodando localmente com banco no Docker
```bash
# 1. Sobe apenas o PostgreSQL na porta 5433
make db

# 2. Roda as migrações Alembic
make migrate

# 3. Em um terminal: roda a API FastAPI com reload
make run-api

# 4. Em outro terminal: roda o Nuxt dev
make run-front
```

---

## 🧪 Verificação e Qualidade

O projeto possui validação estrita em todas as camadas:

```bash
# Executa todos os linters, typechecks e testes de backend e frontend (o mesmo do CI)
make check
```

Comandos individuais:
```bash
make test        # Pytest (backend) + Vitest (frontend)
make lint        # Ruff check (backend) + ESLint (frontend)
make format      # Formatação automática de código
make typecheck   # Mypy strict (backend) + Nuxt typecheck (frontend)
make types       # Regenera tipos TypeScript a partir do OpenAPI da API
```

---

## 🚢 Ambiente de Produção

O projeto conta com arquitetura desacoplada para deploy em produção através do `docker-compose.prod.yml`:

```
┌────────────────────────────────────────────────────────┐
│                      Nginx / Caddy                     │
│                (Terminação TLS no Host)                │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       :8080    ▼               :8000    ▼
┌──────────────────────┐ ┌───────────────────────────────┐
│       frontend       │ │              api              │
│ (Nginx + SPA estático│ │      (FastAPI Uvicorn)        │
│    com PWA e cache)  │ └───────────────┬───────────────┘
└──────────────────────┘                 │
                                         │
┌──────────────────────┐                 │
│        worker        │                 │
│  (Despachador Push)  │                 │
└───────────────┬──────┘                 │
                │                        │
                ▼                        ▼
┌────────────────────────────────────────────────────────┐
│                        postgres                        │
│                 (PostgreSQL 16 interno)                │
└────────────────────────────────────────────────────────┘
```

Para subir em produção:
```bash
# Crie o arquivo .env.prod com senhas e chaves VAPID seguras
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

---

## 📖 Arquitetura e Decisões

Para convenções de código, regras de horas líquidas, design system e decisões de arquitetura detalhadas, consulte [CLAUDE.md](CLAUDE.md).

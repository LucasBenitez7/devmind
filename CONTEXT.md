# DevMind — Project Context

## What this is

B2B SaaS multi-tenant platform for dev teams. Companies upload their internal documentation (runbooks, ADRs, architecture docs, onboarding guides) and query it in natural language via an intelligent LangGraph agent.

The agent decides automatically which source to use:

- Internal docs (RAG with pgvector) → "¿Cómo deployamos el servicio de pagos?"
- Web search (Tavily) → "¿Hay CVEs conocidos en Redis 7.4?"
- Both combined → "¿Qué versión de Redis usamos y tiene vulnerabilidades?"

Responses stream token by token (SSE) with inline source citations [1][2] and a sources array at the end.

Portfolio project — demonstrates agentic RAG, LangGraph stateful graphs, multi-tenant architecture, async Python, Next.js 15.
URL: devmind.lsbstack.com

**Design docs:** `docs/API_DESIGN.md` (schemas), `docs/PHASES.md` (delivery checklist), `docs/TECHNICAL_DECISIONS.md` (limits, chunking, Redis keys, ER sketch).

## Stack

| Layer           | Technology                                             |
| --------------- | ------------------------------------------------------ |
| Language        | Python 3.12 + TypeScript 5.7                           |
| Package manager | uv (backend) · npm (frontend)                          |
| API             | FastAPI 0.115 (async)                                  |
| Validation      | Pydantic v2                                            |
| ORM             | SQLAlchemy 2.0 async                                   |
| Migrations      | Alembic                                                |
| Vector store    | pgvector 0.8 (PostgreSQL 16)                           |
| Cache / broker  | Redis 7.4                                              |
| Background jobs | Celery 5.4                                             |
| Agent           | LangGraph 0.2                                          |
| LLM             | claude-sonnet-4-5 via langchain-anthropic 0.3          |
| Embeddings      | text-embedding-3-small via langchain-openai 0.3        |
| Web search      | Tavily via tavily-python 0.5                           |
| Re-ranking      | Cohere rerank-english-v3.0 via cohere 5.x              |
| Auth            | Auth0 Organizations + JWT/JWKS · Auth0 Next.js SDK 3.x |
| Storage         | Cloudflare R2 (boto3)                                  |
| Frontend        | Next.js 15.2 · React 19 · Tailwind CSS 4 · shadcn/ui  |
| State           | Zustand 5 · TanStack Query 5                           |
| Streaming       | Native EventSource API (SSE) — no Vercel AI SDK        |
| Logging         | structlog (JSON)                                       |
| Linting         | Ruff · ESLint · Prettier                               |
| Type checking   | mypy strict · TypeScript strict                        |
| Testing         | pytest · pytest-asyncio · httpx · Vitest · Playwright  |
| CI/CD           | GitHub Actions → Railway (backend) + Vercel (frontend) |

## Architecture

Modular Monolith. Four infrastructure interfaces with swappable adapters: LLMProvider, VectorStore, SearchTool, StorageProvider.

```
backend/app/
├── modules/
│   ├── auth/             → JWT validation, Auth0 JWKS, permission decorators
│   ├── organizations/    → org CRUD, Auth0 Organizations, API keys
│   ├── users/            → profiles, invitations, roles
│   ├── documents/        → upload, chunking, embeddings, Celery processing
│   ├── conversations/    → history, messages, sources metadata
│   └── agent/            → LangGraph graph, nodes, tools, streaming
│       ├── graph.py      → StateGraph definition
│       ├── nodes.py      → route, rag_retrieval, web_search, rerank, generate
│       ├── tools.py      → RAGTool, TavilySearchTool
│       ├── state.py      → AgentState TypedDict
│       ├── prompts.py    → system prompts
│       └── streaming.py  → SSE handler
├── infrastructure/
│   ├── llm/              → LLMProvider Protocol + ClaudeAdapter
│   ├── vector_store/     → VectorStore Protocol + PgVectorAdapter
│   ├── search/           → SearchTool Protocol + TavilyAdapter
│   └── storage/          → StorageProvider Protocol + R2Adapter
└── core/
    ├── config.py         → pydantic-settings
    ├── database.py       → async engine, get_db
    ├── redis.py          → async Redis client (`from __future__ import annotations` + `Redis[Any]` for mypy; redis-py is not generic at runtime)
    ├── security.py       → JWT decode, org_id extraction
    ├── exceptions.py     → DevMindException hierarchy (N818 ignored — intentional base class naming)
    └── middleware.py     → request ID, logging context
```

## Roles (per organization)

owner → admin → member → viewer

| Action                  | owner | admin | member | viewer |
| ----------------------- | ----- | ----- | ------ | ------ |
| Chat with agent         | ✓     | ✓     | ✓      | ✓      |
| View documents          | ✓     | ✓     | ✓      | ✗      |
| Upload/delete documents | ✓     | ✓     | ✗      | ✗      |
| Manage members          | ✓     | ✓     | ✗      | ✗      |
| Create API keys         | ✓     | ✓     | ✗      | ✗      |
| Delete organization     | ✓     | ✗     | ✗      | ✗      |

## Critical decisions

- **Every query to document_chunks MUST include WHERE org_id = :org_id** — never omit this filter
- Auth0 manages all auth — we never store or handle passwords
- JWT from Auth0 contains: user_id, org_id, role — validated via JWKS
- API keys: never store original value, only bcrypt hash — shown once at creation
- Chunking: 512 tokens, overlap 50, RecursiveCharacterTextSplitter
- Re-ranking: always top-20 from pgvector → Cohere rerank → top-5 to LLM
- Embeddings: always batch (20 per call), always cache in Redis (TTL 24h, key = sha256(text))
- Conversation history: last 10 messages in every agent call; summarize if >8000 tokens
- Magic bytes validation on every upload — never trust file extension alone
- Presigned URLs for R2 (TTL 1h) — never expose direct R2 URLs
- python-jose instead of PyJWT — Auth0 uses RS256/JWKS, python-jose handles it natively
- Redis typing: `Redis[Any]` satisfies mypy (types-redis); postponed annotations avoid runtime `TypeError` because redis-py’s `Redis` is not a generic class at import time

## Known mypy / Ruff overrides (intentional)

```toml
# pyproject.toml — excerpt; full list in backend/pyproject.toml
[[tool.mypy.overrides]]
module = [
    "celery.*", "kombu.*", "slowapi.*", "jose.*", "filetype.*",
    "tavily.*", "cohere.*", "pgvector.*", "boto3.*", "botocore.*",
]
ignore_errors = true

[[tool.mypy.overrides]]
module = ["app.infrastructure.workers.*"]
ignore_errors = true

[tool.ruff.lint]
ignore = ["N818"]      # DevMindException base class — intentional naming
```

## Plans and limits

| Limit         | Free | Pro       |
| ------------- | ---- | --------- |
| Documents     | 10   | Unlimited |
| Max file size | 5 MB | 25 MB     |
| Queries/month | 100  | Unlimited |
| Team members  | 3    | Unlimited |
| API keys      | 1    | 10        |

## Development phases

- [ ] Phase 0 — Project setup (monorepo, Docker Compose, backend CI, pre-commit; ver checklist en `docs/PHASES.md`)
- [ ] Phase 1 — Auth & tenants (Auth0 Organizations, JWT, RBAC, auth UI)
- [ ] Phase 2 — Document ingestion (upload, chunking, embeddings, Celery, pgvector)
- [ ] Phase 3 — RAG core + re-ranking (VectorStore adapter, Cohere rerank)
- [ ] Phase 4 — Agent + web search + streaming + citations (LangGraph, Tavily, SSE)
- [ ] Phase 5 — Conversation memory (history, summarization)
- [ ] Phase 6 — Security hardening (rate limiting, API keys, audit log)
- [ ] Phase 7 — Full testing (coverage >80% backend, E2E critical flows)
- [ ] Phase 8 — Frontend polish (dashboard, chat UI, documents page, settings)
- [ ] Phase 9 — Deploy & launch (Railway + Vercel, CI/CD complete, README + demo GIF)

---

## Current status

**Current phase:** Phase 0 — cierre de setup (PR / validación); **siguiente:** Phase 1 — Auth & tenants

**Hecho en repo (backend, fase 0):**
- Monorepo con `backend/`, `docs/`, `infra/`; carpeta `frontend/` reservada (aún sin scaffold)
- FastAPI: `GET /health`, `GET /health/detailed` en la raíz (sin prefijo `/api/v1` hasta agrupar routers)
- Docker Compose dev: PostgreSQL 16 + pgvector + Redis 7.4 (`infra/docker-compose.dev.yml`)
- Alembic configurado; **pendiente:** primera revisión en `alembic/versions/`
- Ruff, mypy (strict), bandit; pre-commit (Ruff, mypy, bandit, conventional commits)
- GitHub Actions: `.github/workflows/backend.yml` (lint, typecheck, tests con Postgres + Redis de servicio)
- `backend/.env.example` alineado con variables documentadas

**Pendiente típico antes de dar Phase 0 por cerrada:** primera migración Alembic, scaffold frontend + ESLint/Prettier + `.env.local.example`, workflow CI frontend (ver `docs/PHASES.md`).

**Working on next:** Auth0 Organizations, JWT/JWKS middleware, RBAC, `GET /auth/me`, `GET /orgs/me`

**Known decisions:**
- Monorepo: `backend/` + `frontend/` en el mismo repo; CI backend con path filters; CI frontend cuando exista código en `frontend/`
- Deploy: Railway (backend + PostgreSQL + Redis addon) · Vercel (frontend)
- Storage: Cloudflare R2 (S3-compatible, no egress costs)
- No microservices — Modular Monolith, extract only if scale requires it
- Frontend strategy: back first, front only when UI is essential (Phase 1 needs auth UI, Phase 2 needs basic upload UI, rest is backend-only until Phase 8)
- Tests en CI usan la base `devmind_test` creada por el servicio Postgres del workflow; localmente hace falta crear esa DB si quieres correr los mismos tests contra Docker

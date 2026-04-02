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
| Frontend        | Next.js 15.2 · React 19 · Tailwind CSS 4 · shadcn/ui   |
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
    ├── redis.py          → async redis client
    ├── security.py       → JWT decode, org_id extraction
    ├── exceptions.py     → DevMindException hierarchy
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

## Plans and limits

| Limit         | Free | Pro       |
| ------------- | ---- | --------- |
| Documents     | 10   | Unlimited |
| Max file size | 5 MB | 25 MB     |
| Queries/month | 100  | Unlimited |
| Team members  | 3    | Unlimited |
| API keys      | 1    | 10        |

## Development phases

- [ ] Phase 0 — Project setup (monorepo, Docker Compose, CI, pre-commit, branch protection)
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

**Current phase:** Phase 0 — Project setup

**Completed:** —

**Working on now:** Monorepo initialization, Docker Compose dev, CI pipeline with path filters, pre-commit hooks, branch protection.

**Known decisions:**

- Monorepo: backend/ + frontend/ in same repo, CI uses path filters
- Deploy: Railway (backend + PostgreSQL + Redis addon) · Vercel (frontend)
- Storage: Cloudflare R2 (S3-compatible, no egress costs)
- No microservices — Modular Monolith, extract only if scale requires it
- Vertical phases — back + front together per phase

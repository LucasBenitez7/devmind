# DevMind API — Fases de Desarrollo

> Plan de 10 días. Fases verticales — backend + frontend juntos por feature.
> Cada fase tiene una rama dedicada y entregables verificables antes de mergear.

---

## FASE 0 — Project Setup
**Rama**: `feat/phase-0-project-setup`
**Días**: 0.5

**Objetivo**: el repositorio arranca limpio, CI verde, Docker funciona, health check responde.

### Entregables
- [ ] Monorepo creado con estructura completa de carpetas
- [ ] `docker-compose.dev.yml` levanta PostgreSQL 16 + pgvector + Redis 7.4
- [ ] `GET /health` responde `{"status": "ok", "version": "0.1.0"}`
- [ ] Alembic configurado con primera migración vacía aplicada
- [ ] Ruff + mypy configurados en `pyproject.toml`
- [ ] ESLint + Prettier configurados en frontend
- [ ] Pre-commit hooks activos (Ruff, mypy, conventional commits)
- [ ] `.env.example` documentado con todas las variables necesarias
- [ ] `.env.local.example` documentado para frontend
- [ ] CI backend verde: lint + type check + tests pasan
- [ ] CI frontend verde: lint + type check pasan (workflow en `.github/workflows/` cuando exista código en `frontend/`)
- [ ] Branch protection activa en `main` y `dev`
- [ ] `.releaserc.json` configurado

---

## FASE 1 — Auth + Tenants
**Rama**: `feat/phase-1-auth-tenants`
**Días**: 1

**Objetivo**: un usuario puede registrarse, crear una organización y hacer login. El sistema sabe quién es y a qué org pertenece en cada request.

### Entregables Backend
- [ ] Auth0 configurado con Organizations habilitado
- [ ] Middleware de autenticación JWT valida token Auth0 en cada request protegido
- [ ] Modelo `Organization` con campos: id, name, slug, auth0_org_id, plan, created_at
- [ ] Modelo `User` con campos: id, auth0_user_id, email, name, org_id, role, created_at
- [ ] `GET /auth/me` devuelve perfil del usuario autenticado
- [ ] `GET /orgs/me` devuelve organización del usuario
- [ ] Decorador `@require_role("admin")` funcional
- [ ] Tests de integración: token válido pasa, token expirado devuelve 401, rol insuficiente devuelve 403

### Entregables Frontend
- [ ] Auth0 SDK configurado con `app/api/auth/[auth0]/route.ts`
- [ ] Login y logout funcionan
- [ ] Middleware Next.js protege rutas `(app)/*`
- [ ] `useUser()` hook disponible en toda la app

---

## FASE 2 — Ingesta de Documentos
**Rama**: `feat/phase-2-document-ingestion`
**Días**: 2

**Objetivo**: un admin puede subir un documento (PDF, Markdown, TXT), el sistema lo procesa en background, lo divide en chunks, genera embeddings y los almacena en pgvector. El documento queda listo para ser consultado.

### Entregables Backend
- [ ] Modelo `Document`: id, org_id, uploaded_by, filename, file_type, file_size, storage_key, status (pending/processing/ready/error), chunk_count, created_at
- [ ] Modelo `DocumentChunk`: id, document_id, org_id, content, embedding vector(1536), chunk_index, metadata jsonb, created_at
- [ ] `POST /documents/upload` acepta multipart/form-data, valida por magic bytes (no solo extensión), sube a R2, crea registro con status=pending
- [ ] `GET /documents` lista documentos de la org con paginación
- [ ] `GET /documents/{id}` devuelve detalle + status
- [ ] `DELETE /documents/{id}` borra documento, chunks y archivo en R2
- [ ] Celery task `process_document`: descarga de R2, extrae texto (PDF/MD/TXT), chunking con overlap, batch embeddings OpenAI, inserta en pgvector, actualiza status=ready
- [ ] Chunking strategy: 512 tokens, 50 tokens de overlap, RecursiveCharacterTextSplitter
- [ ] Si el procesamiento falla → status=error con mensaje descriptivo
- [ ] Tests unitarios: chunking produce chunks del tamaño correcto, magic bytes rechaza archivos inválidos
- [ ] Tests de integración: upload → Celery task → chunks en DB

### Entregables Frontend
- [ ] Página `/documents` lista documentos con status badge (pending/processing/ready/error)
- [ ] Componente upload con drag & drop, validación de tipo y tamaño en cliente
- [ ] Polling del status cada 3s mientras status != ready
- [ ] Botón de borrar con confirmación

---

## FASE 3 — RAG Core + Re-ranking
**Rama**: `feat/phase-3-rag-core`
**Días**: 1.5

**Objetivo**: dado un query, el sistema recupera los chunks más relevantes de los documentos de la org, los re-rankea con Cohere y los devuelve listos para el LLM.

### Entregables Backend
- [ ] Interface `VectorStore` con métodos `similarity_search(query, org_id, k) → List[Chunk]`
- [ ] Adapter `PgVectorStore` implementa la interface, filtra siempre por `org_id` (nunca se mezclan orgs)
- [ ] Interface `SearchTool` con método `search(query) → List[SearchResult]`
- [ ] Adapter `TavilySearchTool` implementa la interface
- [ ] Interface `LLMProvider` con método `generate(messages, stream) → str | AsyncIterator`
- [ ] Adapter `ClaudeProvider` implementa la interface con `claude-sonnet-4-5`
- [ ] Re-ranking con Cohere `rerank-english-v3.0`: toma los top-20 chunks y devuelve los top-5 más relevantes
- [ ] Tests unitarios: mock VectorStore devuelve chunks correctos, re-ranking reordena por relevancia, filtro por org_id nunca se omite

---

## FASE 4 — Agente + Web Search + Streaming + Citas
**Rama**: `feat/phase-4-agent-streaming`
**Días**: 2

**Objetivo**: el agente decide solo qué fuente usar, genera la respuesta con streaming token a token y cita cada afirmación con su fuente (documento interno o URL web).

### Entregables Backend
- [ ] `AgentState` TypedDict con: query, org_id, conversation_history, retrieved_docs, web_results, final_answer, sources
- [ ] LangGraph `StateGraph` con nodos: `route` → `rag_retrieval` / `web_search` / `both` → `rerank` → `generate`
- [ ] Nodo `route`: clasifica el query en internal/web/both basándose en el contenido (palabras como "nuestro", "sistema", "deploy" → internal; versiones, CVEs, changelogs → web)
- [ ] Nodo `rag_retrieval`: usa PgVectorStore + re-ranking
- [ ] Nodo `web_search`: usa TavilySearchTool, devuelve resultados con URL y snippet
- [ ] Nodo `generate`: construye prompt con chunks/resultados, llama Claude con streaming
- [ ] Cada chunk y resultado web incluido en el prompt tiene un ID de cita `[1]`, `[2]`...
- [ ] La respuesta final incluye array `sources`: `[{id, type: "internal"|"web", title, url?}]`
- [ ] `POST /conversations/{id}/messages` es un SSE endpoint que emite eventos: `delta` (token), `sources` (al final), `done`
- [ ] `GET /conversations` lista conversaciones de la org
- [ ] `POST /conversations` crea conversación vacía
- [ ] `GET /conversations/{id}` devuelve conversación con todos los mensajes
- [ ] Tests unitarios: nodo route clasifica correctamente queries de prueba, SSE emite eventos en orden correcto
- [ ] Tests de integración: POST mensaje → SSE stream completo → mensaje guardado en DB con sources

### Entregables Frontend
- [ ] Página `/chat` con sidebar de conversaciones + área de chat principal
- [ ] Input de query con submit por Enter
- [ ] Streaming: los tokens aparecen en tiempo real con `EventSource`
- [ ] Al terminar el stream, aparecen las fuentes citadas debajo de la respuesta
- [ ] Badge visible `[Docs internos]` o `[Web search]` o `[Ambos]` según qué fuente usó el agente

---

## FASE 5 — Memoria Conversacional
**Rama**: `feat/phase-5-conversation-memory`
**Días**: 0.5

**Objetivo**: el agente recuerda el hilo de la conversación. "¿Y cómo se hace en nuestro sistema?" funciona después de una pregunta anterior.

### Entregables Backend
- [ ] Los últimos N mensajes de la conversación se incluyen en el contexto del agente (default: últimos 10 mensajes)
- [ ] Si el historial supera 8000 tokens, se aplica summarización del historial antiguo
- [ ] `AgentState` incluye `conversation_history: List[BaseMessage]`
- [ ] Tests: query de seguimiento con historial devuelve respuesta coherente con el contexto anterior

---

## FASE 6 — Security Hardening
**Rama**: `security/phase-6-hardening`
**Días**: 0.5

**Objetivo**: la API es segura contra abuso y los errores nunca exponen información técnica.

### Entregables
- [ ] Rate limiting con `slowapi`: 60 req/min por usuario, 10 req/min en endpoints de chat
- [ ] API keys para acceso programático: `POST /api-keys`, `DELETE /api-keys/{id}`, almacenadas hasheadas con bcrypt
- [ ] Autenticación doble: JWT Auth0 (dashboard) o API key (integraciones)
- [ ] Todos los errores del servidor devuelven mensajes en lenguaje humano (ver TECHNICAL_DECISIONS.md)
- [ ] Magic bytes validation activo (ya desde Fase 2, verificar que está en todos los endpoints de upload)
- [ ] Request ID en cada response (`X-Request-ID` header) para trazabilidad
- [ ] Audit log: cada acción sensible (upload, delete, invite, api-key-created) queda registrada en DB

---

## FASE 7 — Testing Completo
**Rama**: `test/phase-7-coverage`
**Días**: 0.5

**Objetivo**: cobertura >= 80% en módulos core, todos los flujos E2E pasan.

### Entregables
- [ ] Tests unitarios completos para: chunking, re-ranking, nodo route del agente, validación de magic bytes
- [ ] Tests de integración completos para todos los endpoints de la API
- [ ] 5 flujos E2E implementados y pasando (checklist a definir en el PR de esta fase o en README)
- [ ] Coverage report en CI — falla si coverage < 80% en módulos core
- [ ] `make test` corre todo el suite en local

---

## FASE 8 — Frontend Polish
**Rama**: `feat/phase-8-frontend`
**Días**: 1

**Objetivo**: el dashboard es funcional, limpio y deja una buena impresión en portfolio.

### Entregables
- [ ] Landing page (`/`) con descripción del producto, CTA de signup
- [ ] Dashboard (`/dashboard`): métricas — documentos indexados, queries este mes, última actividad
- [ ] Página de Settings: miembros del equipo (invite/remove), API keys (crear/revocar), perfil
- [ ] Estados de carga correctos en todos los componentes (skeletons, no spinners genéricos)
- [ ] Estados de error correctos — mensaje humano, botón de retry donde aplica
- [ ] Responsive — funciona bien en mobile (aunque el uso real es desktop)
- [ ] Dark mode

---

## FASE 9 — Deploy + CI/CD + Polish Final
**Rama**: `feat/phase-9-deploy`
**Días**: 0.5

**Objetivo**: la app está desplegada, el CI/CD está completo y el README es impecable.

### Entregables
- [ ] Backend desplegado en Railway con PostgreSQL + Redis addons
- [ ] Frontend desplegado en Vercel
- [ ] Variables de entorno configuradas en ambos servicios
- [ ] GitHub Actions: backend CI (lint + test + deploy a Railway), frontend CI (lint + test + deploy a Vercel)
- [ ] Smoke test post-deploy: `GET /health` responde 200 antes de marcar deploy como exitoso
- [ ] semantic-release configurado — primer release manual `v0.1.0`
- [ ] README.md con: descripción, arquitectura diagram (Mermaid), stack badge, instrucciones de setup local, demo GIF del agente respondiendo con streaming y citas
- [ ] Swagger UI accesible en `/docs` con todos los endpoints documentados

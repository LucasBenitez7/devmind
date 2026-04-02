# DevMind API — Technical Decisions

> Decisiones técnicas detalladas. Cada decisión incluye el "por qué" además del "qué".
> Este documento es la referencia cuando haya duda en la implementación.

---

## 1. Planes y Límites

| Límite | Free | Pro |
|---|---|---|
| Documentos indexados | 10 | Ilimitado |
| Tamaño máximo por documento | 5 MB | 25 MB |
| Queries al agente por mes | 100 | Ilimitado |
| Miembros del equipo | 3 | Ilimitado |
| Retención de historial | 30 días | 1 año |
| API keys | 1 | 10 |
| Formatos soportados | PDF, MD, TXT | PDF, MD, TXT |

**Razón**: los límites del free tier son suficientes para probar el producto pero motivan el upgrade. Documentos y queries son los vectores de coste real (embeddings + LLM).

---

## 2. Tokens y Contexto del LLM

| Parámetro | Valor | Razón |
|---|---|---|
| Modelo | claude-sonnet-4-5 | Balance calidad/coste, streaming nativo |
| Max tokens respuesta | 2048 | Suficiente para respuestas técnicas detalladas |
| Chunks recuperados antes de rerank | 20 | Balance recall/latencia |
| Chunks enviados al LLM después de rerank | 5 | Top-5 es suficiente, no abrumar el contexto |
| Mensajes de historial incluidos | 10 últimos | ~4000 tokens de historial |
| Umbral de summarización del historial | 8000 tokens | Si se supera, summarizar mensajes antiguos |
| Temperatura | 0.1 | Respuestas técnicas deben ser deterministas |

### Qué se registra en DB por cada query

- `tokens_used` (input + output)
- `latency_ms` (tiempo desde query hasta primer token)
- `source_used` ("internal" | "web" | "both")
- `sources` (array JSON con title, url, tipo)

---

## 3. Chunking Strategy

| Parámetro | Valor | Razón |
|---|---|---|
| Chunk size | 512 tokens | Granularidad suficiente para recuperación precisa |
| Chunk overlap | 50 tokens | Evita perder contexto en los bordes del chunk |
| Splitter | RecursiveCharacterTextSplitter | Respeta estructura del texto (párrafos, saltos de línea) |
| Metadata por chunk | document_id, org_id, chunk_index, filename, file_type | Necesario para construir las citas de fuente |

**Por qué 512 tokens y no 1024**: chunks más pequeños dan mayor precisión en la recuperación. Con re-ranking, 512 tokens permite recuperar párrafos específicos en lugar de secciones enteras.

---

## 4. Almacenamiento de Documentos

| Parámetro | Decisión |
|---|---|
| Provider | Cloudflare R2 |
| Estructura de keys | `{org_id}/{document_id}/{filename}` |
| URLs | Presigned URLs con TTL de 1 hora (nunca URLs directas permanentes) |
| Validación de tipo | Magic bytes (primeros bytes del archivo), NO solo extensión |
| Tipos permitidos | PDF (25 50 44 46), MD/TXT (UTF-8 text) |
| Qué se guarda en DB | Solo la key de R2, no la URL (la URL se genera on-demand) |

**Magic bytes para validación:**
- PDF: primeros 4 bytes = `25 50 44 46` (%PDF)
- Markdown/TXT: decodificable como UTF-8 válido

**Por qué presigned URLs**: las URLs directas de R2 son permanentes. Un presigned URL expira, lo que significa que aunque alguien obtenga la URL de la DB no puede acceder al archivo después de 1 hora.

---

## 5. Cache (Redis)

| Clave | TTL | Cuándo se invalida |
|---|---|---|
| `embeddings:{hash_del_query}` | 24 horas | Nunca (deterministas) |
| `org:{org_id}:plan` | 1 hora | Al cambiar el plan |
| `org:{org_id}:usage:{mes}` | Hasta fin de mes | Al incrementar uso |
| `conversation:{id}:history` | 30 minutos | Al añadir mensaje nuevo |

**Por qué cachear embeddings del query**: generar un embedding cuesta ~0.0001 USD pero tarda 100-200ms. El mismo query repetido (muy común en un equipo) se sirve en <5ms desde cache.

---

## 6. Jobs en Background (Celery)

| Task | Trigger | Qué hace |
|---|---|---|
| `process_document` | Upload de documento | Descarga R2, extrae texto, chunking, embeddings batch, inserta pgvector, actualiza status |
| `delete_document_chunks` | Borrado de documento | Borra chunks de pgvector (puede tardar si hay muchos) |
| `cleanup_expired_conversations` | Diario 03:00 UTC | Borra conversaciones más antiguas que el límite del plan |
| `summarize_long_conversation` | Al superar 8000 tokens de historial | Resume mensajes antiguos, guarda resumen en DB |

**Por qué Celery para process_document**: el procesamiento de un PDF de 5MB puede tardar 10-30 segundos (extracción + N llamadas a OpenAI embeddings). Bloquear el request HTTP durante ese tiempo es inaceptable.

---

## 7. Mensajes de Error para el Usuario

**Regla**: nunca stack traces, nunca nombres de tablas, nunca mensajes técnicos.

| Situación | Mensaje al usuario |
|---|---|
| Token expirado / no autenticado | "Tu sesión ha expirado. Por favor inicia sesión de nuevo." |
| Sin permisos (403) | "No tienes permisos para realizar esta acción. Contacta al administrador de tu organización." |
| Documento no encontrado | "Este documento no existe o fue eliminado." |
| Tipo de archivo no permitido | "Solo se permiten archivos PDF, Markdown y TXT." |
| Archivo demasiado grande | "El archivo supera el límite de {X} MB. Comprime el documento o actualiza tu plan." |
| Límite de queries alcanzado | "Has alcanzado el límite de {100} queries este mes. Actualiza a Pro para continuar." |
| Error procesando documento | "No pudimos procesar este documento. Verifica que el archivo no esté dañado e inténtalo de nuevo." |
| Error del agente | "Hubo un problema al procesar tu consulta. Inténtalo de nuevo en unos segundos." |
| Error genérico 500 | "Algo salió mal de nuestro lado. Ya fuimos notificados. Inténtalo de nuevo en unos minutos." |
| Sin conexión (frontend) | "Parece que no tienes conexión a internet. Verifica tu red e inténtalo de nuevo." |

---

## 8. Monitorización

### Métricas críticas (alerta inmediata)

| Métrica | Umbral | Acción |
|---|---|---|
| Error rate API | > 5% en 5 min | Alerta Slack inmediata |
| Latencia p95 del agente | > 30s | Alerta Slack inmediata |
| Celery queue size | > 100 tasks | Alerta Slack inmediata |
| DB connections | > 80% del pool | Alerta Slack inmediata |

### Métricas de revisión diaria

- Queries totales por org
- Documentos procesados con error
- Tokens consumidos (coste estimado)
- Latencia media del agente por source_used

### Sentry

- Todos los errores 500
- Excepciones no manejadas en Celery tasks
- Timeouts del LLM (> 60s)

### Health checks

- `GET /health` — respuesta ligera; en el arranque de la app se verifican conexión a DB y Redis (lifespan)
- `GET /health/detailed` — incluye: latencia DB, latencia Redis, y si la extensión pgvector está activa en PostgreSQL (implementación actual). Comprobación de workers Celery: pendiente cuando encaje con el despliegue

---

## 9. Diagrama Entidad-Relación

```
organizations
  │  id, name, slug, auth0_org_id, plan, created_at
  │
  ├──< users (org_id → organizations.id RESTRICT)
  │     id, auth0_user_id, email, name, org_id, role, created_at
  │
  ├──< api_keys (org_id → organizations.id CASCADE)
  │     id, org_id, name, key_hash, last_used_at, created_at, expires_at
  │
  ├──< documents (org_id → organizations.id RESTRICT)
  │     id, org_id, uploaded_by, filename, file_type, file_size,
  │     storage_key, status, chunk_count, error_message, created_at
  │     │
  │     └──< document_chunks (document_id → documents.id CASCADE)
  │           id, document_id, org_id, content, embedding vector(1536),
  │           chunk_index, metadata jsonb, created_at
  │
  └──< conversations (org_id → organizations.id RESTRICT)
        id, org_id, user_id, title, created_at, updated_at
        │
        └──< messages (conversation_id → conversations.id CASCADE)
              id, conversation_id, role (user|assistant), content,
              sources jsonb, tokens_used, latency_ms, source_used, created_at
```

### Índices necesarios

```sql
-- Búsqueda vectorial por org (la query más frecuente)
CREATE INDEX idx_chunks_embedding ON document_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_org_id ON document_chunks (org_id);

-- Filtros frecuentes
CREATE INDEX idx_documents_org_id ON documents (org_id);
CREATE INDEX idx_documents_status ON documents (status);
CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_conversations_org_id ON conversations (org_id, updated_at DESC);
CREATE INDEX idx_api_keys_key_hash ON api_keys (key_hash);
```

**Comportamiento al borrar:**
- Borrar `organization` → RESTRICT (debe borrar users, docs, convs primero — evita borrado accidental)
- Borrar `document` → CASCADE en `document_chunks` (los chunks no tienen valor sin el documento)
- Borrar `conversation` → CASCADE en `messages`
- Borrar `user` → SET NULL en `documents.uploaded_by` (el documento sigue existiendo)

---

## 10. Backups

| Escenario | Frecuencia | Retención | Proceso de recuperación |
|---|---|---|---|
| PostgreSQL full dump | Diario 02:00 UTC | 7 días | Railway restore desde snapshot |
| Archivos en R2 | Continuo (R2 tiene 11 nines durabilidad) | Ilimitado | Restaurar key desde backup de DB |
| Peor caso: pérdida de embeddings | — | — | Re-procesar todos los documentos (están en R2) |

**Dato clave**: los embeddings en pgvector son regenerables. Si se pierden los vectores pero los documentos originales están en R2, el sistema se puede reconstruir ejecutando `process_document` para cada documento. El tiempo de recuperación depende del número de documentos.

---

## 11. Variables de Entorno

### Backend (.env.example)

```bash
# App
ENVIRONMENT=development
SECRET_KEY=changeme-in-production
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/devmind

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.devmind.app
AUTH0_CLIENT_ID=your-client-id

# LLM
ANTHROPIC_API_KEY=sk-ant-...

# Embeddings
OPENAI_API_KEY=sk-...

# Web Search
TAVILY_API_KEY=tvly-...

# Re-ranking
COHERE_API_KEY=...

# Storage
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=devmind-docs

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Sentry (opcional en dev)
SENTRY_DSN=
```

### Frontend (.env.local.example)

```bash
# Auth0
AUTH0_SECRET=changeme-in-production
AUTH0_BASE_URL=http://localhost:3000
AUTH0_ISSUER_BASE_URL=https://your-tenant.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret

# API
NEXT_PUBLIC_API_URL=http://localhost:8000
```

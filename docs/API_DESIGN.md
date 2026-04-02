# DevMind API — API Design

> Todos los endpoints con request/response schemas completos.
> Base URL objetivo: `/api/v1` (las rutas de dominio se montarán bajo este prefijo al agrupar routers).
> **Fase 0:** `GET /health` y `GET /health/detailed` están en la raíz (`/health`, `/health/detailed`), sin prefijo.
> Autenticación: Bearer JWT (Auth0) o X-API-Key header
> Todos los responses de error siguen el schema: `{"error": "mensaje humano", "code": "ERROR_CODE"}`

---

## Health

### GET /health
Estado del servicio.

**Response 200**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### GET /health/detailed
Estado detallado con latencias de dependencias y comprobación de la extensión pgvector.

**Seguridad (objetivo):** restringir en producción (p. ej. API key interna o red privada). En fase 0 el endpoint es público como el health básico.

**Response 200**
```json
{
  "status": "ok",
  "db_latency_ms": 3,
  "redis_latency_ms": 1,
  "pgvector_active": true
}
```

**Futuro:** se puede añadir comprobación de workers Celery (`celery_workers`) cuando el broker esté integrado en el health check.

---

## Auth

### GET /auth/me
Perfil del usuario autenticado.

**Response 200**
```json
{
  "id": "uuid",
  "email": "dev@company.com",
  "name": "Lucas Benitez",
  "role": "admin",
  "org_id": "uuid",
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Errores**
- 401 — Token inválido o expirado

---

## Organizations

### GET /orgs/me
Organización del usuario autenticado.

**Response 200**
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "free",
  "usage": {
    "documents": 3,
    "documents_limit": 10,
    "queries_this_month": 45,
    "queries_limit": 100
  },
  "created_at": "2025-01-01T00:00:00Z"
}
```

### PATCH /orgs/me
Actualizar nombre de la organización. Requiere rol `owner`.

**Request**
```json
{
  "name": "Nuevo Nombre"
}
```

**Response 200** — Mismo schema que GET /orgs/me

**Errores**
- 403 — Solo el owner puede actualizar la org

---

## Users

### GET /users
Lista miembros de la organización. Requiere rol `admin`.

**Query params**: `page=1&limit=20`

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "dev@company.com",
      "name": "Dev Name",
      "role": "member",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 20
}
```

### POST /users/invite
Invitar un nuevo miembro. Requiere rol `admin`.

**Request**
```json
{
  "email": "newdev@company.com",
  "role": "member"
}
```

**Response 201**
```json
{
  "message": "Invitación enviada a newdev@company.com"
}
```

**Errores**
- 400 — Email ya es miembro de la org
- 403 — Sin permisos
- 422 — Email inválido
- 429 — Límite de miembros del plan alcanzado

### PATCH /users/{user_id}/role
Cambiar rol de un miembro. Requiere rol `admin`.

**Request**
```json
{
  "role": "admin"
}
```

**Response 200** — Schema del user actualizado

**Errores**
- 400 — No se puede cambiar el rol del owner
- 403 — Sin permisos
- 404 — Usuario no encontrado en la org

### DELETE /users/{user_id}
Eliminar miembro de la org. Requiere rol `admin`.

**Response 204** — Sin body

**Errores**
- 400 — No se puede eliminar al owner
- 403 — Sin permisos
- 404 — Usuario no encontrado

---

## Documents

### GET /documents
Lista documentos de la organización.

**Query params**: `page=1&limit=20&status=ready`

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "filename": "arquitectura-sistema.pdf",
      "file_type": "pdf",
      "file_size": 245000,
      "status": "ready",
      "chunk_count": 48,
      "uploaded_by": {
        "id": "uuid",
        "name": "Lucas Benitez"
      },
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "limit": 20
}
```

### POST /documents/upload
Subir un nuevo documento. Requiere rol `admin`. Content-Type: multipart/form-data.

**Request**
```
file: <binary>       ← PDF, MD o TXT, máx 5MB (free) / 25MB (pro)
```

**Response 202** — Aceptado, procesamiento en background
```json
{
  "id": "uuid",
  "filename": "runbook-deploy.md",
  "status": "pending",
  "message": "Tu documento está siendo procesado. Estará listo en unos segundos."
}
```

**Errores**
- 400 — Tipo de archivo no permitido
- 413 — Archivo demasiado grande para el plan
- 429 — Límite de documentos del plan alcanzado

### GET /documents/{id}
Detalle de un documento con estado de procesamiento.

**Response 200**
```json
{
  "id": "uuid",
  "filename": "runbook-deploy.md",
  "file_type": "md",
  "file_size": 12000,
  "status": "ready",
  "chunk_count": 12,
  "error_message": null,
  "uploaded_by": {
    "id": "uuid",
    "name": "Lucas Benitez"
  },
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Errores**
- 404 — Documento no encontrado

### DELETE /documents/{id}
Borra documento, chunks y archivo de R2. Requiere rol `admin`.

**Response 204** — Sin body

**Errores**
- 403 — Sin permisos
- 404 — Documento no encontrado

---

## Conversations

### GET /conversations
Lista conversaciones del usuario autenticado.

**Query params**: `page=1&limit=20`

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "¿Cómo deployamos el servicio de pagos?",
      "message_count": 6,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T01:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "limit": 20
}
```

### POST /conversations
Crear nueva conversación vacía.

**Request**
```json
{}
```

**Response 201**
```json
{
  "id": "uuid",
  "title": null,
  "messages": [],
  "created_at": "2025-01-01T00:00:00Z"
}
```

### GET /conversations/{id}
Conversación completa con todos sus mensajes.

**Response 200**
```json
{
  "id": "uuid",
  "title": "¿Cómo deployamos el servicio de pagos?",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "¿Cómo deployamos el servicio de pagos?",
      "sources": null,
      "created_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Para deployar el servicio de pagos, sigue estos pasos [1]...",
      "sources": [
        {
          "id": 1,
          "type": "internal",
          "title": "runbook-deploy.md",
          "document_id": "uuid"
        }
      ],
      "source_used": "internal",
      "tokens_used": 856,
      "latency_ms": 1240,
      "created_at": "2025-01-01T00:00:01Z"
    }
  ],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:01Z"
}
```

**Errores**
- 404 — Conversación no encontrada o no pertenece al usuario

### DELETE /conversations/{id}
Borrar conversación y todos sus mensajes.

**Response 204** — Sin body

---

## Agent — Chat (SSE Streaming)

### POST /conversations/{id}/messages
Enviar un mensaje y recibir respuesta del agente via Server-Sent Events.

**Request** (Content-Type: application/json)
```json
{
  "content": "¿Hay algún bug conocido en la versión de Redis que usamos?"
}
```

**Response 200** (Content-Type: text/event-stream)

El stream emite eventos en este orden:

```
event: delta
data: {"token": "Según"}

event: delta
data: {"token": " la"}

event: delta
data: {"token": " documentación"}

... (un evento por token)

event: source_decision
data: {"source_used": "both"}

event: sources
data: {
  "sources": [
    {"id": 1, "type": "internal", "title": "redis-config.md", "document_id": "uuid"},
    {"id": 2, "type": "web", "title": "Redis 7.4 Release Notes", "url": "https://redis.io/..."}
  ]
}

event: done
data: {"message_id": "uuid", "tokens_used": 412, "latency_ms": 2100}
```

**Errores** (devueltos como evento SSE antes de cerrar el stream)
```
event: error
data: {"error": "Hubo un problema al procesar tu consulta. Inténtalo de nuevo.", "code": "AGENT_ERROR"}
```

- 404 — Conversación no encontrada
- 429 — Límite de queries del plan alcanzado

---

## API Keys

### GET /api-keys
Lista API keys de la organización. Requiere rol `admin`.

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "CI/CD Pipeline",
      "key_prefix": "dm_live_abc1",
      "last_used_at": "2025-01-01T00:00:00Z",
      "created_at": "2025-01-01T00:00:00Z",
      "expires_at": null
    }
  ]
}
```

**Nota**: el valor completo de la key solo se devuelve en el momento de creación. Después solo se muestra el prefijo.

### POST /api-keys
Crear nueva API key. Requiere rol `admin`.

**Request**
```json
{
  "name": "CI/CD Pipeline",
  "expires_at": null
}
```

**Response 201**
```json
{
  "id": "uuid",
  "name": "CI/CD Pipeline",
  "key": "dm_live_abc123xyz...",
  "message": "Guarda esta key ahora. No podrás verla de nuevo."
}
```

**Errores**
- 429 — Límite de API keys del plan alcanzado

### DELETE /api-keys/{id}
Revocar una API key. Requiere rol `admin`.

**Response 204** — Sin body

**Errores**
- 404 — API key no encontrada

---

## Tabla Resumen de Endpoints

| Método | Endpoint | Auth | Rol mínimo |
|---|---|---|---|
| GET | /health | No | — |
| GET | /health/detailed | No (fase 0); restringir en prod. | — |
| GET | /auth/me | Sí | viewer |
| GET | /orgs/me | Sí | viewer |
| PATCH | /orgs/me | Sí | owner |
| GET | /users | Sí | admin |
| POST | /users/invite | Sí | admin |
| PATCH | /users/{id}/role | Sí | admin |
| DELETE | /users/{id} | Sí | admin |
| GET | /documents | Sí | member |
| POST | /documents/upload | Sí | admin |
| GET | /documents/{id} | Sí | member |
| DELETE | /documents/{id} | Sí | admin |
| GET | /conversations | Sí | viewer |
| POST | /conversations | Sí | viewer |
| GET | /conversations/{id} | Sí | viewer |
| DELETE | /conversations/{id} | Sí | viewer |
| POST | /conversations/{id}/messages | Sí | viewer |
| GET | /api-keys | Sí | admin |
| POST | /api-keys | Sí | admin |
| DELETE | /api-keys/{id} | Sí | admin |

# Deployment

## What runs

| Service | Image | Host port | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | `POSTGRES_PORT` (5432) | PostgreSQL with pgvector. Health check: `pg_isready` |
| `redis` | `redis:7-alpine` | `REDIS_PORT` (6379) | Rate limiting. The production file requires a password and persists to disk |
| `backend` | built from `backend/Dockerfile` (Python 3.11-slim, non-root user) | `BACKEND_PORT` (8000) | Runs `alembic upgrade head`, then Uvicorn. Health check: `GET /health` every 30 s |
| `frontend` | built from `frontend/Dockerfile` (Next.js standalone) | `FRONTEND_PORT` (3000) | `NEXT_PUBLIC_API_URL` is baked in at build time |

Two switches in the backend entrypoint:

| Variable | Default | What it does |
|---|---|---|
| `RUN_MIGRATIONS` | `true` | Run `alembic upgrade head` at start. Set `false` on all but one replica, or run migrations as a release step |
| `FORWARDED_ALLOW_IPS` | `*` | Which proxies Uvicorn trusts for `X-Forwarded-*`. **Set it to your proxy's address in production** |

`docker-compose.prod.yml` differs from the development file: it sets `ENVIRONMENT=production`, `DEBUG=false`, `DEMO_MODE=false` and `AUTO_CREATE_TABLES=false`, **refuses to start unless** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PASSWORD`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` are set, only exposes the backend inside the network (put TLS and a reverse proxy in front), and installs the optional provider packages by default (`INSTALL_OPTIONAL=true`).

## Local Docker stack

1. Copy `.env.example` to `.env` and set a unique `JWT_SECRET`.
2. Set `POSTGRES_PASSWORD` and update `DATABASE_URL` if needed.
3. Start the stack:

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before starting Uvicorn. The Compose file
waits for PostgreSQL and Redis health checks. `AUTO_CREATE_TABLES` is disabled in Compose;
migrations are the schema authority.

For a local API-only run:

```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
python ../database/seed/seed.py  # optional synthetic demo data
uvicorn app.main:app --reload
```

## Retrieval engine and optional tools

- The default `RAG_ENGINE=local` needs no provider keys. Set `RAG_ENGINE=external` plus
  `LLM_API_KEY` / `EMBEDDING_API_KEY` to use Groq and Gemini.
- Photo import of lab reports needs `tesseract` on the backend host (`apt install tesseract-ocr`).
- Load the real knowledge with `python scripts/ingest_real_knowledge.py` and
  `python scripts/build_book_index.py`, then approve documents in *Admin → Documents*.
- The frontend ships its own Docker image; see [`frontend/README.md`](../frontend/README.md).

## Production checklist

- Use `docker-compose.prod.yml` or an orchestrator with secret management.
- Set a unique `JWT_SECRET` of at least 32 characters.
- Set `ENVIRONMENT=production`, `DEBUG=false`, and `DEMO_MODE=false`.
- Use a managed PostgreSQL/pgvector instance, encrypted backups, and a private Redis network.
- Run migrations as a controlled release step, not concurrently from every replica.
- Put the API behind TLS and a reverse proxy/load balancer.
- Configure exact `CORS_ORIGINS`; do not use `*` with credentials.
- Set `INSTALL_OPTIONAL=true` at build time if the deployment needs Groq/Gemini/Redis client packages; the default image stays smaller and uses the safe grounded fallback when providers are unavailable.
- Keep provider keys in a secret manager; never expose them through frontend environment variables.
- Restrict `/admin`, `/evaluation`, and `/internal/metrics` at the network and authorization layers.
- Run backend tests, Ruff, secret scan, and safety evaluation before release.
- Establish a clinical source-review owner and guideline renewal schedule.

## Health and observability

`GET /health` checks application/database availability. Staff can inspect
`GET /internal/metrics`; metrics contain route counts and latency aggregates, not raw health
queries. Every response includes a request ID for correlation.

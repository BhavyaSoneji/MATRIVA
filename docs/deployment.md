# Deployment

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

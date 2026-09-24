# MATRIVA Frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS frontend for MATRIVA, a pregnancy-guidance
web app that combines modern medical evidence with traditional/Ayurvedic knowledge behind a safety-first
chat and recommendation experience.

## Development

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL to your backend
npm run dev
```

Useful scripts: `npm run build`, `npm run lint`, `npm run typecheck`, `npm run test:e2e`.

## Environment variables

- `NEXT_PUBLIC_API_URL` — base URL of the MATRIVA backend API (default `http://localhost:8000`).

## Deployment

The app builds to a Next.js "standalone" output and ships with a multi-stage `Dockerfile`.

### Build and run with Docker directly

```bash
docker build -t matriva-frontend --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.example.com matriva-frontend
```

This has been verified locally: `docker build` succeeds, the container starts, and it serves HTTP 200 on `/`.

### Via docker-compose (recommended for local/full-stack runs)

From the repository root:

```bash
docker compose up --build frontend
```

The `frontend` service in `docker-compose.yml` builds this directory, passes `NEXT_PUBLIC_API_URL` as both
a build arg and a runtime env var, waits for the `backend` service to be healthy, and publishes the app on
`FRONTEND_PORT` (default `3000`).

### Deploying to a hosting platform

Any platform that can run a Docker image or a Node.js server works:

- **Container platforms** (Fly.io, Render, Railway, AWS ECS/Fargate, Google Cloud Run): point them at the
  `Dockerfile` in this directory and set `NEXT_PUBLIC_API_URL` to your deployed backend's public URL as a
  build arg (it is inlined into the client bundle at build time) and/or runtime env var.
- **Vercel**: Vercel builds this Next.js app directly without the Dockerfile; set `NEXT_PUBLIC_API_URL` as a
  project environment variable.

Actual provisioning of cloud infrastructure (DNS, TLS, hosting account setup) is a manual/ops step outside
this repository's automation and is not performed by this repo's tooling.

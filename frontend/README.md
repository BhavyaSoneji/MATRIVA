# MATRIVA Frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS frontend for MATRIVA, an evidence-first pregnancy
companion that combines modern medical guidance with traditional/Ayurvedic knowledge behind a safety-first
chat. The product is **one chat workspace** (slash commands such as `/plan`, `/checkin`, `/check`, `/readings`,
`/meals`, `/summary`, `/book`, `/map`) plus landing, signup/login, onboarding, settings and admin pages.

## Development

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL to your backend
npm run dev
```

Useful scripts: `npm run build`, `npm run lint`, `npm run typecheck`, `npm run test:e2e` (Playwright, mocked API, 9 tests).

## Layout

- `app/` — routes: `chat` (the companion), `onboarding`, `settings`, `login`, `signup`, `admin/*`
- `components/care/` — plan, check-in, readings, meals, summary and safety-check widgets
- `components/` — chat answer, book and map widgets, voice, retrieval trace, resource cards
- `lib/` — API client and helpers; `tests/e2e/` — Playwright specs

> This project uses a recent Next.js with breaking changes; see `AGENTS.md` before writing code.

## Add a card to the chat

Features are slash commands that open a card inside the conversation, not pages.

1. Write the component in `components/care/` (or `components/`). Wrap it in `Frame` and use `Chip` for choices.
2. Add its type to `WidgetSpec` in `components/chat-widgets.tsx` (care cards use `CareAction` in `components/care/plan-widget.tsx`) and a `case` in the `ChatWidget` switch.
3. Add an entry to `QUICK_ACTIONS` in `app/chat/page.tsx`: `id`, `label`, `command` (the slash command), `icon`, `hint`, and `widget`.
4. Add the response types to `lib/care-types.ts`, and call the API with `api.get` from `lib/api.ts`.
5. Add a Playwright spec that mocks the endpoint (see `tests/e2e/care.spec.ts`).

## Tests

`npx playwright test` runs the specs in `tests/e2e/` against a production build, with the API mocked by `page.route`. They test the interface and its contract with the backend, not the backend. Playwright starts `npm run build && npm run start` on port 3000 and **reuses any server already listening there**: stop a stale dev server first, or you will test old code.

## Environment variables

- `NEXT_PUBLIC_API_URL` — base URL of the MATRIVA backend API (default `http://localhost:8000`; the README's local `uvicorn` example runs on `8010`, so set it in `.env.local`).

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

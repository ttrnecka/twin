# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An "AI Digital Twin" — a chatbot that impersonates the repo owner on their website. Two independent deployables:

- `backend/` — FastAPI app, served locally with uvicorn or wrapped by Mangum for AWS Lambda + API Gateway.
- `frontend/` — Next.js 16 / React 19 single-page chat UI.

The two are wired together by the hardcoded API URL in `frontend/components/twin.tsx` (the `fetch()` call to API Gateway). When changing the deployed endpoint, update that string — there is no env-var indirection on the frontend.

## Backend

### Layout & data flow

- `server.py` is the FastAPI app. Endpoints: `GET /`, `GET /health`, `POST /chat`, `GET /conversation/{session_id}`.
- `resources.py` reads the persona files **once at import time** from `backend/data/`: `facts.json`, `summary.txt`, `style.txt`, `linkedin.pdf`. Changing those files requires a server restart (and a re-deploy for Lambda). `linkedin.pdf` is parsed with `pypdf`; missing file is handled, missing `.txt`/`.json` will crash on startup.
- `context.py` builds the system prompt from the resources. The prompt is regenerated per-request (so `datetime.now()` is fresh) but the underlying persona data is the cached module-level state from `resources.py`.
- `lambda_handler.py` is a 3-line Mangum adapter — the Lambda entrypoint is `lambda_handler.handler`.

### Conversation memory

`POST /chat` persists conversation history per `session_id` as `{session_id}.json`. Storage backend is chosen at request time by env vars:

- `USE_S3=true` → writes to `S3_BUCKET` via boto3. `s3_client` is created at module import only if `USE_S3` is true.
- otherwise → writes to local dir `MEMORY_DIR` (default `../memory`).

Only the last 10 messages are sent to OpenAI per request (see the `conversation[-10:]` slice in `server.py`).

### Running locally

```bash
cd backend
uv sync                              # install deps (uv.lock is the source of truth)
cp .env.example .env                 # then fill in OPENAI_API_KEY
uv run python server.py              # serves on 0.0.0.0:8000
```

Required/used env vars: `OPENAI_API_KEY`, `CORS_ORIGINS` (comma-separated), `USE_S3`, `S3_BUCKET`, `MEMORY_DIR`.

### Deploying to Lambda

`deploy.py` builds `lambda-deployment.zip` by `pip install`-ing into `lambda-package/` inside the official `public.ecr.aws/lambda/python:3.12` Docker image (forced `linux/amd64`, `manylinux2014_x86_64` wheels only). Docker must be running. It copies `server.py`, `lambda_handler.py`, `context.py`, `resources.py`, and the `data/` directory.

```bash
cd backend
uv run python deploy.py              # produces lambda-deployment.zip
aws lambda update-function-code \
    --function-name twin-api \
    --zip-file fileb://lambda-deployment.zip \
    --region us-east-1
```

Two parallel dependency files exist: `pyproject.toml` (used by `uv` for local dev) and `requirements.txt` (used by `deploy.py` inside the Lambda Docker image). Keep them in sync when adding deps.

### Deploying frontend to Cloudfront

```
cd frontend
npm run build
aws s3 sync out/ s3://twin-frontend-tt2026 --delete
```
Create invalidation in CF gui

## Frontend

### Critical: this is Next.js 16, not earlier versions

`frontend/AGENTS.md` (referenced from `frontend/CLAUDE.md`) explicitly warns: APIs, conventions, and file structure differ from older Next.js. **Read the relevant guide in `node_modules/next/dist/docs/` before writing Next.js code.** Heed deprecation notices.

Other version notes:
- React 19, Tailwind CSS v4 (note the `@tailwindcss/postcss` plugin in `postcss.config.mjs`, not the v3 config style).
- `npm run dev` runs `next dev -H 127.0.0.1 --webpack --port 3000` — the `--webpack` flag opts out of Next 16's default Turbopack. `build` also uses `--webpack`. Don't drop that flag without checking the implications.

### Commands

```bash
cd frontend
npm install
npm run dev      # http://127.0.0.1:3000
npm run build
npm run lint     # eslint via flat config (eslint.config.mjs)
```

There is no test runner configured for the frontend.

### Structure

App Router only — `app/layout.tsx`, `app/page.tsx`, `app/globals.css`. The chat UI is a single client component, `components/twin.tsx`, imported as `@/components/twin` (path alias from `tsconfig.json`).

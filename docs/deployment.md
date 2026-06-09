# CuratorML deployment guide

This document focuses on running CuratorML locally or on a single self-hosted machine.

## Deployment model

CuratorML uses a split deployment:

- Docker Compose runs PostgreSQL, the FastAPI backend, and the frontend
- a host Python process runs ML inference
- an optional OpenAI-compatible provider handles translation and embeddings

That split is the recommended way to run the project today.

## What runs in Docker

The Compose stack contains:

- PostgreSQL/pgvector
- backend API
- frontend web app

The frontend is published on port `8081` by default.

## What runs on the host

The inference service runs outside Docker and listens on port `8001` by default.

The host path is used because model/runtime dependencies are easier to manage there, and because the backend only needs a simple HTTP target.

## Quick deployment steps

### 1. Prepare the environment file

```bash
cp .env.example .env
```

Edit `.env` and set a strong database password.

### 2. Download model files

```bash
bash scripts/download-models.sh
```

This downloads:

- the default YOLO segmentation weights from Hugging Face
- the OCR assets used by the backend/inference workflow

### 3. Start the inference service

```bash
bash scripts/start-inference.sh
```

Health check:

```text
http://localhost:8001/health
```

### 4. Start Docker Compose

```bash
docker compose build
docker compose up -d
```

### 5. Verify the stack

```bash
docker compose ps
curl -f http://localhost:8081/health
curl -f http://localhost:8081/api/v1/projects
curl -f http://localhost:8001/health
```

## Docker Model Runner

If you want local translation support on Docker Desktop, use Docker Model Runner.

From inside the backend container, the recommended endpoint is:

```text
http://model-runner.docker.internal/engines/v1
```

From the host, the usual endpoint is:

```text
http://localhost:12434/engines/v1
```

Set `TRANSLATION_MODEL` and, if needed, `TRANSLATION_MEMORY_EMBEDDING_MODEL` to actual model IDs you pulled in Docker.

## Production-style single-machine deployment

For a cleaner public deployment:

- keep the inference service private
- put a reverse proxy in front of the frontend/backend entrypoint
- terminate TLS at the proxy
- keep `.env` out of Git
- keep model weights out of Git
- use persistent volumes for database and app storage

## Reverse proxy example

A simple Caddy config could look like this:

```caddyfile
curator.example.com {
    reverse_proxy 127.0.0.1:8081
}
```

If you want to proxy the backend separately, expose the backend port only locally and route through the frontend or your own gateway.

## Common failure modes

### Docker daemon is not running

Start Docker Desktop or the Docker service and rerun the setup.

### Inference health check fails

Check:

- the model file exists at `backend/app/services/ml/best.pt`
- the inference port is free
- `scripts/start-inference.sh` is still running

### Docker backend cannot reach the host inference service

Use the Docker Desktop host alias:

```text
http://host.docker.internal:8001
```

On Linux, you may need host-gateway support or a different reachable address.

### Translation is unavailable

Check that your OpenAI-compatible base URL and model IDs are correct.

## Operational reminder

The repository is source-only.

Do not commit:

- `.env`
- uploaded images
- model weights
- generated artifacts
- database files

Use the download scripts and host runtime instead.

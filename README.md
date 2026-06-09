# CuratorML

CuratorML is a local-first manga translation workspace for turning scanned manga pages into editable translation projects. It combines a React editor, a FastAPI backend, PostgreSQL/pgvector storage, local OCR, YOLO segmentation-assisted masking, OpenCV-based cleanup/inpainting, translation memory, and PSD/image export workflows.

The project is built for supervised manga translation: a human translator stays in control while ML tools handle repetitive page preparation tasks such as region detection, OCR, reading-order support, mask cleanup, translation suggestions, and export packaging.

## What it does

- Creates manga translation projects and chapters.
- Uploads page images into a persistent project workspace.
- Detects manga page regions with a YOLO segmentation model.
- Runs OCR through a local Manga OCR ONNX model.
- Supports reading-order and text-region workflows.
- Cleans masked text areas with traditional/OpenCV cleanup and inpainting for editing.
- Stores translation memory for consistency across pages.
- Streams long-running job progress from the backend to the UI.
- Exports edited results and layered PSD artifacts for downstream editing.
- Runs the web app locally with Docker Compose, with an optional host-side ML inference service for auto-detection.

## Tech stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Zustand, React Query
- Backend: FastAPI, SQLAlchemy async, Alembic, Pydantic, Uvicorn
- Database: PostgreSQL with pgvector
- ML/OCR: YOLO segmentation model, manga-ocr-2025 ONNX assets, OpenCV, ONNX Runtime
- Translation gateway: optional OpenAI-compatible endpoint; Docker Model Runner is supported
- Deployment: Docker Compose for the web stack, local Python service for ML inference

## Repository layout

```text
.
├── backend/                 # FastAPI API, services, models, migrations, tests
├── frontend/                # React/Vite user interface
├── scripts/                 # setup, model download, and inference startup scripts
├── docker-compose.yml       # PostgreSQL, backend, and frontend services
├── .env.example             # safe local configuration template
└── README.md
```

## Requirements

- Docker and Docker Compose
- Python 3.10+ for the host ML inference service
- curl
- Node.js 20+ if running the frontend outside Docker
- Optional OpenAI-compatible LLM endpoint if using translation features, such as Docker Model Runner on Docker Desktop

On macOS, Docker Desktop is the easiest way to run the containerized services.

## Runtime pieces

CuratorML has three separable runtime pieces:

1. **Docker Compose app stack**: PostgreSQL/pgvector, the FastAPI backend, and the React frontend. This can run without model weights for project management and non-ML workflows.
2. **Host inference service**: a separate Python service at `http://localhost:8001` for YOLO page-region segmentation. The Docker backend calls it through `INFERENCE_REMOTE_URL`. OCR uses the downloaded Manga OCR ONNX assets from the backend runtime.
3. **Optional local LLM translation provider**: any OpenAI-compatible chat/embedding endpoint. Docker Desktop Model Runner is the documented easy option for Docker users; other local providers remain configurable.

Inpainting/text cleanup is traditional OpenCV/mask-region processing. There are no separate learned cleanup weights; the downloadable `.pt` file is only the YOLO segmentation model.

## Quick start

For the containerized web app only (PostgreSQL, backend API, and frontend):

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

This path does not require host Python ML dependencies or model weights. The UI,
API health check, project endpoints, and non-ML workflows can run this way. ML
auto-detection/mask inference requires the host inference service described
below.

For full ML-assisted auto-detection, also prepare model files and start the host
inference API:

```bash
bash scripts/download-models.sh
bash scripts/start-inference.sh
```

The repository does not include model weights. `scripts/download-models.sh`
fetches the default YOLO segmentation weights from Hugging Face repo
`ShadowB/Manga109-panel-balloon-text-yolov26-segmentation` (`best.pt`) and stores
it at `backend/app/services/ml/best.pt`, then downloads OCR assets. Override the
YOLO source with `YOLO_MODEL_URL=<direct-url>` if needed; `INPAINT_MODEL_URL` is
accepted only as a deprecated alias.

The one-command setup remains available:

```bash
bash scripts/setup.sh
```

It creates `.env`, checks/downloads models, starts inference, builds/starts the
Docker Compose stack, and opens the frontend on macOS. If the YOLO model asset is
not reachable, it stops with the same actionable instructions shown by
`scripts/download-models.sh`.

After startup:

- Frontend: `http://localhost:8081`
- Backend health: `http://localhost:8081/health` through the web stack, backend internally on port `8000`
- Inference health, when enabled: `http://localhost:8001/health`
- API projects endpoint: `http://localhost:8081/api/v1/projects`

## Manual local setup

If you do not want to use the setup script, run the web stack manually:

```bash
cp .env.example .env
```

Before starting Docker Compose, edit `.env` if needed and keep `DATABASE_URL` aligned with `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`; `docker-compose.yml` passes `DATABASE_URL` directly to the backend.

```bash
docker compose build
docker compose up -d
```

To enable ML auto-detection, prepare the model files and start inference in a
separate terminal:

```bash
bash scripts/download-models.sh
bash scripts/start-inference.sh
```

Check service status:

```bash
docker compose ps
curl http://localhost:8081/health
```

If inference is enabled:

```bash
curl http://localhost:8001/health
```

View logs:

```bash
docker compose logs -f
```

Stop the stack:

```bash
docker compose down
```

Stop and remove local database/storage volumes:

```bash
docker compose down -v
```

## Deployment

CuratorML is currently packaged as a self-hosted Docker Compose deployment. The default deployment target is a single machine where Docker runs PostgreSQL, the backend API, and the frontend. The ML inference service runs separately on the host when auto-detection is enabled.

### 1. Prepare the server

Install the required system tools:

```bash
sudo apt-get update
sudo apt-get install -y git curl python3 python3-venv docker.io docker-compose-plugin
```

Enable Docker:

```bash
sudo systemctl enable --now docker
```

Clone the repository:

```bash
git clone https://github.com/sadowb/CuratorML.git
cd CuratorML
```

Create the environment file:

```bash
cp .env.example .env
```

Edit `.env` before exposing the app publicly:

```bash
nano .env
```

At minimum, set a strong `POSTGRES_PASSWORD` and make sure `DATABASE_URL` matches it. The template derives `DATABASE_URL` from the `POSTGRES_*` values for Docker Compose; if you replace it with a literal value, keep it in sync:

```env
POSTGRES_DB=manga_db
POSTGRES_USER=manga
POSTGRES_PASSWORD=replace-with-a-strong-password
DATABASE_URL=postgresql+asyncpg://manga:replace-with-a-strong-password@db:5432/manga_db
```

Translation is optional. `.env.example` defaults to Docker Desktop Model Runner as seen from the backend container:

```env
TRANSLATION_PROVIDER_MODE=compatible_local
TRANSLATION_BASE_URL=http://model-runner.docker.internal/engines/v1
TRANSLATION_MODEL=<docker-model-id>
TRANSLATION_MEMORY_EMBEDDING_BASE_URL=http://model-runner.docker.internal/engines/v1
TRANSLATION_MEMORY_EMBEDDING_MODEL=<embedding-model-id-if-used>
LLM_INFERENCE_BASE_URL=http://model-runner.docker.internal/engines/v1
```

Enable Docker Model Runner in Docker Desktop, pull a chat model, and set `TRANSLATION_MODEL` to the model ID reported by Docker (for example, from `docker model ls`). If using translation-memory embeddings, also configure an OpenAI-compatible embedding model with `TRANSLATION_MEMORY_EMBEDDING_MODEL`. From the host, Docker Model Runner is commonly reachable at `http://localhost:12434/engines/v1`; containers should use `http://model-runner.docker.internal/engines/v1`.

For another OpenAI-compatible provider, replace those base URLs, for example:

```env
TRANSLATION_BASE_URL=http://host.docker.internal:8033/v1
TRANSLATION_MEMORY_EMBEDDING_BASE_URL=http://host.docker.internal:8033/v1
LLM_INFERENCE_BASE_URL=http://host.docker.internal:8033/v1
TRANSLATION_API_KEY=replace-if-required
TRANSLATION_MEMORY_EMBEDDING_API_KEY=replace-if-required
LLM_INFERENCE_API_KEY=replace-if-required
```

Do not commit `.env`.

### 2. Prepare model files for ML auto-detection

The Docker web stack can run before this step. Complete it when you want YOLO
region detection/OCR-driven ML workflows.

```bash
bash scripts/download-models.sh
```

The repository intentionally does not track model weights. The script downloads
YOLO segmentation weights first; once they are available, it downloads Manga OCR
ONNX/tokenizer files into `backend/models/manga-ocr-2025-onnx/`.

Default YOLO source:

```text
https://huggingface.co/ShadowB/Manga109-panel-balloon-text-yolov26-segmentation/resolve/main/best.pt?download=1
```

The Hugging Face repo also contains `last.pt`, but CuratorML defaults to
`best.pt`. The script stores it at:

```text
backend/app/services/ml/best.pt
```

To host weights elsewhere, use the primary override:

```bash
YOLO_MODEL_URL="https://example.com/direct/best.pt" bash scripts/download-models.sh
```

`INPAINT_MODEL_URL` is still accepted as a deprecated alias for existing setups,
but the file is used only for YOLO segmentation. Inpainting cleanup is
traditional OpenCV/mask processing and does not require learned cleanup weights.
Existing local installs with the legacy filename
`backend/app/services/ml/final_best_with_split_logic.pt` remain supported.

### 3. Start the inference service

Run the ML inference API on the host when ML auto-detection is enabled. By default it binds to `127.0.0.1:8001` and runs without reload mode:

```bash
bash scripts/start-inference.sh
```

It serves:

```text
http://localhost:8001/health
http://localhost:8001/infer/mask_inference
```

If the Docker backend cannot reach the host inference service through `host.docker.internal`, Docker Desktop for Mac or Linux host-gateway setups may require binding the inference server to a reachable interface:

```bash
INFERENCE_HOST=0.0.0.0 INFERENCE_PORT=8001 bash scripts/start-inference.sh
```

Only do this on trusted/private networks or with firewall rules in place. Public servers should keep port `8001` private and expose only the frontend/reverse proxy. For development hot reload, opt in explicitly with `INFERENCE_RELOAD=true`.

For a persistent server deployment, run it under systemd, tmux, or a process manager. Example systemd unit:

```ini
[Unit]
Description=CuratorML inference service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/CuratorML
ExecStart=/bin/bash /opt/CuratorML/scripts/start-inference.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4. Build and start the web stack

```bash
docker compose build
docker compose up -d
```

The frontend is published on:

```text
http://localhost:8081
```

For production behind a domain, put Nginx/Caddy/Traefik in front of port `8081` and terminate TLS there.

Example Caddy reverse proxy:

```caddyfile
curator.example.com {
    reverse_proxy 127.0.0.1:8081
}
```

### 5. Verify deployment

```bash
docker compose ps
curl -f http://localhost:8081/health
curl -f http://localhost:8081
```

If inference is enabled, also check:

```bash
curl -f http://localhost:8001/health
```

Expected results:

- PostgreSQL service is healthy.
- Backend service is healthy.
- Frontend responds on port `8081`.
- Inference service returns `{"status":"ok"}` when enabled.

### 6. Update deployment

```bash
git pull
docker compose build
docker compose up -d
```

If database migrations are required, run Alembic from the backend container or a backend environment configured with the same `DATABASE_URL`.

## Development

Backend development:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
npm ci
uvicorn app.main:app --reload
```

`npm ci` in `backend/` installs the Node-side PSD writer dependencies used by layered PSD export.

Frontend development:

```bash
cd frontend
npm install
npm run dev
```

Default Vite dev server:

```text
http://localhost:5173
```

## Tests and quality checks

Backend tests:

```bash
cd backend
pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

Frontend lint:

```bash
cd frontend
npm run lint
```

Docker build check:

```bash
docker compose build
```

## Configuration

Important environment variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL connection string used by FastAPI |
| `POSTGRES_DB` | PostgreSQL database name used by Docker Compose |
| `POSTGRES_USER` | PostgreSQL user used by Docker Compose |
| `POSTGRES_PASSWORD` | PostgreSQL password used by Docker Compose |
| `STORAGE_ROOT` | Backend file storage path |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `INFERENCE_MODE` | `remote` for host inference service, `local` for in-process inference |
| `INFERENCE_REMOTE_URL` | URL of the inference service, default `http://host.docker.internal:8001` in Docker |
| `INFERENCE_HOST` | Host interface used by `scripts/start-inference.sh`; defaults to `127.0.0.1` |
| `INFERENCE_PORT` | Port used by `scripts/start-inference.sh`; defaults to `8001` |
| `INFERENCE_RELOAD` | Opt-in reload mode for `scripts/start-inference.sh`; defaults to `false` |
| `YOLO_MODEL_PATH` | Local YOLO weights path used by the inference service; defaults to `backend/app/services/ml/best.pt` |
| `YOLO_MODEL_URL` | Optional direct URL for `scripts/download-models.sh` to fetch YOLO segmentation weights |
| `INPAINT_MODEL_URL` | Deprecated alias for `YOLO_MODEL_URL`; retained for existing setup scripts only |
| `YOLO_DEVICE` | YOLO execution device: `auto`, `cpu`, `cuda`, or `mps`; `auto` lets Ultralytics choose |
| `TRANSLATION_PROVIDER_MODE` | `compatible_local` or `openai_official` |
| `TRANSLATION_BASE_URL` | OpenAI-compatible chat/completions base URL; Docker Model Runner from containers uses `http://model-runner.docker.internal/engines/v1` |
| `TRANSLATION_MODEL` | Chat model ID to request from the configured provider |
| `TRANSLATION_API_KEY` | API key if the configured chat provider requires one |
| `TRANSLATION_MEMORY_EMBEDDING_BASE_URL` | OpenAI-compatible embeddings base URL |
| `TRANSLATION_MEMORY_EMBEDDING_MODEL` | Embedding model ID to request from the configured provider |
| `TRANSLATION_MEMORY_EMBEDDING_API_KEY` | API key if the embedding provider requires one |
| `LLM_INFERENCE_BASE_URL` | Compatibility local LLM endpoint; keep aligned with the OpenAI-compatible provider when used |
| `LLM_INFERENCE_API_KEY` | API key if the configured LLM endpoint requires one |

## Data and model policy

This repository should stay source-only:

- Do not commit `.env` files.
- Do not commit database files or uploaded manga pages.
- Do not commit model weights.
- Do not commit copyrighted Manga109 images or validation batches.
- Use `scripts/download-models.sh`, Hugging Face, or your own direct download URL for large model artifacts.

The `.gitignore` is configured to keep runtime storage, database files, local secrets, generated artifacts, and ML weights out of Git.

## Current status

CuratorML is an MVP research/product prototype. It is suitable for local demos, portfolio review, and controlled self-hosted testing. Before a public production deployment, review authentication, rate limiting, storage quotas, model licensing, and access control for uploaded page images.

## License

See `LICENSE`.

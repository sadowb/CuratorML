# CuratorML architecture

This document explains how CuratorML is split across the frontend, backend, database, inference service, and optional local LLM provider.

## High-level layout

```text
Browser
  ↓
React/Vite frontend
  ↓
FastAPI backend
  ├─ PostgreSQL + pgvector
  ├─ project/page/job APIs
  ├─ translation memory
  └─ remote inference dispatch
        ↓
Host Python inference service
  ├─ YOLO segmentation
  ├─ OCR asset loading
  └─ mask/page analysis

Optional:
FastAPI backend → OpenAI-compatible local/remote LLM provider
```

## Why the ML stack is split

CuratorML uses a hybrid setup on purpose:

- the web app is containerized because it is easy to deploy and share
- the heavier ML inference code stays on the host because model/runtime dependencies are easier to manage there
- the LLM provider is optional and can be local or remote, as long as it speaks an OpenAI-compatible API

This keeps the app usable for normal project management even when the ML pieces are unavailable.

## Frontend responsibilities

The frontend is a React/Vite app that handles:

- project navigation
- page upload and project views
- editor interactions
- displaying progress for long-running jobs
- surfacing backend responses and validation errors

## Backend responsibilities

The backend is a FastAPI application that handles:

- authentication/authorization plumbing if enabled in the current deployment
- project, chapter, page, and job APIs
- database persistence
- translation memory and retrieval
- routing requests to inference services
- export orchestration
- application health checks

## Database responsibilities

PostgreSQL stores:

- project metadata
- page metadata
- job records
- translation memory
- vector embeddings when enabled

`pgvector` is used so the backend can perform similarity-based memory retrieval.

## Inference service responsibilities

The host Python inference service is responsible for the expensive ML path:

- loading the YOLO segmentation model
- using local OCR assets
- creating masks or detection metadata for page regions
- exposing a small HTTP API that the backend can call

The default inference health endpoint is:

```text
http://localhost:8001/health
```

The inference endpoint used in the current workflow is:

```text
http://localhost:8001/infer/mask_inference
```

## Model strategy

CuratorML intentionally keeps the model weights outside Git:

- YOLO segmentation weights are downloaded from Hugging Face
- OCR assets are downloaded separately
- the Docker web stack does not need to bake model weights into its images

The default YOLO model file is:

```text
backend/app/services/ml/best.pt
```

The legacy filename `final_best_with_split_logic.pt` is still supported for existing installs.

## Cleanup / inpainting strategy

The cleanup step is traditional image processing, not a separate learned inpainting model.

That means:

- masks come from detection/region logic
- cleanup uses OpenCV and related mask processing
- the UI and docs should not describe the `.pt` file as an inpainting model

## Translation strategy

Translation is optional and uses an OpenAI-compatible API shape.

Supported uses:

- chat-completions style calls
- embedding-style calls for translation memory

The most convenient local option is Docker Desktop Model Runner, but the backend can target any compatible provider.

## Runtime flow

1. A user uploads or opens a page.
2. The backend stores the page and metadata.
3. The editor requests detection or job execution.
4. The backend forwards the ML request to the host inference service when `INFERENCE_MODE=remote`.
5. The inference service returns detections or masks.
6. The backend combines those results with OCR, memory, and export workflows.
7. The frontend renders the response and keeps the user in control.

## Deployment model

CuratorML is intentionally split into two operational units:

- Docker Compose for the web application
- host service for ML inference

This avoids forcing all heavy model dependencies into the container image and makes local debugging easier.

## Design tradeoffs

The current design chooses practicality over maximal container purity:

- easier to reproduce the web stack
- easier to debug YOLO/OCR runtime issues
- easier to swap translation providers
- slightly more setup work for ML-assisted workflows

That is the tradeoff the current repository is optimized for.

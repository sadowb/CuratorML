from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.schemas.mask_inference import DetectionOut, MaskInferenceResponse
from app.services.ml.yolo_inference_service import run_inference

app = FastAPI(title="Manga Inference Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ZERO_UUID = uuid.UUID(int=0)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/infer/mask_inference", response_model=MaskInferenceResponse)
async def infer_mask(image: UploadFile = File(...)) -> MaskInferenceResponse:
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")

    tmp_dir = settings.storage_root_path / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(image.filename or "upload.png").name
    tmp_path = tmp_dir / f"inference-{uuid.uuid4().hex}-{safe_name}"
    tmp_path.write_bytes(data)

    try:
        detections = run_inference(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    return MaskInferenceResponse(
        pipeline_run_id=ZERO_UUID,
        page_id=ZERO_UUID,
        stage="mask_inference",
        detections=[DetectionOut.model_validate(item) for item in detections],
    )

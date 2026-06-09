from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_YOLO_MODEL_PATH = Path("backend/app/services/ml/best.pt")
LEGACY_YOLO_MODEL_PATH = Path("backend/app/services/ml/final_best_with_split_logic.pt")


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/manga_db"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    storage_root: Path = Path("./storage")
    max_upload_size_mb: int = 25
    sql_echo: bool = False
    # YOLO segmentation model configuration
    yolo_model_path: Path = DEFAULT_YOLO_MODEL_PATH
    yolo_confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    yolo_iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    yolo_inference_size: int = Field(default=1216, ge=64)
    yolo_max_detections: int = Field(default=120, ge=1)
    yolo_device: str = "auto"

    # Text handling
    text_use_detection_box: bool = True
    text_box_padding_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    text_box_min_padding_px: int = Field(default=0, ge=0)

    # Balloon repair
    balloon_repair_enabled: bool = True
    balloon_match_text_boxes: bool = True
    balloon_box_match_expand_ratio: float = Field(default=0.05, ge=0.0, le=1.0)

    # Dedicated morphology libraries
    balloon_use_scipy_fill_holes: bool = True
    balloon_use_skimage_diameter_closing: bool = True
    balloon_use_skimage_remove_small_holes: bool = True
    balloon_use_skimage_remove_small_objects: bool = True

    # Balloon morphology tuning
    balloon_close_ratio: float = Field(default=0.015, ge=0.0, le=1.0)
    balloon_close_min_px: int = Field(default=2, ge=0)
    balloon_close_max_px: int = Field(default=7, ge=0)
    balloon_text_box_dilation_px: int = Field(default=1, ge=0)

    balloon_remove_small_holes_max_size: int = Field(default=64, ge=0)
    balloon_remove_small_objects_max_size: int = Field(default=0, ge=0)

    # Repair guards
    balloon_max_area_growth_ratio: float = Field(default=1.6, gt=0.0)
    balloon_min_repaired_area_ratio: float = Field(default=0.6, gt=0.0)
    balloon_polygon_approx_eps_ratio: float = Field(default=0.002, ge=0.0, le=1.0)

    # Inpaint mask shaping
    inpaint_ai_expand_base_ratio: float = Field(default=0.01, ge=0.0, le=0.2)
    inpaint_ai_expand_strength_ratio: float = Field(default=0.03, ge=0.0, le=0.4)
    inpaint_ai_expand_min_px: int = Field(default=0, ge=0)
    inpaint_ai_expand_max_px: int = Field(default=40, ge=0)
    inpaint_balloon_inset_ratio: float = Field(default=0.03, ge=0.0, le=0.5)
    inpaint_balloon_inset_min_px: int = Field(default=1, ge=0)
    inpaint_balloon_inset_max_px: int = Field(default=12, ge=0)
    inpaint_balloon_clean_close_min_px: int = Field(default=1, ge=0)
    inpaint_balloon_clean_close_max_px: int = Field(default=5, ge=0)
    inpaint_balloon_clip_min_coverage_ratio: float = Field(default=0.45, ge=0.0, le=1.0)

    # MLX VLM (translation context extraction on Apple Silicon)
    mlx_vlm_model_path: str = ""
    mlx_vlm_timeout_seconds: int = 300
    mlx_vlm_max_tokens: int = 650

    # Inference dispatch
    inference_mode: str = "local"  # "local" or "remote"
    inference_remote_url: str = "http://localhost:8001"
    inference_timeout_seconds: int = 120

    # Phase 2 grounding helper artifact behavior
    grounding_helper_persist_debug: bool = False
    grounding_helper_image_format: str = "png"

    # Phase 3 translation provider
    translation_provider_mode: str = "compatible_local"  # or "openai_official"
    translation_base_url: str = ""
    translation_base_urls: list[str] | str = []
    translation_api_key: SecretStr | None = None
    translation_model: str = "local-model"
    translation_timeout_seconds: int = 120
    translation_local_timeout_seconds: int = 1800
    translation_max_output_tokens: int | None = Field(default=None, ge=128, le=8192)
    translation_max_lines_per_call: int = Field(default=8, ge=1, le=64)
    translation_max_retries: int = 2
    translation_log_stream_chunks: bool = False
    translation_log_raw_output_on_parse_error: bool = True

    # Translator memory retrieval
    translation_memory_embedding_base_url: str = ""
    translation_memory_embedding_api_key: SecretStr | None = None
    translation_memory_embedding_model: str = "local-embedding-model"
    translation_memory_embedding_dimensions: int = Field(default=1024, ge=1)
    translation_memory_top_k_exact: int = Field(default=20, ge=1, le=100)
    translation_memory_top_k_fts: int = Field(default=20, ge=1, le=100)
    translation_memory_top_k_vector: int = Field(default=10, ge=1, le=100)
    translation_memory_max_hard_rules: int = Field(default=12, ge=1, le=50)
    translation_memory_max_soft_notes: int = Field(default=8, ge=1, le=50)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise ValueError("Invalid CORS_ORIGINS format")

    @field_validator("yolo_device", mode="before")
    @classmethod
    def normalize_yolo_device(cls, value: str | None) -> str:
        device = "auto" if value is None else str(value).strip().lower()
        if not device:
            device = "auto"
        if device not in {"auto", "cpu", "cuda", "mps"}:
            raise ValueError("YOLO_DEVICE must be one of: auto, cpu, cuda, mps")
        return device

    @field_validator("translation_base_urls", mode="before")
    @classmethod
    def parse_translation_base_urls(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise ValueError("Invalid TRANSLATION_BASE_URLS format")

    @property
    def storage_root_path(self) -> Path:
        if self.storage_root.is_absolute():
            return self.storage_root
        return (BACKEND_DIR / self.storage_root).resolve()

    @property
    def yolo_model_path_resolved(self) -> Path:
        if self.yolo_model_path.is_absolute():
            return self.yolo_model_path

        candidate_paths = [
            self.yolo_model_path,
            BACKEND_DIR / self.yolo_model_path,
            BACKEND_DIR.parent / self.yolo_model_path,
        ]

        for path in candidate_paths:
            if path.exists():
                return path.resolve()

        if self.yolo_model_path == DEFAULT_YOLO_MODEL_PATH:
            legacy_candidate_paths = [
                LEGACY_YOLO_MODEL_PATH,
                BACKEND_DIR / LEGACY_YOLO_MODEL_PATH,
                BACKEND_DIR.parent / LEGACY_YOLO_MODEL_PATH,
            ]
            for path in legacy_candidate_paths:
                if path.exists():
                    return path.resolve()

        return (BACKEND_DIR / self.yolo_model_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

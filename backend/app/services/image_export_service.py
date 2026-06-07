from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page_file import PageFile
from app.repositories.page_repository import PageRepository
from app.services.psd_export.assembler import PsdExportAssembler
from app.services.psd_export.asset_resolver import PsdExportAssetResolver
from app.services.psd_export.models import PageExportOptions
from app.services.response_mapper import build_page_file_url
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path


class ImageExportService:
    def __init__(
        self,
        *,
        page_repo: PageRepository | None = None,
        assembler: PsdExportAssembler | None = None,
        asset_resolver: PsdExportAssetResolver | None = None,
    ) -> None:
        self.page_repo = page_repo or PageRepository()
        self.assembler = assembler or PsdExportAssembler(page_repo=self.page_repo)
        self.asset_resolver = asset_resolver or PsdExportAssetResolver()

    async def export_page(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        *,
        format: str,
    ) -> tuple[str, str, str]:
        normalized = format.strip().lower()
        if normalized not in {"png", "jpg", "jpeg", "webp", "pdf"}:
            raise ValueError("Unsupported format. Use one of: png, jpg, jpeg, webp, pdf")

        options = PageExportOptions(include_merged_preview=True, inpainted_visible=True, original_visible=False)
        document = await self.assembler.assemble(db, page_id=page_id, options=options)
        resolved = self.asset_resolver.resolve(document)
        merged = resolved.merged_preview
        if merged is None:
            raise RuntimeError("Could not generate merged preview for export")

        ext = "jpg" if normalized == "jpeg" else normalized
        file_kind = f"translated_export_{ext}"
        file_name = f"translated.{ext}"
        relative_path = build_page_artifact_storage_path(
            str(document.project_id),
            str(document.chapter_id),
            str(document.page_id),
            file_kind,
            file_name,
        )
        out_path = resolve_storage_path(str(relative_path))
        self._write_image(out_path, merged.rgba, ext)

        mime_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "webp": "image/webp",
            "pdf": "application/pdf",
        }[ext]
        await self._upsert_page_file(
            db=db,
            page_id=document.page_id,
            file_kind=file_kind,
            file_path=str(relative_path),
            mime_type=mime_type,
            width=resolved.canvas.width,
            height=resolved.canvas.height,
        )
        await db.commit()
        return file_kind, str(relative_path), build_page_file_url(
            document.project_id,
            document.chapter_id,
            document.page_id,
            file_kind,
        )

    def _write_image(self, output_path: Path, rgba: np.ndarray, ext: str) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.fromarray(rgba, mode="RGBA")
        if ext == "png":
            image.save(output_path, format="PNG")
            return
        if ext == "webp":
            image.save(output_path, format="WEBP", quality=95, method=6)
            return
        if ext == "jpg":
            image.convert("RGB").save(output_path, format="JPEG", quality=95, optimize=True)
            return
        if ext == "pdf":
            image.convert("RGB").save(output_path, format="PDF", resolution=300.0)
            return
        raise ValueError(f"Unsupported image extension: {ext}")

    async def _upsert_page_file(
        self,
        *,
        db: AsyncSession,
        page_id: uuid.UUID,
        file_kind: str,
        file_path: str,
        mime_type: str,
        width: int | None,
        height: int | None,
    ) -> None:
        current = await self.page_repo.get_current_file_by_kind(db, page_id, file_kind)
        if current is not None:
            current.pipeline_run_id = None
            current.file_path = file_path
            current.mime_type = mime_type
            current.width = width
            current.height = height
            current.is_current = True
            return

        await self.page_repo.mark_files_not_current(db, page_id=page_id, file_kind=file_kind)
        page_file = PageFile(
            page_id=page_id,
            pipeline_run_id=None,
            file_kind=file_kind,
            file_path=file_path,
            mime_type=mime_type,
            width=width,
            height=height,
            is_current=True,
        )
        await self.page_repo.create_file(db, page_file)

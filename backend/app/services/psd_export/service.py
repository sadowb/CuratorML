from __future__ import annotations

"""PSD export orchestration.

Example:
    result = await PsdExportService().export_page(
        db,
        page_id,
        include_preview=True,
        include_ocr_notes=True,
    )
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page_file import PageFile
from app.repositories.page_repository import PageRepository
from app.services.psd_export.assembler import PsdExportAssembler
from app.services.psd_export.asset_resolver import PsdExportAssetResolver
from app.services.psd_export.models import PageExportOptions, PsdExportResult
from app.services.psd_export.tree_builder import PsdExportTreeBuilder
from app.services.psd_export.writers.ag_psd_writer import AgPsdWriter
from app.services.psd_export.writers.base import BasePsdWriter
from app.services.psd_export.writers.psd_tools_writer import PsdToolsWriter
from app.services.response_mapper import build_page_file_url
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path


class PsdExportService:
    def __init__(
        self,
        *,
        page_repo: PageRepository | None = None,
        assembler: PsdExportAssembler | None = None,
        asset_resolver: PsdExportAssetResolver | None = None,
        tree_builder: PsdExportTreeBuilder | None = None,
        writer: BasePsdWriter | None = None,
    ) -> None:
        self.page_repo = page_repo or PageRepository()
        self.assembler = assembler or PsdExportAssembler(page_repo=self.page_repo)
        self.asset_resolver = asset_resolver or PsdExportAssetResolver()
        self.tree_builder = tree_builder or PsdExportTreeBuilder()
        self.writer = writer or AgPsdWriter()

    async def export_page(
        self,
        db: AsyncSession,
        page_id: uuid.UUID,
        *,
        include_preview: bool = False,
        include_ocr_notes: bool = False,
        include_brush_cleanup: bool = False,
        include_merged_preview: bool = True,
        original_visible: bool = True,
        inpainted_visible: bool = True,
    ) -> PsdExportResult:
        options = PageExportOptions(
            include_preview=include_preview,
            include_ocr_notes=include_ocr_notes,
            include_brush_cleanup=include_brush_cleanup,
            include_merged_preview=include_merged_preview,
            original_visible=original_visible,
            inpainted_visible=inpainted_visible,
        )

        document = await self.assembler.assemble(db, page_id=page_id, options=options)
        resolved = self.asset_resolver.resolve(document)
        spec = self.tree_builder.build(
            document=document,
            resolved=resolved,
            writer_name=self.writer.writer_name,
            writer_version=self.writer.writer_version,
        )

        psd_relative = build_page_artifact_storage_path(
            str(document.project_id),
            str(document.chapter_id),
            str(document.page_id),
            "psd_export",
            "page.psd",
        )
        manifest_relative = build_page_artifact_storage_path(
            str(document.project_id),
            str(document.chapter_id),
            str(document.page_id),
            "psd_export",
            "page_export_manifest.json",
        )
        out_psd_path = resolve_storage_path(str(psd_relative))
        out_manifest_path = resolve_storage_path(str(manifest_relative))

        manifest = self.writer.write(spec, out_psd_path, out_manifest_path)
        await self._upsert_page_files(
            db=db,
            page_id=document.page_id,
            psd_relative_path=str(psd_relative),
            manifest_relative_path=str(manifest_relative),
            canvas_width=resolved.canvas.width,
            canvas_height=resolved.canvas.height,
        )
        await db.commit()

        psd_url = build_page_file_url(document.project_id, document.chapter_id, document.page_id, "psd_export")
        manifest_url = build_page_file_url(
            document.project_id,
            document.chapter_id,
            document.page_id,
            "psd_export_manifest",
        )
        return PsdExportResult(
            export_id=document.export_id,
            page_id=document.page_id,
            writer=self.writer.writer_name,
            writer_version=self.writer.writer_version,
            canvas=resolved.canvas,
            psd_path=str(psd_relative),
            manifest_path=str(manifest_relative),
            psd_url=psd_url,
            manifest_url=manifest_url,
            layer_count=len(spec.layers),
            manifest=manifest,
        )

    async def _upsert_page_files(
        self,
        *,
        db: AsyncSession,
        page_id: uuid.UUID,
        psd_relative_path: str,
        manifest_relative_path: str,
        canvas_width: int,
        canvas_height: int,
    ) -> None:
        await self._upsert_page_file(
            db=db,
            page_id=page_id,
            file_kind="psd_export",
            file_path=psd_relative_path,
            mime_type="image/vnd.adobe.photoshop",
            width=canvas_width,
            height=canvas_height,
        )
        await self._upsert_page_file(
            db=db,
            page_id=page_id,
            file_kind="psd_export_manifest",
            file_path=manifest_relative_path,
            mime_type="application/json",
            width=None,
            height=None,
        )

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

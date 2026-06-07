from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.models.page_file import PageFile
from app.services.psd_export.models import (
    CanvasSize,
    PageExportDocument,
    PageExportOptions,
    PageImageAsset,
    PsdLayerSpec,
    PsdWriteSpec,
    ResolvedPageAssets,
    ResolvedRasterAsset,
)
from app.services.psd_export.service import PsdExportService


class FakeDb:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakePageRepo:
    def __init__(self) -> None:
        self.files: dict[str, PageFile] = {}
        self.marked: list[str] = []

    async def get_current_file_by_kind(self, _db, _page_id, file_kind: str) -> PageFile | None:
        return self.files.get(file_kind)

    async def mark_files_not_current(self, _db, *, page_id, file_kind: str) -> None:
        self.marked.append(file_kind)

    async def create_file(self, _db, page_file: PageFile) -> PageFile:
        self.files[page_file.file_kind] = page_file
        return page_file


class FakeAssembler:
    def __init__(self, document: PageExportDocument) -> None:
        self.document = document

    async def assemble(self, _db, *, page_id, options: PageExportOptions) -> PageExportDocument:
        assert page_id == self.document.page_id
        self.document.options = options
        return self.document


class FakeResolver:
    def __init__(self, resolved: ResolvedPageAssets) -> None:
        self.resolved = resolved

    def resolve(self, _document: PageExportDocument) -> ResolvedPageAssets:
        return self.resolved


class FakeTreeBuilder:
    def __init__(self, spec: PsdWriteSpec) -> None:
        self.spec = spec

    def build(self, *, document, resolved, writer_name: str, writer_version: str) -> PsdWriteSpec:
        _ = (document, resolved, writer_name, writer_version)
        return self.spec


class FakeWriter:
    writer_name = "fake_writer"
    writer_version = "1"

    def write(self, _spec, out_psd_path: Path, out_manifest_path: Path) -> dict:
        out_psd_path.parent.mkdir(parents=True, exist_ok=True)
        out_psd_path.write_bytes(b"fake_psd")
        manifest = {"writer": self.writer_name, "layers": [{"name": "Original"}]}
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        out_manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest


def _mk_asset(key: str, name: str) -> ResolvedRasterAsset:
    return ResolvedRasterAsset(
        asset_key=key,
        name=name,
        kind="base",
        rgba=np.zeros((20, 30, 4), dtype=np.uint8),
        source_kind="page_file",
        source_ids={"page_file_id": str(uuid.uuid4())},
    )


async def test_psd_export_service_writes_files_and_updates_db(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "storage_root", tmp_path)

    page_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    project_id = uuid.uuid4()
    document = PageExportDocument(
        export_id=uuid.uuid4(),
        page_id=page_id,
        chapter_id=chapter_id,
        project_id=project_id,
        canvas=CanvasSize(width=30, height=20),
        original_image=PageImageAsset(
            file_id=uuid.uuid4(),
            file_kind="original",
            file_path="project/chapter/page/original.png",
            mime_type="image/png",
        ),
        options=PageExportOptions(),
    )
    resolved = ResolvedPageAssets(
        canvas=CanvasSize(width=30, height=20),
        original=_mk_asset("base_original", "Original"),
        inpainted=_mk_asset("base_inpainted", "Inpainted"),
        panels=[],
        balloons=[],
        text_masks=[],
        dialogue_text_layers=[],
        floating_text_layers=[],
        helper_layers=[],
        preview=None,
        merged_preview=None,
        input_summary={},
        fallback_notes=[],
    )
    spec = PsdWriteSpec.build(
        export_id=document.export_id,
        page_id=page_id,
        root_name=f"Page_{page_id}",
        canvas=CanvasSize(width=30, height=20),
        group_order=["00_Base"],
        layers=[
            PsdLayerSpec(
                z_index=0,
                layer_id="base_original",
                name="Original",
                group_path="00_Base",
                visible=True,
                source_kind="page_file",
                source_ids={"page_file_id": str(uuid.uuid4())},
                asset_key="base_original",
            )
        ],
        raster_assets={"base_original": np.zeros((20, 30, 4), dtype=np.uint8)},
        writer_name="fake_writer",
        writer_version="1",
        input_summary={},
        fallback_notes=[],
    )
    repo = FakePageRepo()
    service = PsdExportService(
        page_repo=repo,  # type: ignore[arg-type]
        assembler=FakeAssembler(document),  # type: ignore[arg-type]
        asset_resolver=FakeResolver(resolved),  # type: ignore[arg-type]
        tree_builder=FakeTreeBuilder(spec),  # type: ignore[arg-type]
        writer=FakeWriter(),  # type: ignore[arg-type]
    )
    db = FakeDb()
    result = await service.export_page(db, page_id)

    assert db.committed is True
    assert result.layer_count == 1
    assert result.psd_path.endswith("artifacts/psd_export/page.psd")
    assert result.manifest_path.endswith("artifacts/psd_export/page_export_manifest.json")
    assert "psd_export" in repo.files
    assert "psd_export_manifest" in repo.files

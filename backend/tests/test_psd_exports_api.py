from __future__ import annotations

import uuid

from app.api.dependencies import get_db, get_psd_export_service
from app.schemas.psd_export import PsdExportRequest
from app.services.psd_export.models import CanvasSize, PsdExportResult


async def fake_db_dependency():
    yield object()


class FakePsdExportService:
    def __init__(self) -> None:
        self.page_id = uuid.uuid4()

    async def export_page(self, _db, page_id: uuid.UUID, **kwargs) -> PsdExportResult:
        if page_id != self.page_id:
            raise LookupError("Page not found")
        return PsdExportResult(
            export_id=uuid.uuid4(),
            page_id=page_id,
            writer="fake_writer",
            writer_version="1",
            canvas=CanvasSize(width=1440, height=2048),
            psd_path=f"project_x/chapter_y/page_{page_id}/artifacts/psd_export/page.psd",
            manifest_path=f"project_x/chapter_y/page_{page_id}/artifacts/psd_export/page_export_manifest.json",
            psd_url=f"/api/v1/storage/{uuid.uuid4()}/{uuid.uuid4()}/{page_id}/psd_export",
            manifest_url=f"/api/v1/storage/{uuid.uuid4()}/{uuid.uuid4()}/{page_id}/psd_export_manifest",
            layer_count=8,
            manifest={"layers": [{"name": "Original"}], "opts": kwargs},
        )


def test_psd_export_route_contract(client, test_app) -> None:
    service = FakePsdExportService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_psd_export_service] = lambda: service

    payload = PsdExportRequest(
        include_preview=True,
        include_ocr_notes=True,
        include_brush_cleanup=False,
        include_merged_preview=True,
        original_visible=False,
        inpainted_visible=True,
    )
    response = client.post(f"/api/v1/pages/{service.page_id}/exports/psd", json=payload.model_dump())
    assert response.status_code == 200
    body = response.json()
    assert body["page_id"] == str(service.page_id)
    assert body["writer"] == "fake_writer"
    assert body["outputs"]["psd_path"].endswith("artifacts/psd_export/page.psd")
    assert body["outputs"]["manifest_path"].endswith("artifacts/psd_export/page_export_manifest.json")


def test_psd_export_route_not_found(client, test_app) -> None:
    service = FakePsdExportService()
    test_app.dependency_overrides[get_db] = fake_db_dependency
    test_app.dependency_overrides[get_psd_export_service] = lambda: service

    response = client.post(f"/api/v1/pages/{uuid.uuid4()}/exports/psd", json={})
    assert response.status_code == 404
    assert response.json()["detail"] == "Page not found"

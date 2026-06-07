from fastapi import APIRouter

from app.api.v1.endpoints import chapters, image_exports, jobs, memory, pages, projects, psd_exports, storage

api_router = APIRouter()
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(chapters.router, tags=["chapters"])
api_router.include_router(pages.router, tags=["pages"])
api_router.include_router(psd_exports.router, tags=["psd-exports"])
api_router.include_router(image_exports.router, tags=["image-exports"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(storage.router, tags=["storage"])
api_router.include_router(memory.router, tags=["memory"])

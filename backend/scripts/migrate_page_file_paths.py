from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import AsyncSessionFactory, dispose_engine
from app.models.chapter import Chapter
from app.models.page import Page
from app.models.page_file import PageFile
from app.utils.page_file_path_migration import (
    needs_page_file_path_migration,
    normalized_page_file_path,
)
from app.utils.storage import resolve_storage_path


@dataclass
class MigrationCounters:
    scanned: int = 0
    unchanged: int = 0
    updated_paths: int = 0
    moved_files: int = 0
    already_moved: int = 0
    skipped_missing_source: int = 0
    skipped_invalid_path: int = 0
    skipped_conflicts: int = 0
    skipped_invalid_filename: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize page_files.file_path from page_<number> to page_<page_uuid> "
            "and move storage files accordingly."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates and move files. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Optional project UUID to scope migration.",
    )
    return parser.parse_args()


def _to_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    return uuid.UUID(value)


async def run_migration(*, apply: bool, project_id: uuid.UUID | None) -> MigrationCounters:
    counters = MigrationCounters()
    async with AsyncSessionFactory() as session:
        stmt = (
            select(PageFile, Page, Chapter)
            .join(Page, Page.id == PageFile.page_id)
            .join(Chapter, Chapter.id == Page.chapter_id)
        )
        if project_id is not None:
            stmt = stmt.where(Chapter.project_id == project_id)

        rows = (await session.execute(stmt)).all()

        for page_file, page, chapter in rows:
            counters.scanned += 1
            current_path = page_file.file_path

            try:
                needs_migration = needs_page_file_path_migration(
                    current_path,
                    project_id=chapter.project_id,
                    chapter_id=chapter.id,
                    page_id=page.id,
                )
            except ValueError:
                counters.skipped_invalid_filename += 1
                print(f"SKIP invalid filename: id={page_file.id} path={current_path!r}")
                continue

            if not needs_migration:
                counters.unchanged += 1
                continue

            target_rel = normalized_page_file_path(
                current_path,
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                page_id=page.id,
            )

            try:
                source_abs = resolve_storage_path(current_path)
                target_abs = resolve_storage_path(target_rel)
            except ValueError:
                counters.skipped_invalid_path += 1
                print(f"SKIP invalid path: id={page_file.id} path={current_path!r}")
                continue

            if not apply:
                print(f"PLAN id={page_file.id} old={current_path} new={target_rel}")
                counters.updated_paths += 1
                continue

            can_update = False
            if source_abs == target_abs:
                can_update = True
            elif source_abs.exists() and not target_abs.exists():
                target_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source_abs), str(target_abs))
                counters.moved_files += 1
                can_update = True
            elif (not source_abs.exists()) and target_abs.exists():
                counters.already_moved += 1
                can_update = True
            elif source_abs.exists() and target_abs.exists():
                counters.skipped_conflicts += 1
                print(
                    "SKIP conflict: "
                    f"id={page_file.id} source={source_abs} target={target_abs}"
                )
            else:
                counters.skipped_missing_source += 1
                print(
                    "SKIP missing source: "
                    f"id={page_file.id} source={source_abs} target={target_abs}"
                )

            if can_update:
                page_file.file_path = target_rel
                counters.updated_paths += 1

        if apply:
            await session.commit()
        else:
            await session.rollback()

    return counters


def print_summary(counters: MigrationCounters, *, apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n== {mode} SUMMARY ==")
    print(f"scanned={counters.scanned}")
    print(f"unchanged={counters.unchanged}")
    print(f"updated_paths={counters.updated_paths}")
    print(f"moved_files={counters.moved_files}")
    print(f"already_moved={counters.already_moved}")
    print(f"skipped_missing_source={counters.skipped_missing_source}")
    print(f"skipped_invalid_path={counters.skipped_invalid_path}")
    print(f"skipped_conflicts={counters.skipped_conflicts}")
    print(f"skipped_invalid_filename={counters.skipped_invalid_filename}")


async def main() -> int:
    args = parse_args()
    project_id = _to_uuid(args.project_id)
    counters = await run_migration(apply=args.apply, project_id=project_id)
    print_summary(counters, apply=args.apply)
    await dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import uuid
from collections import defaultdict
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
from app.utils.storage import build_page_artifact_storage_path, resolve_storage_path


@dataclass
class CleanupCounters:
    scanned_rows: int = 0
    scanned_groups: int = 0
    kept_rows: int = 0
    deleted_rows: int = 0
    made_current: int = 0
    normalized_paths: int = 0
    moved_files: int = 0
    replaced_existing_targets: int = 0
    already_at_target: int = 0
    source_missing_target_present: int = 0
    missing_both_paths: int = 0
    invalid_paths: int = 0
    removed_run_dirs: int = 0
    skipped_protected_run_dirs: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize inpaint artifacts to stable paths, deduplicate page_files "
            "for inpainted/inpaint_mask, and remove old run_* folders."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply cleanup. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Optional project UUID to scope cleanup.",
    )
    return parser.parse_args()


def _to_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    return uuid.UUID(value)


def _target_relative_path(
    *,
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    page_id: uuid.UUID,
    file_kind: str,
) -> str:
    if file_kind == "inpainted":
        artifact_name = "page.png"
    elif file_kind == "inpaint_mask":
        artifact_name = "erasure_mask.png"
    else:
        raise ValueError(f"Unsupported file_kind: {file_kind}")

    return str(
        build_page_artifact_storage_path(
            str(project_id),
            str(chapter_id),
            str(page_id),
            "inpainted",
            artifact_name,
        )
    )


def _sort_keeper_key(page_file: PageFile) -> tuple[int, object, str]:
    # Prefer current row first, then newest created_at.
    return (
        1 if bool(page_file.is_current) else 0,
        page_file.created_at,
        str(page_file.id),
    )


def _extract_run_dir_name(relative_path: str) -> str | None:
    marker = "/artifacts/inpainted/"
    idx = relative_path.find(marker)
    if idx == -1:
        return None
    suffix = relative_path[idx + len(marker) :]
    parts = suffix.split("/")
    if not parts:
        return None
    first = parts[0]
    if first.startswith("run_"):
        return first
    return None


async def run_cleanup(*, apply: bool, project_id: uuid.UUID | None) -> CleanupCounters:
    counters = CleanupCounters()

    async with AsyncSessionFactory() as session:
        stmt = (
            select(PageFile, Page, Chapter)
            .join(Page, Page.id == PageFile.page_id)
            .join(Chapter, Chapter.id == Page.chapter_id)
            .where(PageFile.file_kind.in_(["inpainted", "inpaint_mask"]))
        )
        if project_id is not None:
            stmt = stmt.where(Chapter.project_id == project_id)

        rows = (await session.execute(stmt)).all()
        counters.scanned_rows = len(rows)

        grouped: dict[tuple[uuid.UUID, str], list[tuple[PageFile, Page, Chapter]]] = defaultdict(list)
        pages_for_dir_cleanup: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]] = {}
        for page_file, page, chapter in rows:
            grouped[(page.id, page_file.file_kind)].append((page_file, page, chapter))
            pages_for_dir_cleanup[page.id] = (chapter.project_id, chapter.id)

        protected_run_dirs_by_page: dict[uuid.UUID, set[str]] = defaultdict(set)

        for (page_id, file_kind), file_rows in grouped.items():
            counters.scanned_groups += 1
            ordered = sorted(file_rows, key=lambda item: _sort_keeper_key(item[0]), reverse=True)
            keeper_file, keeper_page, keeper_chapter = ordered[0]
            duplicates = ordered[1:]
            counters.kept_rows += 1

            target_rel = _target_relative_path(
                project_id=keeper_chapter.project_id,
                chapter_id=keeper_chapter.id,
                page_id=keeper_page.id,
                file_kind=file_kind,
            )

            source_rel = keeper_file.file_path
            source_abs: Path | None
            target_abs: Path | None
            try:
                source_abs = resolve_storage_path(source_rel)
                target_abs = resolve_storage_path(target_rel)
            except ValueError:
                source_abs = None
                target_abs = None
                counters.invalid_paths += 1

            planned_notes: list[str] = []

            if source_rel == target_rel:
                counters.already_at_target += 1
            elif source_abs is None or target_abs is None:
                planned_notes.append("invalid_path")
            elif source_abs.exists():
                planned_notes.append(f"move:{source_rel} -> {target_rel}")
                if target_abs.exists() and target_abs != source_abs:
                    planned_notes.append("replace_existing_target")
            elif target_abs.exists():
                planned_notes.append("use_existing_target_missing_source")
                counters.source_missing_target_present += 1
            else:
                planned_notes.append("missing_both_source_and_target")
                counters.missing_both_paths += 1

            if not bool(keeper_file.is_current):
                planned_notes.append("set_current_true")

            if duplicates:
                planned_notes.append(f"delete_duplicates:{len(duplicates)}")

            if not apply:
                print(
                    "PLAN "
                    f"page={page_id} kind={file_kind} keep={keeper_file.id} "
                    f"notes={','.join(planned_notes) if planned_notes else 'none'}"
                )
                continue

            # Apply path normalization and file movement.
            if source_rel != target_rel:
                if source_abs is None or target_abs is None:
                    pass
                elif source_abs.exists():
                    target_abs.parent.mkdir(parents=True, exist_ok=True)
                    if target_abs.exists() and target_abs != source_abs:
                        if target_abs.is_file():
                            target_abs.unlink()
                            counters.replaced_existing_targets += 1
                        else:
                            raise ValueError(f"Target path is not a file: {target_abs}")
                    if source_abs != target_abs:
                        shutil.move(str(source_abs), str(target_abs))
                        counters.moved_files += 1
                    keeper_file.file_path = target_rel
                    counters.normalized_paths += 1
                elif target_abs.exists():
                    keeper_file.file_path = target_rel
                    counters.normalized_paths += 1
                else:
                    # Keep original path if neither exists.
                    pass

            if not bool(keeper_file.is_current):
                keeper_file.is_current = True
                counters.made_current += 1

            for dup_file, _dup_page, _dup_chapter in duplicates:
                await session.delete(dup_file)
                counters.deleted_rows += 1

            run_dir = _extract_run_dir_name(keeper_file.file_path)
            if run_dir:
                protected_run_dirs_by_page[keeper_page.id].add(run_dir)

        # Remove stale run_* directories under artifacts/inpainted.
        for page_id, (project_uuid, chapter_uuid) in pages_for_dir_cleanup.items():
            inpaint_dir_rel = (
                f"project_{project_uuid}/chapter_{chapter_uuid}/page_{page_id}/artifacts/inpainted"
            )
            try:
                inpaint_dir_abs = resolve_storage_path(inpaint_dir_rel)
            except ValueError:
                counters.invalid_paths += 1
                continue

            if not inpaint_dir_abs.exists() or not inpaint_dir_abs.is_dir():
                continue

            protected = protected_run_dirs_by_page.get(page_id, set())
            for child in inpaint_dir_abs.iterdir():
                if not child.is_dir() or not child.name.startswith("run_"):
                    continue
                if child.name in protected:
                    counters.skipped_protected_run_dirs += 1
                    continue
                if apply:
                    shutil.rmtree(child)
                counters.removed_run_dirs += 1

        if apply:
            await session.commit()
        else:
            await session.rollback()

    return counters


def print_summary(counters: CleanupCounters, *, apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n== {mode} SUMMARY ==")
    print(f"scanned_rows={counters.scanned_rows}")
    print(f"scanned_groups={counters.scanned_groups}")
    print(f"kept_rows={counters.kept_rows}")
    print(f"deleted_rows={counters.deleted_rows}")
    print(f"made_current={counters.made_current}")
    print(f"normalized_paths={counters.normalized_paths}")
    print(f"moved_files={counters.moved_files}")
    print(f"replaced_existing_targets={counters.replaced_existing_targets}")
    print(f"already_at_target={counters.already_at_target}")
    print(f"source_missing_target_present={counters.source_missing_target_present}")
    print(f"missing_both_paths={counters.missing_both_paths}")
    print(f"invalid_paths={counters.invalid_paths}")
    print(f"removed_run_dirs={counters.removed_run_dirs}")
    print(f"skipped_protected_run_dirs={counters.skipped_protected_run_dirs}")


async def main() -> int:
    args = parse_args()
    project_id = _to_uuid(args.project_id)
    counters = await run_cleanup(apply=args.apply, project_id=project_id)
    print_summary(counters, apply=args.apply)
    await dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


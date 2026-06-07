from __future__ import annotations

from scripts.migrate_page_file_paths import print_summary, MigrationCounters


def test_print_summary_formats_without_error(capsys) -> None:
    counters = MigrationCounters(
        scanned=10,
        unchanged=4,
        updated_paths=6,
        moved_files=5,
        already_moved=1,
        skipped_missing_source=0,
        skipped_invalid_path=0,
        skipped_conflicts=0,
        skipped_invalid_filename=0,
    )

    print_summary(counters, apply=False)
    output = capsys.readouterr().out
    assert "DRY-RUN SUMMARY" in output
    assert "updated_paths=6" in output

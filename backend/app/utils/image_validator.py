from __future__ import annotations

from pathlib import Path

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class InvalidImageFile(ValueError):
    pass


def validate_image_filename(filename: str | None) -> str:
    if not filename:
        raise InvalidImageFile("File must have a valid filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise InvalidImageFile("Only PNG, JPG, and WEBP files are supported")

    return suffix

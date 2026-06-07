const IMAGE_MIME_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
const IMAGE_EXTENSION_PATTERN = /\.(png|jpe?g|webp)$/i;

export function isSupportedImageUpload(
  file: Pick<File, "type" | "name">,
): boolean {
  if (
    IMAGE_MIME_TYPES.includes(file.type as (typeof IMAGE_MIME_TYPES)[number])
  ) {
    return true;
  }

  return IMAGE_EXTENSION_PATTERN.test(file.name);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

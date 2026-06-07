import type { PageText } from "../types/api";

function firstNonBlank(values: Array<string | null | undefined>): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return "";
}

export function resolveTranslatedText(text: Pick<
  PageText,
  "display_text_final" | "translation_corrected" | "translation_draft"
>): string {
  return firstNonBlank([
    text.display_text_final,
    text.translation_corrected,
    text.translation_draft,
  ]);
}

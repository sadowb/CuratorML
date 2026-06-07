import { describe, expect, it } from "vitest";

import { resolveTranslatedText } from "../textDisplay";

describe("resolveTranslatedText", () => {
  it("prefers final text when non-blank", () => {
    expect(
      resolveTranslatedText({
        display_text_final: "Final",
        translation_corrected: "Corrected",
        translation_draft: "Draft",
      }),
    ).toBe("Final");
  });

  it("falls back to corrected when final is blank", () => {
    expect(
      resolveTranslatedText({
        display_text_final: "   ",
        translation_corrected: "Corrected",
        translation_draft: "Draft",
      }),
    ).toBe("Corrected");
  });

  it("falls back to draft when final and corrected are blank", () => {
    expect(
      resolveTranslatedText({
        display_text_final: "   ",
        translation_corrected: "",
        translation_draft: "Draft",
      }),
    ).toBe("Draft");
  });

  it("falls back to draft when final and corrected are null", () => {
    expect(
      resolveTranslatedText({
        display_text_final: null,
        translation_corrected: null,
        translation_draft: "Draft",
      }),
    ).toBe("Draft");
  });

  it("returns empty string when no translated field has content", () => {
    expect(
      resolveTranslatedText({
        display_text_final: null,
        translation_corrected: "",
        translation_draft: " ",
      }),
    ).toBe("");
  });
});

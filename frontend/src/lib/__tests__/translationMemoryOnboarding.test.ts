import { describe, expect, it } from "vitest";
import { parseBulkMemoryInput } from "../translationMemoryOnboarding";

describe("parseBulkMemoryInput", () => {
  it("parses valid simple lines", () => {
    const result = parseBulkMemoryInput("ゾロ -> Zoro\n鬼斬り -> Oni Giri");
    expect(result.errors).toEqual([]);
    expect(result.validEntries).toHaveLength(2);
    expect(result.validEntries[0].source_term).toBe("ゾロ");
    expect(result.validEntries[0].preferred_translation).toBe("Zoro");
  });

  it("parses metadata fields", () => {
    const result = parseBulkMemoryInput(
      "海軍 -> Marines | type=organization | aliases=海軍本部, Marines | scope=chapter",
    );
    expect(result.errors).toEqual([]);
    expect(result.validEntries).toHaveLength(1);
    expect(result.validEntries[0].entry_type).toBe("organization");
    expect(result.validEntries[0].aliases).toEqual(["海軍本部", "Marines"]);
    expect(result.validEntries[0].scope_mode).toBe("chapter");
  });

  it("returns line-level errors for malformed input", () => {
    const result = parseBulkMemoryInput("bad line without arrow");
    expect(result.validEntries).toHaveLength(0);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});

import { createMemoryEntry } from "./api";
import type {
  MemoryEntryType,
  TranslationMemoryEntryCreatePayload,
} from "../types/api";

export interface StagedMemoryEntry {
  id: string;
  entry_type: MemoryEntryType;
  source_term: string;
  preferred_translation: string;
  scope_mode: "project" | "chapter";
  aliases: string[];
  notes?: string;
}

export interface ParsedBulkMemoryResult {
  validEntries: Omit<StagedMemoryEntry, "id">[];
  errors: string[];
}

const VALID_TYPES = new Set<MemoryEntryType>([
  "character",
  "attack",
  "place",
  "organization",
]);
const PENDING_MEMORY_PREFIX = "pending_memory_entries:";

function parseAliases(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseEntryType(value: string): MemoryEntryType | null {
  const normalized = value.trim().toLowerCase();
  if (!VALID_TYPES.has(normalized as MemoryEntryType)) {
    return null;
  }
  return normalized as MemoryEntryType;
}

export function parseBulkMemoryInput(input: string): ParsedBulkMemoryResult {
  const lines = input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const validEntries: Omit<StagedMemoryEntry, "id">[] = [];
  const errors: string[] = [];

  lines.forEach((line, index) => {
    const [mainPair, ...metaParts] = line.split("|").map((part) => part.trim());
    if (!mainPair || !mainPair.includes("->")) {
      errors.push(`Line ${index + 1}: expected "source -> preferred".`);
      return;
    }

    const [sourceTermRaw, preferredRaw] = mainPair.split("->").map((part) => part.trim());
    if (!sourceTermRaw || !preferredRaw) {
      errors.push(`Line ${index + 1}: source and preferred translation are required.`);
      return;
    }

    const draft: Omit<StagedMemoryEntry, "id"> = {
      entry_type: "character",
      source_term: sourceTermRaw,
      preferred_translation: preferredRaw,
      scope_mode: "project",
      aliases: [],
      notes: "",
    };

    for (const meta of metaParts) {
      if (!meta.includes("=")) {
        errors.push(
          `Line ${index + 1}: invalid metadata segment "${meta}" (use key=value).`,
        );
        return;
      }
      const [rawKey, rawValue] = meta.split("=", 2);
      const key = rawKey.trim().toLowerCase();
      const value = rawValue.trim();
      if (!value) continue;

      if (key === "type") {
        const parsedType = parseEntryType(value);
        if (!parsedType) {
          errors.push(
            `Line ${index + 1}: invalid type "${value}" (character|attack|place|organization).`,
          );
          return;
        }
        draft.entry_type = parsedType;
      } else if (key === "aliases") {
        draft.aliases = parseAliases(value);
      } else if (key === "scope") {
        const scope = value.toLowerCase();
        if (scope !== "project" && scope !== "chapter") {
          errors.push(
            `Line ${index + 1}: invalid scope "${value}" (project|chapter).`,
          );
          return;
        }
        draft.scope_mode = scope;
      } else if (key === "notes") {
        draft.notes = value;
      } else {
        errors.push(
          `Line ${index + 1}: unsupported metadata key "${key}".`,
        );
        return;
      }
    }

    validEntries.push(draft);
  });

  return { validEntries, errors };
}

export interface FailedMemorySave {
  entry: StagedMemoryEntry;
  error: string;
}

export async function createMemoryEntriesBatch(
  projectId: string,
  chapterNumber: number,
  entries: StagedMemoryEntry[],
  concurrency = 4,
): Promise<{ failed: FailedMemorySave[] }> {
  if (entries.length === 0) {
    return { failed: [] };
  }

  const failed: FailedMemorySave[] = [];
  let cursor = 0;
  const workerCount = Math.max(1, Math.min(concurrency, entries.length));

  const workers = Array.from({ length: workerCount }, async () => {
    while (cursor < entries.length) {
      const currentIndex = cursor;
      cursor += 1;
      const entry = entries[currentIndex];

      const payload: TranslationMemoryEntryCreatePayload = {
        entry_type: entry.entry_type,
        source_term: entry.source_term,
        preferred_translation: entry.preferred_translation,
        scope_chapter: entry.scope_mode === "chapter" ? chapterNumber : null,
        aliases: entry.aliases,
        notes: entry.notes?.trim() ? entry.notes.trim() : null,
      };

      try {
        await createMemoryEntry(projectId, payload);
      } catch (err) {
        failed.push({
          entry,
          error: err instanceof Error ? err.message : "Failed to save memory entry.",
        });
      }
    }
  });

  await Promise.all(workers);
  return { failed };
}

function pendingMemoryKey(projectId: string): string {
  return `${PENDING_MEMORY_PREFIX}${projectId}`;
}

export function savePendingMemoryEntries(
  projectId: string,
  failedEntries: StagedMemoryEntry[],
): void {
  if (typeof window === "undefined") return;
  if (failedEntries.length === 0) {
    window.sessionStorage.removeItem(pendingMemoryKey(projectId));
    return;
  }
  window.sessionStorage.setItem(
    pendingMemoryKey(projectId),
    JSON.stringify(failedEntries),
  );
}

export function loadPendingMemoryEntries(projectId: string): StagedMemoryEntry[] {
  if (typeof window === "undefined") return [];
  const raw = window.sessionStorage.getItem(pendingMemoryKey(projectId));
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as StagedMemoryEntry[];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function clearPendingMemoryEntries(projectId: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(pendingMemoryKey(projectId));
}

export function createStagedMemoryEntry(
  entry: Omit<StagedMemoryEntry, "id">,
): StagedMemoryEntry {
  return {
    ...entry,
    id: crypto.randomUUID(),
  };
}

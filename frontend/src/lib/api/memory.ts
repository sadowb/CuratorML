import { request } from "./core";
import type {
  MemoryEntryType,
  TranslationMemoryEntry,
  TranslationMemoryEntryCreatePayload,
  TranslationMemoryEntryUpdatePayload,
} from "../../types/api";

interface ListMemoryEntriesOptions {
  entry_type?: MemoryEntryType;
  scope_chapter?: number;
  q?: string;
}

export async function createMemoryEntry(
  projectId: string,
  payload: TranslationMemoryEntryCreatePayload,
): Promise<TranslationMemoryEntry> {
  return request<TranslationMemoryEntry>(`/projects/${projectId}/memory/entries`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

interface CreateMemoryEntriesBatchResponse {
  created: TranslationMemoryEntry[];
  failed: Array<{
    index: number;
    source_term: string;
    detail: string;
  }>;
}

export async function createMemoryEntriesBatchRequest(
  projectId: string,
  entries: TranslationMemoryEntryCreatePayload[],
): Promise<CreateMemoryEntriesBatchResponse> {
  return request<CreateMemoryEntriesBatchResponse>(
    `/projects/${projectId}/memory/entries/batch`,
    {
      method: "POST",
      body: JSON.stringify({ entries }),
    },
  );
}

export async function listMemoryEntries(
  projectId: string,
  options?: ListMemoryEntriesOptions,
): Promise<TranslationMemoryEntry[]> {
  const query = new URLSearchParams();
  if (options?.entry_type) {
    query.set("entry_type", options.entry_type);
  }
  if (options?.scope_chapter) {
    query.set("scope_chapter", String(options.scope_chapter));
  }
  if (options?.q) {
    query.set("q", options.q);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<TranslationMemoryEntry[]>(
    `/projects/${projectId}/memory/entries${suffix}`,
  );
}

export async function updateMemoryEntry(
  projectId: string,
  entryId: string,
  payload: TranslationMemoryEntryUpdatePayload,
): Promise<TranslationMemoryEntry> {
  return request<TranslationMemoryEntry>(
    `/projects/${projectId}/memory/entries/${entryId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteMemoryEntry(
  projectId: string,
  entryId: string,
): Promise<void> {
  await request<void>(`/projects/${projectId}/memory/entries/${entryId}`, {
    method: "DELETE",
  });
}

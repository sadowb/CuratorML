import { z } from 'zod';
import type { MemoryEntryType } from "./api";

const optionalEstimatedPagesSchema = z.preprocess(
  (value) => {
    if (value === '' || value === null || value === undefined) {
      return undefined;
    }
    return value;
  },
  z.coerce.number().int().min(1).optional(),
);

export const projectSchema = z.object({
  projectName: z.string().min(2, 'Project name must be at least 2 characters'),
  sourceLang: z.string(),
  targetLang: z.string(),
  direction: z.enum(['LTR', 'RTL']),
  chapterTitle: z.string().min(1, 'Chapter title is required'),
  chapterNumber: z.coerce.number().int().min(1, 'Chapter number must be at least 1'),
  estimatedPages: optionalEstimatedPagesSchema,
  context: z.string().optional(),
  enableOcr: z.boolean(),
  requireQc: z.boolean(),
});

export type ProjectFormData = z.infer<typeof projectSchema>;

export interface ProjectMemoryRowForm {
  id: string;
  entry_type: MemoryEntryType;
  source_term: string;
  preferred_translation: string;
  scope_mode: "project" | "chapter";
  aliases: string[];
  notes?: string;
}

export interface ProjectMemoryBulkDraft {
  rawText: string;
  parseErrors: string[];
}

import { describe, expect, it } from 'vitest';
import { projectSchema } from '../forms';

describe('projectSchema (Zod validation)', () => {
  const validData = {
    projectName: 'Naruto',
    sourceLang: 'Japanese',
    targetLang: 'English (US)',
    direction: 'LTR' as const,
    chapterTitle: 'Chapter 41 - Night Market',
    chapterNumber: 41,
    estimatedPages: 48,
    context: 'Naruto has just returned to the village.',
    enableOcr: true,
    requireQc: true,
  };

  it('passes with valid data', () => {
    const result = projectSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('rejects short project names', () => {
    const result = projectSchema.safeParse({ ...validData, projectName: 'A' });
    expect(result.success).toBe(false);
  });

  it('rejects chapter number below 1', () => {
    const result = projectSchema.safeParse({ ...validData, chapterNumber: 0 });
    expect(result.success).toBe(false);
  });

  it('accepts undefined estimatedPages', () => {
    const result = projectSchema.safeParse({ ...validData, estimatedPages: undefined });
    expect(result.success).toBe(true);
  });

  it('coerces chapter number from string', () => {
    const result = projectSchema.safeParse({ ...validData, chapterNumber: '12' });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.chapterNumber).toBe(12);
    }
  });

  it('only allows LTR or RTL for direction', () => {
    const result = projectSchema.safeParse({ ...validData, direction: 'INVALID' });
    expect(result.success).toBe(false);
  });

  it('rejects missing required fields', () => {
    const result = projectSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});

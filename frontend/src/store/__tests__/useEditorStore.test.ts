import { beforeEach, describe, expect, it } from 'vitest';
import { useEditorStore } from '../useEditorStore';

describe('useEditorStore', () => {
  beforeEach(() => {
    useEditorStore.setState({
      viewMode: 'Original',
      activeWorkflow: 'Mask',
      draftsByPage: {},
    });
  });

  it('has correct initial state', () => {
    const state = useEditorStore.getState();
    expect(state.viewMode).toBe('Original');
    expect(state.activeWorkflow).toBe('Mask');
    expect(state.draftsByPage).toEqual({});
  });

  it('sets viewMode correctly', () => {
    useEditorStore.getState().setViewMode('Translated');
    expect(useEditorStore.getState().viewMode).toBe('Translated');
  });

  it('sets activeWorkflow correctly', () => {
    useEditorStore.getState().setActiveWorkflow('OCR');
    expect(useEditorStore.getState().activeWorkflow).toBe('OCR');
  });

  it('upserts drafts by page and text id', () => {
    useEditorStore.getState().upsertDraft('page-1', 'text-1', { ocr_text_corrected: 'Updated text' });

    const draft = useEditorStore.getState().getPageDrafts('page-1')['text-1'];
    expect(draft).toBeDefined();
    expect(draft.ocr_text_corrected).toBe('Updated text');
    expect(typeof draft.updatedAt).toBe('number');
  });

  it('clears draft entries', () => {
    useEditorStore.getState().upsertDraft('page-1', 'text-1', { ocr_text_corrected: 'Updated text' });
    useEditorStore.getState().clearDraft('page-1', 'text-1');

    expect(useEditorStore.getState().getPageDrafts('page-1')).toEqual({});
  });
});

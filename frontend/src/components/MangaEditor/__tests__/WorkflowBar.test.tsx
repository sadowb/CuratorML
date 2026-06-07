import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import WorkflowBar from '../WorkflowBar';
import { useEditorStore } from '../../../store/useEditorStore';

const chapters = [
  {
    id: 'chapter-1',
    title: 'Chapter 1',
    chapter_number: 1,
  },
];

describe('WorkflowBar mask save button', () => {
  beforeEach(() => {
    useEditorStore.setState({ activeWorkflow: 'Mask' });
  });

  it('disables Save Masks when there are no dirty masks', () => {
    render(
      <WorkflowBar
        chapters={chapters}
        activeChapterId="chapter-1"
        onChapterChange={vi.fn()}
        onCreateChapter={vi.fn()}
        isCreatingChapter={false}
        onRunMaskInference={vi.fn()}
        onSaveMasks={vi.fn()}
        hasDirtyMasks={false}
      />,
    );

    expect(screen.getByRole('button', { name: 'Save edited masks' })).toBeDisabled();
  });

  it('enables Save Masks when dirty masks are present', () => {
    render(
      <WorkflowBar
        chapters={chapters}
        activeChapterId="chapter-1"
        onChapterChange={vi.fn()}
        onCreateChapter={vi.fn()}
        isCreatingChapter={false}
        onRunMaskInference={vi.fn()}
        onSaveMasks={vi.fn()}
        hasDirtyMasks
      />,
    );

    expect(screen.getByRole('button', { name: 'Save edited masks' })).toBeEnabled();
  });

  it('shows saving state while masks are being saved', () => {
    render(
      <WorkflowBar
        chapters={chapters}
        activeChapterId="chapter-1"
        onChapterChange={vi.fn()}
        onCreateChapter={vi.fn()}
        isCreatingChapter={false}
        onRunMaskInference={vi.fn()}
        onSaveMasks={vi.fn()}
        hasDirtyMasks
        isSavingMasks
      />,
    );

    expect(screen.getByRole('button', { name: 'Save edited masks' })).toBeDisabled();
    expect(screen.getByText('Saving...')).toBeInTheDocument();
  });
});

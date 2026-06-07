import { Button } from "../ui/Button";

interface CreateChapterModalProps {
  isOpen: boolean;
  description: string;
  chapterTitle: string;
  onChapterTitleChange: (title: string) => void;
  chapterNumber: number;
  onChapterNumberChange: (nextNumber: number) => void;
  onClose: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  submitLabel?: string;
}

export function CreateChapterModal({
  isOpen,
  description,
  chapterTitle,
  onChapterTitleChange,
  chapterNumber,
  onChapterNumberChange,
  onClose,
  onSubmit,
  isSubmitting,
  submitLabel = "Create Chapter",
}: CreateChapterModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border border-brand-border bg-white shadow-xl p-6 flex flex-col gap-4">
        <h3 className="text-lg font-semibold text-gray-900">Add Chapter</h3>
        <p className="text-sm text-gray-600">{description}</p>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-gray-700">Chapter Title</span>
          <input
            className="h-10 rounded-md border border-brand-border px-3 text-sm"
            value={chapterTitle}
            onChange={(event) => onChapterTitleChange(event.target.value)}
            placeholder="Chapter 2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-gray-700">Chapter Number</span>
          <input
            type="number"
            min={1}
            className="h-10 rounded-md border border-brand-border px-3 text-sm"
            value={chapterNumber}
            onChange={(event) =>
              onChapterNumberChange(
                Math.max(1, Number(event.target.value) || 1),
              )
            }
          />
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : submitLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

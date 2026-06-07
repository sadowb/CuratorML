import TopHeader from "./TopHeader";

interface ChapterOption {
  id: string;
  title: string;
  chapter_number: number;
}

interface WorkflowBarProps {
  chapters: ChapterOption[];
  activeChapterId?: string;
  onChapterChange: (chapterId: string) => void;
  onCreateChapter: () => void;
  isCreatingChapter: boolean;
  onRunMaskInference?: () => void;
  isRunningMaskInference?: boolean;
  onSaveMasks?: () => void;
  isSavingMasks?: boolean;
  hasDirtyMasks?: boolean;
  jobPhase?: "idle" | "submitting" | "pending" | "running" | "completed" | "failed";
  jobDetail?: string | null;
}

export default function WorkflowBar(props: WorkflowBarProps) {
  return (
    <TopHeader
      {...props}
      onUploadPages={() => undefined}
      isUploadingPages={false}
      uploadError={null}
      uploadNotice={null}
    />
  );
}

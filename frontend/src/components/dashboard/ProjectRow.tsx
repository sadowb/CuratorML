import { Trash2 } from "lucide-react";
import { Badge } from "../ui/Badge";
import type { ProjectListItem } from "../../types/api";

function mapStatusToVariant(
  status: string,
): "default" | "warning" | "success" | "outline" {
  const normalized = status.toLowerCase();
  if (normalized.includes("active")) {
    return "warning";
  }
  if (normalized.includes("completed")) {
    return "success";
  }
  if (normalized.includes("archived")) {
    return "outline";
  }
  return "default";
}

interface ProjectRowProps {
  project: ProjectListItem;
  isOpening: boolean;
  isRouting: boolean;
  isDeleting: boolean;
  onOpenEditor: (projectId: string) => void;
  onOpenUpload: (projectId: string) => void;
  onAddChapter: (projectId: string, projectName: string) => void;
  onDeleteProject: (projectId: string, projectName: string) => void;
}

export function ProjectRow({
  project,
  isOpening,
  isRouting,
  isDeleting,
  onOpenEditor,
  onOpenUpload,
  onAddChapter,
  onDeleteProject,
}: ProjectRowProps) {
  return (
    <article className="border-b border-[#eadde1] px-5 py-6 text-left transition-colors hover:bg-[#fff9fb] lg:px-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <button
            type="button"
            onClick={() => onOpenEditor(project.id)}
            className="mb-1 text-[15px] font-bold text-[#2d151d] transition-colors hover:text-[#6b2d3c]"
          >
            {project.name}
          </button>
          <p className="mb-3 text-[13px] font-medium text-[#6e5b62]">
            {project.chapter_count} chapters · {project.page_count} pages ·{" "}
            {project.source_language} → {project.target_language}
          </p>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap justify-end">
          <Badge variant={mapStatusToVariant(project.project_status)}>
            {project.project_status}
          </Badge>
          {isOpening ? (
            <span className="text-xs text-brand-text-muted">Opening...</span>
          ) : null}
          {isRouting ? (
            <span className="text-xs text-brand-text-muted">Routing...</span>
          ) : null}
          <button
            type="button"
            onClick={() => onOpenEditor(project.id)}
            disabled={isOpening || isDeleting}
            className="h-8 rounded-full border border-[#d8c7cd] px-3 text-xs font-semibold text-[#2d151d] transition-colors hover:bg-[#f7ecef] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Open Editor
          </button>
          <button
            type="button"
            onClick={() => onOpenUpload(project.id)}
            disabled={isRouting || isDeleting}
            className="h-8 rounded-full border border-[#d8c7cd] px-3 text-xs font-semibold text-[#2d151d] transition-colors hover:bg-[#f7ecef] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Upload Pages
          </button>
          <button
            type="button"
            onClick={() => onAddChapter(project.id, project.name)}
            disabled={isDeleting}
            className="h-8 rounded-full border border-[#d8c7cd] px-3 text-xs font-semibold text-[#2d151d] transition-colors hover:bg-[#f7ecef] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Add Chapter
          </button>
          <button
            type="button"
            onClick={() => onDeleteProject(project.id, project.name)}
            disabled={isDeleting}
            className="h-8 w-8 rounded-full border border-red-200 text-red-600 hover:bg-red-50 flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={`Delete project ${project.name}`}
          >
            {isDeleting ? (
              <span className="text-[10px] font-bold">...</span>
            ) : (
              <Trash2 className="w-4 h-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </article>
  );
}

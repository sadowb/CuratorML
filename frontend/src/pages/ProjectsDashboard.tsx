import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PaginationControls } from "../components/dashboard/PaginationControls";
import { ProjectRow } from "../components/dashboard/ProjectRow";
import {
  ProjectsToolbar,
  type ProjectStatusFilter,
} from "../components/dashboard/ProjectsToolbar";
import { CreateChapterModal } from "../components/shared/CreateChapterModal";
import { Button } from "../components/ui/Button";
import { InlineAlert } from "../components/ui/InlineAlert";
import {
  createProjectChapter,
  deleteProject,
  getProjectEntry,
  listProjectChapters,
  listProjects,
} from "../lib/api";
import type { ProjectListItem } from "../types/api";

const PROJECTS_PER_PAGE = 6;

interface CreateChapterPayload {
  title: string;
  chapter_number: number;
}

// -- Pure Filtering Logic ----------------------------------------------------
function filterAndPaginateProjects(
  projects: ProjectListItem[],
  searchTerm: string,
  statusFilter: string,
  page: number,
  perPage: number,
) {
  const normalizedQuery = searchTerm.trim().toLowerCase();
  
  const filtered = projects.filter((project) => {
    if (
      statusFilter !== "all" &&
      !project.project_status.toLowerCase().includes(statusFilter)
    ) {
      return false;
    }
    if (!normalizedQuery) return true;
    return [
      project.name,
      project.source_language,
      project.target_language,
      project.project_status,
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const validPage = Math.min(page, totalPages);

  const startIndex = (validPage - 1) * perPage;
  const paginated = filtered.slice(startIndex, startIndex + perPage);

  return { filtered, paginated, totalPages, validPage };
}

// -- Main Page ---------------------------------------------------------------
export default function ProjectsDashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // URL State (Replaces useState and manual syncing)
  const [searchParams, setSearchParams] = useSearchParams();
  const searchTerm = searchParams.get("search") ?? "";
  const statusFilter = (searchParams.get("status") ?? "all") as ProjectStatusFilter;
  const currentPage = parseInt(searchParams.get("page") ?? "1", 10);

  const updateUrlParams = (key: string, value: string) => {
    setSearchParams((prev) => {
      if (value === "" || value === "all" || value === "1") {
        prev.delete(key);
      } else {
        prev.set(key, value);
      }
      if (key !== "page") prev.delete("page"); // Reset tracking on filter change
      return prev;
    });
  };

  // UI Error State (Routing / Modals)
  const [uiError, setUiError] = useState<string | null>(null);

  // -- Queries & Mutations (Replaces useEffect, isLoading, error tracking)
  const { data: projects = [], isLoading: isFetchingProjects, error: fetchError } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
    onError: (err) => setUiError(err instanceof Error ? err.message : "Failed to delete"),
  });

  const [openingProjectId, setOpeningProjectId] = useState<string | null>(null);
  const [uploadingProjectId, setUploadingProjectId] = useState<string | null>(null);

  const openProjectRoute = async (projectId: string, routeKind: "editor" | "upload") => {
    setUiError(null);
    if (routeKind === "editor") {
      setOpeningProjectId(projectId);
    } else {
      setUploadingProjectId(projectId);
    }

    try {
      const entry = await getProjectEntry(projectId);
      const destination = routeKind === "editor" ? (entry.editor_url ?? entry.upload_url) : entry.upload_url;
      if (destination) {
        navigate(destination);
      } else {
        setUiError(`Create a chapter first to open this project.`);
      }
    } catch (routeError) {
      setUiError(routeError instanceof Error ? routeError.message : "Failed to open project");
    } finally {
      if (routeKind === "editor") {
        setOpeningProjectId(null);
      } else {
        setUploadingProjectId(null);
      }
    }
  };

  // Chapter Creation Modal State
  const [isChapterModalOpen, setIsChapterModalOpen] = useState(false);
  const [chapterTitle, setChapterTitle] = useState("");
  const [chapterNumber, setChapterNumber] = useState(1);
  const [activeChapterProject, setActiveChapterProject] = useState<{ id: string; name: string } | null>(null);

  const chapterMutation = useMutation({
    mutationFn: ({ pId, payload }: { pId: string; payload: CreateChapterPayload }) =>
      createProjectChapter(pId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setIsChapterModalOpen(false);
      setActiveChapterProject(null);
    },
    onError: (err) => setUiError(err instanceof Error ? err.message : "Failed to create chapter"),
  });

  const openCreateChapterModal = async (projectId: string, projectName: string) => {
    setUiError(null);
    try {
      const chapters = await listProjectChapters(projectId);
      setActiveChapterProject({ id: projectId, name: projectName });
      const nextNumber = chapters.length === 0 ? 1 : Math.max(...chapters.map((c) => c.chapter_number)) + 1;
      setChapterNumber(nextNumber);
      setChapterTitle(`Chapter ${nextNumber}`);
      setIsChapterModalOpen(true);
    } catch (err) {
      setUiError(err instanceof Error ? err.message : "Failed to prepare chapter creation");
    }
  };

  // -- Derived UI State ------------------------------------------------------
  const hasProjects = projects.length > 0;
  
  const { filtered, paginated, totalPages, validPage } = filterAndPaginateProjects(
    projects,
    searchTerm,
    statusFilter,
    currentPage,
    PROJECTS_PER_PAGE
  );

  const summaryText =
    isFetchingProjects && !hasProjects
      ? "Loading projects..."
      : `Showing ${paginated.length > 0 ? (validPage - 1) * PROJECTS_PER_PAGE + 1 : 0}-${
          (validPage - 1) * PROJECTS_PER_PAGE + paginated.length
        } of ${filtered.length}`;

  const displayError = (fetchError as Error)?.message || uiError;

  return (
    <div className="scrollbar-hide flex h-full w-full flex-col overflow-y-auto bg-[radial-gradient(circle_at_88%_0%,_#fceff4_0%,_#fbfbfb_44%,_#f5f4f0_100%)] px-4 pb-20 pt-12 text-brand-text lg:px-6">
      <div className="mx-auto mb-7 w-full max-w-[1440px]">
        <div className="rounded-[18px] border border-[#e3d2d8] bg-white/90 p-6 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.45)] backdrop-blur-sm lg:p-7">
          <div className="flex items-end justify-between gap-6 flex-wrap">
            <div>
              <p className="text-[11px] uppercase tracking-[0.2em] text-brand-text-chip font-bold mb-3">
                Control Center
              </p>
              <h1 className="text-[38px] lg:text-[44px] font-serif text-gray-900 mb-3 leading-none tracking-tight">
                Manga Translation Operations
              </h1>
              <p className="text-[15px] text-gray-600 font-medium max-w-2xl">
                Search fast, filter by status, and jump into upload or editor
                sessions without context switching.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button onClick={() => navigate("/create")} variant="primary" className="whitespace-nowrap">
                + Create Project
              </Button>
              <Button
                onClick={() => {
                  const firstProject = filtered[0] ?? projects[0];
                  if (firstProject) void openProjectRoute(firstProject.id, "editor");
                }}
                variant="outline"
                className="whitespace-nowrap"
                disabled={!hasProjects || openingProjectId !== null}
              >
                Open Editor
              </Button>
            </div>
          </div>
        </div>
      </div>

      <CreateChapterModal
        isOpen={isChapterModalOpen}
        description={`Create a new chapter in ${activeChapterProject?.name ?? "this project"}.`}
        chapterTitle={chapterTitle}
        onChapterTitleChange={setChapterTitle}
        chapterNumber={chapterNumber}
        onChapterNumberChange={(val) => setChapterNumber(Math.max(1, Number(val) || 1))}
        onClose={() => setIsChapterModalOpen(false)}
        onSubmit={() =>
          activeChapterProject &&
          chapterMutation.mutate({
            pId: activeChapterProject.id,
            payload: { title: chapterTitle.trim(), chapter_number: chapterNumber },
          })
        }
        isSubmitting={chapterMutation.isPending}
      />

      <div className="mx-auto w-full max-w-[1440px]">
        {displayError ? <InlineAlert className="mb-6">{displayError}</InlineAlert> : null}

        <section className="overflow-hidden rounded-[18px] border border-[#e3d2d8] bg-white shadow-[0_18px_40px_-34px_rgba(74,31,44,0.4)]">
          <ProjectsToolbar
            summaryText={summaryText}
            searchTerm={searchTerm}
            onSearchTermChange={(val) => updateUrlParams("search", val)}
            statusFilter={statusFilter}
            onStatusFilterChange={(val) => updateUrlParams("status", val)}
          />

          {isFetchingProjects && !hasProjects ? (
            <div className="p-7 grid gap-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={`skeleton-${index}`}
                  className="h-[74px] rounded-xl border border-gray-100 bg-gradient-to-r from-gray-50 via-white to-gray-50 animate-pulse"
                />
              ))}
            </div>
          ) : null}

          {!isFetchingProjects && projects.length === 0 ? (
            <div className="p-10 sm:p-12">
              <div className="mx-auto flex max-w-[760px] flex-col items-center rounded-[22px] border border-[#ead8df] bg-gradient-to-b from-white to-[#fff7f9] px-6 py-8 text-center shadow-[0_18px_40px_-34px_rgba(74,31,44,0.35)] sm:px-10 sm:py-10">
                <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-brand-text-chip">
                  Welcome
                </p>
                <h2 className="mt-3 text-[28px] font-serif tracking-[-0.02em] text-brand-text-dark sm:text-[34px]">
                  Your workspace is empty.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-brand-text-muted sm:text-base">
                  Start with one project, upload a few pages, then open the editor when you are ready to translate.
                </p>

                <div className="mt-6 grid w-full gap-3 sm:grid-cols-3">
                  {[
                    "1. Create a project",
                    "2. Upload pages",
                    "3. Open the editor",
                  ].map((step) => (
                    <div
                      key={step}
                      className="rounded-xl border border-[#ead8df] bg-white px-4 py-3 text-sm font-medium text-brand-text-dark"
                    >
                      {step}
                    </div>
                  ))}
                </div>

                <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                  <Button onClick={() => navigate("/create")} variant="primary" className="whitespace-nowrap">
                    Create Your First Project
                  </Button>
                </div>
              </div>
            </div>
          ) : null}

          {!isFetchingProjects && projects.length > 0 && filtered.length === 0 ? (
            <div className="p-12 text-center text-brand-text-muted">
              <p className="text-sm font-semibold text-brand-text">No matching projects.</p>
              <p className="text-xs mt-2">Try a different search term or switch the status filter.</p>
              <div className="mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearchParams({});
                  }}
                >
                  Reset Filters
                </Button>
              </div>
            </div>
          ) : null}

          {!isFetchingProjects && filtered.length > 0 ? (
            <div className="flex flex-col">
              {paginated.map((project) => (
                <ProjectRow
                  key={project.id}
                  project={project}
                  isOpening={openingProjectId === project.id}
                  isRouting={uploadingProjectId === project.id}
                  isDeleting={deleteMutation.variables === project.id && deleteMutation.isPending}
                  onOpenEditor={(pId) => void openProjectRoute(pId, "editor")}
                  onOpenUpload={(pId) => void openProjectRoute(pId, "upload")}
                  onAddChapter={(pId, pName) => void openCreateChapterModal(pId, pName)}
                  onDeleteProject={(pId, pName) => {
                    if (window.confirm(`Delete project "${pName}"? This will permanently remove its chapters and pages.`)) {
                      setUiError(null);
                      deleteMutation.mutate(pId);
                    }
                  }}
                />
              ))}
              {totalPages > 1 ? (
                <PaginationControls
                  currentPage={validPage}
                  totalPages={totalPages}
                  onPageChange={(val) => updateUrlParams("page", val.toString())}
                />
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

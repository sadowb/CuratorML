import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useForm,
  FormProvider,
  type SubmitHandler,
  type Resolver,
  useFormContext,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { InlineAlert } from "../components/ui/InlineAlert";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Toggle } from "../components/ui/Toggle";
import { Button } from "../components/ui/Button";
import { createProject } from "../lib/api";
import {
  clearPendingMemoryEntries,
  createMemoryEntriesBatch,
  createStagedMemoryEntry,
  parseBulkMemoryInput,
  savePendingMemoryEntries,
} from "../lib/translationMemoryOnboarding";
import { projectSchema, type ProjectFormData, type ProjectMemoryRowForm } from "../types/forms";
import { cn } from "../lib/utils";
import type { MemoryEntryType } from "../types/api";

function ProjectDetailsSection() {
  const {
    register,
    formState: { errors },
  } = useFormContext<ProjectFormData>();

  return (
    <section className="rounded-2xl border border-brand-border-pink bg-white p-5 flex flex-col gap-3.5 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-[1px] text-brand-text-section">
        01 Project Details
      </h2>

      <div className="flex flex-col gap-3.5">
        <Input
          label="Project Name"
          placeholder="e.g. Naruto"
          {...register("projectName")}
          error={errors.projectName?.message as string}
        />

        <div className="flex flex-col gap-1.5 w-full">
          <label className="text-[11px] font-medium text-brand-text-label tracking-wide">
            Context (optional)
          </label>
          <textarea
            {...register("context")}
            placeholder="Optional plot summary (for example: a short Wikipedia-style recap)."
            rows={4}
            className="w-full resize-none rounded-md border border-[#d8c7cd] bg-white px-3 py-2 text-sm text-[#2d151d] transition-colors placeholder:text-[#9c8f94] focus:outline-none focus-visible:border-[#6b2d3c] focus-visible:ring-1 focus-visible:ring-[#c69aa6]"
          />
          {errors.context && (
            <span className="text-[10px] text-red-500 mt-0.5">
              {errors.context.message as string}
            </span>
          )}
          <p className="text-[10px] text-brand-text-muted">
            Keep this as broad story context; canonical term consistency lives in Translation Memory below.
          </p>
        </div>
      </div>
    </section>
  );
}

function LanguageConfigSection() {
  const { register, watch, setValue } = useFormContext<ProjectFormData>();
  const direction = watch("direction");

  return (
    <section className="rounded-2xl border border-brand-border-pink bg-white p-5 flex flex-col gap-3.5 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-[1px] text-brand-text-section">
        02 Language Configuration
      </h2>

      <div className="flex flex-col gap-3.5">
        <div className="flex w-full gap-5">
          <Select label="Source Language" {...register("sourceLang")}>
            <option value="Japanese">Japanese</option>
            <option value="Korean">Korean</option>
            <option value="Chinese">Chinese</option>
          </Select>
          <Select label="Target Language" {...register("targetLang")}>
            <option value="English (US)">English (US)</option>
            <option value="French">French</option>
            <option value="Spanish">Spanish</option>
          </Select>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-medium text-brand-text-label tracking-wide">
            Translation Direction
          </label>
          <div className="flex">
            <button
              type="button"
              onClick={() => setValue("direction", "LTR")}
              className={cn(
                "flex-1 px-5 py-2 border border-r-0 rounded-l-md text-[13px] font-semibold transition-all",
                direction === "LTR"
                  ? "border-[#6b2d3c] bg-[#6b2d3c] text-white"
                  : "border-[#d8c7cd] bg-white text-[#6e5b62] hover:bg-[#f7ecef]",
              )}
              aria-pressed={direction === "LTR"}
            >
              LTR
            </button>
            <button
              type="button"
              onClick={() => setValue("direction", "RTL")}
              className={cn(
                "flex-1 px-5 py-2 border rounded-r-md text-[13px] font-medium transition-all",
                direction === "RTL"
                  ? "border-[#6b2d3c] bg-[#6b2d3c] text-white"
                  : "border-[#d8c7cd] bg-white text-[#6e5b62] hover:bg-[#f7ecef]",
              )}
              aria-pressed={direction === "RTL"}
            >
              Keep original balloons (RTL)
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function ChapterMetadataSection() {
  const {
    register,
    formState: { errors },
  } = useFormContext<ProjectFormData>();

  return (
    <section className="rounded-2xl border border-brand-border-pink bg-white p-5 flex flex-col gap-3.5 shadow-sm overflow-visible">
      <h2 className="text-xs font-semibold uppercase tracking-[1px] text-brand-text-section">
        03 Chapter Metadata
      </h2>

      <div className="flex flex-col gap-3.5">
        <div className="flex w-full gap-5">
          <Input
            label="Chapter Title"
            placeholder="Chapter 41 - Night Market"
            {...register("chapterTitle")}
            error={errors.chapterTitle?.message as string}
          />
          <Input
            type="number"
            label="Chapter Number"
            placeholder="41"
            {...register("chapterNumber")}
            error={errors.chapterNumber?.message as string}
          />
        </div>

        <div className="flex w-full gap-5">
          <Input
            type="number"
            label="Estimated Pages (optional)"
            placeholder="48"
            {...register("estimatedPages")}
            error={errors.estimatedPages?.message as string}
          />
          <div className="flex-1 rounded-md border border-[#e3d2d8] bg-[#fff9fb] px-3 py-2 text-xs leading-relaxed text-[#6e5b62]">
            Leave blank to auto-detect from uploaded page count.
          </div>
        </div>
      </div>
    </section>
  );
}

interface TranslationMemorySectionProps {
  rows: ProjectMemoryRowForm[];
  onAddRow: (row: Omit<ProjectMemoryRowForm, "id">) => void;
  onUpdateRow: (id: string, row: Omit<ProjectMemoryRowForm, "id">) => void;
  onRemoveRow: (id: string) => void;
}

function TranslationMemorySection({
  rows,
  onAddRow,
  onUpdateRow,
  onRemoveRow,
}: TranslationMemorySectionProps) {
  const { watch } = useFormContext<ProjectFormData>();
  const chapterNumber = watch("chapterNumber");
  const [entryType, setEntryType] = useState<MemoryEntryType>("character");
  const [scopeMode, setScopeMode] = useState<"project" | "chapter">("project");
  const [sourceTerm, setSourceTerm] = useState("");
  const [preferredTranslation, setPreferredTranslation] = useState("");
  const [aliasesText, setAliasesText] = useState("");
  const [notes, setNotes] = useState("");
  const [bulkDraft, setBulkDraft] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [bulkErrors, setBulkErrors] = useState<string[]>([]);
  const [editingRowId, setEditingRowId] = useState<string | null>(null);

  const resetQuickAdd = () => {
    setSourceTerm("");
    setPreferredTranslation("");
    setAliasesText("");
    setNotes("");
    setScopeMode("project");
    setEntryType("character");
    setEditingRowId(null);
  };

  const buildDraftFromInputs = (): Omit<ProjectMemoryRowForm, "id"> => ({
    entry_type: entryType,
    scope_mode: scopeMode,
    source_term: sourceTerm.trim(),
    preferred_translation: preferredTranslation.trim(),
    aliases: aliasesText
      .split(",")
      .map((alias) => alias.trim())
      .filter(Boolean),
    notes: notes.trim() || "",
  });

  const handleAddOrUpdateSingle = () => {
    if (!sourceTerm.trim() || !preferredTranslation.trim()) {
      setAddError("Source term and preferred translation are required.");
      return;
    }
    const draft = buildDraftFromInputs();
    if (editingRowId) {
      onUpdateRow(editingRowId, draft);
    } else {
      onAddRow(draft);
    }
    setAddError(null);
    resetQuickAdd();
  };

  const handleParseBulk = () => {
    const parsed = parseBulkMemoryInput(bulkDraft);
    setBulkErrors(parsed.errors);
    if (parsed.validEntries.length > 0) {
      parsed.validEntries.forEach(onAddRow);
      setBulkDraft("");
    }
  };

  const handleEditRow = (row: ProjectMemoryRowForm) => {
    setEditingRowId(row.id);
    setEntryType(row.entry_type);
    setScopeMode(row.scope_mode);
    setSourceTerm(row.source_term);
    setPreferredTranslation(row.preferred_translation);
    setAliasesText(row.aliases.join(", "));
    setNotes(row.notes ?? "");
    setAddError(null);
  };

  return (
    <section className="rounded-2xl border border-brand-border-pink bg-white p-5 flex flex-col gap-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-[1px] text-brand-text-section">
        04 Translation Memory
      </h2>

      <p className="text-xs leading-relaxed text-brand-text-muted">
        Add canonical terms now so translation stays consistent. Use chapter scope only for temporary chapter-specific context.
      </p>

      <div className="grid grid-cols-2 gap-3 rounded-xl border border-[#ecdce1] bg-[#fff9fb] p-3">
        <Select
          label="Type"
          value={entryType}
          onChange={(event) => setEntryType(event.target.value as MemoryEntryType)}
        >
          <option value="character">Character</option>
          <option value="attack">Attack</option>
          <option value="place">Place</option>
          <option value="organization">Organization</option>
        </Select>
        <Select
          label="Scope"
          value={scopeMode}
          onChange={(event) => setScopeMode(event.target.value as "project" | "chapter")}
        >
          <option value="project">Project</option>
          <option value="chapter">Chapter</option>
        </Select>
        <Input
          label="Source Term"
          placeholder="ゾロ"
          value={sourceTerm}
          onChange={(event) => setSourceTerm(event.target.value)}
          containerClassName="col-span-1"
        />
        <Input
          label="Preferred Translation"
          placeholder="Zoro"
          value={preferredTranslation}
          onChange={(event) => setPreferredTranslation(event.target.value)}
          containerClassName="col-span-1"
        />
        <Input
          label="Aliases (comma-separated)"
          placeholder="ゾロー, Roronoa Zoro"
          value={aliasesText}
          onChange={(event) => setAliasesText(event.target.value)}
          containerClassName="col-span-2"
        />
        <Input
          label="Notes (optional)"
          placeholder="Use this spelling canon."
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          containerClassName="col-span-2"
        />
        <div className="col-span-2 flex items-center justify-between gap-3">
          <span className="text-[10px] text-brand-text-muted">
            {scopeMode === "chapter"
              ? `Will apply to chapter ${chapterNumber}.`
              : "Will apply project-wide."}
          </span>
          <div className="flex items-center gap-2">
            {editingRowId ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={resetQuickAdd}
              >
                Cancel Edit
              </Button>
            ) : null}
            <Button type="button" size="sm" onClick={handleAddOrUpdateSingle}>
              {editingRowId ? "Save Changes" : "Add Row"}
            </Button>
          </div>
        </div>
        {addError ? <p className="col-span-2 text-[10px] text-red-500">{addError}</p> : null}
      </div>

      <div className="rounded-xl border border-[#ecdce1] bg-[#fffdfd] p-3">
        <label className="text-[11px] font-medium text-brand-text-label tracking-wide">
          Bulk Paste Helper
        </label>
        <textarea
          value={bulkDraft}
          onChange={(event) => setBulkDraft(event.target.value)}
          placeholder={`ゾロ -> Zoro | type=character | aliases=ゾロー\n鬼斬り -> Oni Giri | type=attack\n海軍 -> Marines | type=organization | scope=chapter`}
          rows={5}
          className="mt-1.5 w-full resize-y rounded-md border border-[#d8c7cd] bg-white px-3 py-2 text-sm text-[#2d151d] placeholder:text-[#9c8f94] focus:outline-none focus-visible:border-[#6b2d3c] focus-visible:ring-1 focus-visible:ring-[#c69aa6]"
        />
        <div className="mt-2 flex items-center justify-between">
          <p className="text-[10px] text-brand-text-muted">
            Format: <code>source -&gt; preferred</code>, optional <code>| type=...</code>, <code>| aliases=a,b</code>, <code>| scope=chapter</code>.
          </p>
          <Button type="button" size="sm" variant="outline" onClick={handleParseBulk}>
            Parse & Add
          </Button>
        </div>
        {bulkErrors.length > 0 ? (
          <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-2">
            {bulkErrors.map((error) => (
              <p key={error} className="text-[10px] text-red-600">
                {error}
              </p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-[#ecdce1] bg-[#fffdfd] p-3">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-[12px] font-semibold text-brand-text-dark">
            Staged Entries ({rows.length})
          </h3>
          <span className="text-[10px] text-brand-text-muted">
            Saved after project creation
          </span>
        </div>
        {rows.length === 0 ? (
          <p className="text-[11px] text-brand-text-muted">No staged memory entries yet.</p>
        ) : (
          <div className="flex max-h-[220px] flex-col gap-2 overflow-y-auto">
            {rows.map((row) => (
              <div
                key={row.id}
                className="rounded-md border border-[#ead8df] bg-white p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-[12px] font-bold text-brand-text-dark">
                      {row.source_term} {"->"} {row.preferred_translation}
                    </p>
                    <p className="text-[10px] uppercase tracking-wide text-brand-text-muted">
                      {row.entry_type} • {row.scope_mode}
                    </p>
                    {row.aliases.length > 0 ? (
                      <p className="text-[10px] text-brand-text-muted">
                        Aliases: {row.aliases.join(", ")}
                      </p>
                    ) : null}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[10px]"
                    onClick={() => handleEditRow(row)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-[10px]"
                    onClick={() => onRemoveRow(row.id)}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function WorkflowSettingsSection() {
  const { watch, setValue } = useFormContext<ProjectFormData>();
  const enableOcr = watch("enableOcr");
  const requireQc = watch("requireQc");

  return (
    <section className="flex flex-col gap-3 rounded-[18px] border border-[#e3d2d8] bg-[#fffdfd] p-4 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.4)]">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6b2d3c]">
        05 Workflow Settings
      </h2>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between rounded-xl border border-[#ecdce1] bg-[#fff6f8] p-3">
          <span className="font-semibold text-[13px] text-brand-text-dark">
            Enable OCR pre-processing
          </span>
          <Toggle
            active={enableOcr}
            onToggle={() => setValue("enableOcr", !enableOcr)}
            label="Enable OCR pre-processing"
          />
        </div>

        <div className="flex items-center justify-between rounded-xl border border-[#ecdce1] bg-[#fff6f8] p-3">
          <span className="font-semibold text-[13px] text-brand-text-dark">
            Require quality-check pass
          </span>
          <Toggle
            active={requireQc}
            onToggle={() => setValue("requireQc", !requireQc)}
            label="Require quality-check pass"
          />
        </div>
      </div>
    </section>
  );
}

function FormActions({ isSubmitting = false }: { isSubmitting?: boolean }) {
  const navigate = useNavigate();

  return (
    <section className="flex flex-col gap-3 rounded-[18px] border border-[#e3d2d8] bg-[#fff9fb] p-4 shadow-[0_18px_40px_-34px_rgba(74,31,44,0.4)]">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6b2d3c]">
        Primary Action
      </h2>

      <p className="text-xs font-medium leading-relaxed text-[#6e5b62]">
        We create the project first, then save staged translation memory entries before redirecting to upload.
      </p>

      <div className="flex items-center gap-2.5 w-full mt-1">
        <Button
          type="submit"
          disabled={isSubmitting}
          className="flex-1 rounded-full bg-[#6b2d3c] px-4 py-3 text-[13px] font-bold text-white shadow-md transition-all hover:bg-[#572430] active:scale-[0.98] disabled:opacity-70"
        >
          {isSubmitting ? "Creating Project..." : "Create Project & Start Upload"}
        </Button>
        <Button
          type="button"
          onClick={() => navigate("/dashboard")}
          variant="outline"
          className="rounded-full border border-[#d8c7cd] bg-white px-5 py-3 text-[13px] font-semibold text-[#2d151d] transition-colors hover:bg-[#f7ecef]"
        >
          Cancel
        </Button>
      </div>
    </section>
  );
}

export default function CreateProject() {
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [memoryRows, setMemoryRows] = useState<ProjectMemoryRowForm[]>([]);

  const methods = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema) as Resolver<ProjectFormData>,
    defaultValues: {
      projectName: "",
      sourceLang: "Japanese",
      targetLang: "English (US)",
      direction: "LTR",
      chapterTitle: "",
      chapterNumber: 1,
      estimatedPages: undefined,
      context: "",
      enableOcr: true,
      requireQc: true,
    },
  });

  const {
    handleSubmit,
    formState: { isSubmitting },
  } = methods;

  const onAddMemoryRow = (row: Omit<ProjectMemoryRowForm, "id">) => {
    setMemoryRows((prev) => [...prev, createStagedMemoryEntry(row)]);
  };

  const onRemoveMemoryRow = (id: string) => {
    setMemoryRows((prev) => prev.filter((row) => row.id !== id));
  };

  const onUpdateMemoryRow = (
    id: string,
    updated: Omit<ProjectMemoryRowForm, "id">,
  ) => {
    setMemoryRows((prev) =>
      prev.map((row) =>
        row.id === id
          ? {
              ...row,
              ...updated,
            }
          : row,
      ),
    );
  };

  const onSubmit: SubmitHandler<ProjectFormData> = async (data) => {
    setSubmitError(null);

    try {
      const response = await createProject({
        name: data.projectName,
        source_language: data.sourceLang,
        target_language: data.targetLang,
        reading_direction: data.direction,
        chapter_title: data.chapterTitle,
        chapter_number: data.chapterNumber,
        estimated_pages: data.estimatedPages,
        context: data.context || undefined,
        enable_ocr: data.enableOcr,
        require_qc: data.requireQc,
      });

      let failedRows: ProjectMemoryRowForm[] = [];
      if (memoryRows.length > 0) {
        const result = await createMemoryEntriesBatch(
          response.project.id,
          response.chapter.chapter_number,
          memoryRows,
          4,
        );
        failedRows = result.failed.map((item) => item.entry);
      }

      if (failedRows.length > 0) {
        savePendingMemoryEntries(response.project.id, failedRows);
      } else {
        clearPendingMemoryEntries(response.project.id);
      }

      const params = new URLSearchParams({
        chapterId: response.chapter.id,
      });
      if (failedRows.length > 0) {
        params.set("memoryRetry", "1");
        params.set("memoryFailedCount", String(failedRows.length));
      }

      navigate(`/projects/${response.project.id}/upload?${params.toString()}`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to create project";
      setSubmitError(message);
    }
  };

  return (
    <FormProvider {...methods}>
      <div className="flex h-full w-full overflow-hidden bg-[#f6f2f4]">
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="scrollbar-hide mx-auto flex h-full w-full max-w-[1440px] flex-1 flex-col gap-7 overflow-y-auto bg-[#fffdfd] px-10 py-9"
        >
          <div className="flex w-full flex-col gap-2.5">
            <span className="text-[11px] font-semibold uppercase tracking-[1.2px] text-brand-text-section">
              Project Setup
            </span>
            <h1 className="text-[40px] font-serif font-medium tracking-[-1px] text-brand-text-dark">
              Create Manga Translation Project
            </h1>
            <p className="w-full text-sm leading-relaxed text-brand-text-muted">
              Configure project details and canonical translation memory, then continue to upload and editor review.
            </p>
          </div>

          {submitError ? <InlineAlert>{submitError}</InlineAlert> : null}

          <div className="flex h-full w-full min-h-0 min-w-0 items-start gap-7">
            <div className="flex min-w-0 flex-1 flex-col gap-6">
              <ProjectDetailsSection />
              <LanguageConfigSection />
              <ChapterMetadataSection />
              <TranslationMemorySection
                rows={memoryRows}
                onAddRow={onAddMemoryRow}
                onUpdateRow={onUpdateMemoryRow}
                onRemoveRow={onRemoveMemoryRow}
              />
            </div>

            <div className="flex w-[380px] shrink-0 flex-col gap-5 pb-5">
              <WorkflowSettingsSection />
              <FormActions isSubmitting={isSubmitting} />
            </div>
          </div>
        </form>
      </div>
    </FormProvider>
  );
}

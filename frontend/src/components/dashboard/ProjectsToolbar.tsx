import { Search } from "lucide-react";

export type ProjectStatusFilter = "all" | "active" | "completed" | "archived";

const STATUS_FILTERS: Array<{ value: ProjectStatusFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

interface ProjectsToolbarProps {
  summaryText: string;
  searchTerm: string;
  onSearchTermChange: (nextValue: string) => void;
  statusFilter: ProjectStatusFilter;
  onStatusFilterChange: (nextFilter: ProjectStatusFilter) => void;
}

export function ProjectsToolbar({
  summaryText,
  searchTerm,
  onSearchTermChange,
  statusFilter,
  onStatusFilterChange,
}: ProjectsToolbarProps) {
  return (
    <div className="flex flex-col gap-5 border-b border-[#eadde1] bg-[#fff9fb] p-5 lg:p-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#6b2d3c]">
          Projects
        </h2>
        <div className="text-xs text-[#6e5b62]">{summaryText}</div>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <label
          htmlFor="project-search"
          className="relative flex-1 min-w-[220px]"
        >
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a7a80]"
            aria-hidden="true"
          />
          <input
            id="project-search"
            type="search"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
            placeholder="Search project, language, or status..."
            className="h-11 w-full rounded-xl border border-[#d8c7cd] bg-white pl-10 pr-3 text-sm text-[#2d151d] transition-colors focus:outline-none focus-visible:border-[#6b2d3c] focus-visible:ring-2 focus-visible:ring-[#c69aa6]"
          />
        </label>
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {STATUS_FILTERS.map((filter) => {
            const isActive = statusFilter === filter.value;
            return (
              <button
                key={filter.value}
                type="button"
                onClick={() => onStatusFilterChange(filter.value)}
                className={`h-8 px-3 rounded-full text-xs font-bold border transition-colors whitespace-nowrap ${
                  isActive
                    ? "border-[#6b2d3c] bg-[#6b2d3c] text-white"
                    : "border-[#d8c7cd] bg-white text-[#6e5b62] hover:bg-[#f7ecef]"
                }`}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

import Pagination from "react-responsive-pagination";

import "react-responsive-pagination/themes/classic.css";
import "./PaginationOverride.css"; // We'll create this to match brand styles

interface PaginationControlsProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (nextPage: number) => void;
}

export function PaginationControls({
  currentPage,
  totalPages,
  onPageChange,
}: PaginationControlsProps) {
  return (
    <nav
      aria-label="Projects pagination"
      className="px-6 lg:px-7 py-4 bg-brand-surface-muted/60 border-t border-brand-border flex justify-center"
    >
      <Pagination
        current={currentPage}
        total={totalPages}
        onPageChange={onPageChange}
      />
    </nav>
  );
}

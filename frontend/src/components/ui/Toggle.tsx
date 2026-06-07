import React from "react";
import { cn } from "../../lib/utils";

interface ToggleProps {
  active: boolean;
  onToggle: () => void;
  label: string;
  className?: string;
}

export const Toggle = React.forwardRef<HTMLButtonElement, ToggleProps>(
  ({ active, onToggle, label, className }, ref) => (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={active}
      aria-label={label}
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full",
        "border-2 border-transparent transition-colors duration-200 ease-in-out",
        "focus-visible:ring-2 focus-visible:ring-brand-maroon focus-visible:ring-offset-2 focus:outline-none",
        active ? "bg-brand-maroon" : "bg-gray-300",
        className,
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white",
          "shadow-sm ring-0 transition duration-200 ease-in-out",
          active ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  ),
);
Toggle.displayName = "Toggle";

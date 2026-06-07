import React from "react";
import { cn } from "../../lib/utils";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, children, ...props }, ref) => {
    return (
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        {label && (
          <label className="text-[11px] font-medium text-brand-text-label tracking-wide">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            className={cn(
              "h-10 w-full appearance-none rounded-md border border-brand-border-form bg-white px-3 pr-8 text-sm text-brand-text-dark focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-maroon focus-visible:border-brand-maroon transition-colors font-medium",
              error && "border-red-500",
              className,
            )}
            ref={ref}
            {...props}
          >
            {children}
          </select>
          <span
            className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-brand-text-placeholder text-[10px]"
            aria-hidden="true"
          >
            ▼
          </span>
        </div>
        {error && (
          <span className="text-[10px] text-red-500 mt-0.5">{error}</span>
        )}
      </div>
    );
  },
);
Select.displayName = "Select";

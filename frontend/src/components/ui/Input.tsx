import React from "react";
import { cn } from "../../lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  containerClassName?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    { className, type = "text", label, error, containerClassName, ...props },
    ref,
  ) => {
    return (
      <div
        className={cn(
          "flex flex-col gap-1.5 min-w-0 flex-1",
          containerClassName,
        )}
      >
        {label && (
          <label className="text-[11px] font-medium text-brand-text-label tracking-wide">
            {label}
          </label>
        )}
        <input
          type={type}
          className={cn(
            "h-10 w-full rounded-md border border-brand-border-form bg-white px-3 text-sm text-brand-text-dark focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-maroon focus-visible:border-brand-maroon transition-colors font-medium placeholder:text-brand-text-placeholder",
            error && "border-red-500",
            className,
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <span className="text-[10px] text-red-500 mt-0.5">{error}</span>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";

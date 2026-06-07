import React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "warning" | "success" | "outline" | "ghost";
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  const variants = {
    default:
      "bg-brand-surface-pinkAlt text-brand-text-maroon border-brand-border-sidebar",
    warning:
      "bg-brand-surface-progressBg text-brand-text-goldDark border-brand-border-yellowStrong",
    success: "bg-[#e8fccf] text-[#5d850e] border-[#d8f7b7]",
    outline: "bg-transparent text-gray-600 border-gray-200",
    ghost:
      "bg-brand-surface-uploadBg text-brand-maroon border-brand-border-pinkLight",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-3.5 py-1 text-[11px] font-bold rounded-full border shadow-sm tracking-wide",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

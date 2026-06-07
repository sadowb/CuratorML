import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

type InlineAlertVariant = "error" | "info" | "success";

interface InlineAlertProps {
  variant?: InlineAlertVariant;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<InlineAlertVariant, string> = {
  error: "border-red-200 bg-red-50 text-red-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  success: "border-green-200 bg-green-50 text-green-700",
};

export function InlineAlert({
  variant = "error",
  children,
  className,
}: InlineAlertProps) {
  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3 text-sm",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </div>
  );
}

import React from "react";
import { cn } from "../../lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "yellow";
  size?: "sm" | "md" | "lg" | "pill" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-bold tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c69aa6] focus-visible:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap";

    const variants = {
      primary:
        "rounded-full bg-[#6b2d3c] text-white shadow-sm hover:bg-[#572430]",
      secondary:
        "rounded-full border border-[#d8c7cd] bg-[#fff7f8] text-[#2d151d] shadow-sm hover:bg-[#f7ecef]",
      outline:
        "rounded-full border border-[#d8c7cd] bg-white text-[#2d151d] shadow-sm hover:bg-[#f7ecef]",
      ghost: "rounded-full bg-transparent text-[#2d151d] hover:bg-[#f7ecef]",
      yellow:
        "rounded-full bg-[#f0d37b] text-[#2d151d] shadow-sm hover:brightness-105",
    };

    const sizes = {
      sm: "h-8 px-4 text-xs",
      md: "h-11 px-6 text-sm",
      lg: "h-12 px-8 text-[15px]",
      pill: "h-[34px] px-5 rounded-full text-xs",
      icon: "h-9 w-9 rounded-md",
    };

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

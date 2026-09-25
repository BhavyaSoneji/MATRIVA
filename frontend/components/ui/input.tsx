import * as React from "react";
import { cn } from "@/lib/utils";

/* Fields are underlines, not boxes — the grid already supplies the structure. */
const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-11 w-full rounded-none border-0 border-b border-border bg-transparent px-0 py-2 text-base text-foreground transition-colors placeholder:text-muted-foreground/70 focus-visible:border-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/*
  Badges are typographic marks, not filled pills. Meaning is carried by the
  glyph the caller supplies (◆ ◇ ○ ▲) as much as by hue, so they stay readable
  in grayscale and for colour-blind readers.
*/
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-none text-[9.5px] font-bold uppercase tracking-[0.14em] leading-none",
  {
    variants: {
      variant: {
        default: "bg-primary px-2.5 py-1.5 text-primary-foreground",
        secondary: "text-muted-foreground",
        outline: "border border-border px-2.5 py-1.5 text-muted-foreground",
        success: "text-success",
        warning: "text-warning",
        destructive: "text-destructive",
        traditional: "text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };

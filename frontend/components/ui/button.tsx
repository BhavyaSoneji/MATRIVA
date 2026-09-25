import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-none border border-transparent font-bold tracking-[0.1em] uppercase transition-[transform,box-shadow,background-color,color] duration-200 ease-editorial disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-card hover:-translate-y-0.5 hover:shadow-float",
        secondary: "bg-secondary text-secondary-foreground hover:bg-sage-200",
        outline: "border-border bg-transparent hover:border-accent hover:text-accent",
        ghost: "hover:bg-muted",
        destructive: "bg-destructive text-destructive-foreground hover:-translate-y-0.5",
        link: "normal-case tracking-normal font-semibold text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 px-6 text-[12px]",
        sm: "h-9 px-4 text-[11px]",
        lg: "h-14 px-8 text-[13px]",
        icon: "h-11 w-11 px-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };

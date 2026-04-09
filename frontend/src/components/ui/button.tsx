import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[10px] text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 hover:rounded-[20px] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[var(--color-accent)] px-4 py-2 text-[var(--color-accent-foreground)] shadow-sm hover:opacity-90",
        secondary: "border border-[var(--color-border)] bg-white px-4 py-2 text-[var(--color-foreground)] hover:bg-[var(--color-panel-muted)]",
        outline: "border border-[var(--color-border)] bg-transparent px-4 py-2 text-[var(--color-foreground)] hover:bg-[var(--color-panel-muted)]",
        ghost: "px-3 py-2 text-[var(--color-muted-foreground)] hover:bg-black/5",
        danger: "bg-[var(--color-danger)] px-4 py-2 text-white hover:opacity-90",
      },
      size: {
        default: "h-10",
        sm: "h-8 px-3 text-xs",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/15 text-primary ring-1 ring-inset ring-primary/30",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-transparent bg-destructive/15 text-destructive ring-1 ring-inset ring-destructive/40",
        success:
          "border-transparent bg-success/15 text-success ring-1 ring-inset ring-success/30 dark:text-[hsl(var(--success))]",
        warning:
          "border-transparent bg-warning/15 text-warning ring-1 ring-inset ring-warning/30 dark:text-[hsl(var(--warning))]",
        info:
          "border-transparent bg-muted text-muted-foreground ring-1 ring-inset ring-border",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }

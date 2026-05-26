import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface ChartCardProps {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function ChartCard({
  title,
  description,
  action,
  children,
  className,
}: ChartCardProps) {
  return (
    <section
      className={cn(
        'flex flex-col rounded-lg border border-border/80 bg-card',
        className,
      )}
    >
      <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold tracking-tight text-foreground">
            {title}
          </h3>
          {description && (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </header>
      <div className="flex flex-1 flex-col px-2 pb-3 pt-4">{children}</div>
    </section>
  )
}

interface ChartEmptyProps {
  message: string
  className?: string
}

export function ChartEmpty({ message, className }: ChartEmptyProps) {
  return (
    <div
      className={cn(
        'flex h-full min-h-[180px] items-center justify-center px-4 text-center text-xs text-muted-foreground',
        className,
      )}
    >
      {message}
    </div>
  )
}

interface ChartSkeletonProps {
  className?: string
}

export function ChartSkeleton({ className }: ChartSkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn(
        'flex h-full min-h-[180px] animate-pulse items-end gap-2 px-4 pb-2',
        className,
      )}
    >
      {[40, 65, 35, 80, 50, 70, 45, 60, 55, 75].map((h, i) => (
        <span
          key={i}
          className="flex-1 rounded bg-muted"
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  )
}

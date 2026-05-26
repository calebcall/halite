import type { TooltipContentProps } from 'recharts'

import { cn } from '@/lib/utils'

// Recharts injects `active`, `payload`, etc. at render time (it clones the
// element passed to `content`), so they need to be optional on the prop type
// even though recharts marks them required. Everything else here is ours.
type ChartTooltipProps = Partial<TooltipContentProps<number, string>> & {
  /** Optional override for the title row (defaults to the data point's label). */
  titleFormatter?: (label: unknown) => string
  /** Optional formatter for each series value. */
  valueFormatter?: (value: number, name: string) => string
  /** When true, hide the colored dot next to each row. */
  hideIndicator?: boolean
  className?: string
}

export function ChartTooltip({
  active,
  payload,
  label,
  titleFormatter,
  valueFormatter,
  hideIndicator,
  className,
}: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const title = titleFormatter ? titleFormatter(label) : String(label ?? '')
  return (
    <div
      role="tooltip"
      className={cn(
        'min-w-[8rem] rounded-md border border-border/80 bg-popover/95 px-3 py-2 text-xs shadow-lg shadow-black/30 backdrop-blur',
        className,
      )}
    >
      {title && (
        <div className="mb-1 font-medium text-foreground">{title}</div>
      )}
      <div className="flex flex-col gap-0.5">
        {payload.map((entry, i) => {
          const name = entry.name ?? ''
          const value = typeof entry.value === 'number' ? entry.value : 0
          const formatted = valueFormatter
            ? valueFormatter(value, String(name))
            : value.toLocaleString()
          const color =
            (entry.payload as { fill?: string } | undefined)?.fill ??
            entry.color
          return (
            <div key={`${name}-${i}`} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                {!hideIndicator && (
                  <span
                    aria-hidden
                    className="h-2 w-2 rounded-[2px]"
                    style={{ backgroundColor: color }}
                  />
                )}
                {name || 'Value'}
              </span>
              <span className="font-medium tabular-nums text-foreground">
                {formatted}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

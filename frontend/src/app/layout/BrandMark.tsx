import { cn } from '@/lib/utils'

interface BrandMarkProps {
  /** Sizing classes (e.g. "h-8 w-8") for the rendered SVG. */
  className?: string
  /** Override the default `text-primary` color via Tailwind text-* class. */
  toneClassName?: string
}

/**
 * Halite "lattice" brand mark — a 3×3 grid of rounded amber squares.
 *
 * The source SVG (logos/brand/lattice/icon.svg) uses a 512×512 viewBox with
 * generous padding for standalone use. For inline use next to text we
 * crop to the content bounds (98..414 on both axes) so the mark fills
 * its container instead of floating in negative space.
 *
 * Fill is `currentColor`, so callers can recolor with Tailwind's text-*
 * utilities; defaults to the brand amber via `text-primary`.
 */
export function BrandMark({ className, toneClassName }: BrandMarkProps) {
  return (
    <svg
      viewBox="98 98 316 316"
      fill="currentColor"
      className={cn(toneClassName ?? 'text-primary', className)}
      aria-hidden
      role="img"
    >
      <rect x="208" y="208" width="96" height="96" rx="18" />
      <rect x="226" y="98" width="60" height="60" rx="12" />
      <rect x="354" y="226" width="60" height="60" rx="12" />
      <rect x="226" y="354" width="60" height="60" rx="12" />
      <rect x="98" y="226" width="60" height="60" rx="12" />
      <g fillOpacity="0.55">
        <rect x="103" y="103" width="50" height="50" rx="10" />
        <rect x="359" y="103" width="50" height="50" rx="10" />
        <rect x="359" y="359" width="50" height="50" rx="10" />
        <rect x="103" y="359" width="50" height="50" rx="10" />
      </g>
    </svg>
  )
}

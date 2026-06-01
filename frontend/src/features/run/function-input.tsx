import { useEffect, useMemo, useRef, useState } from 'react'

import { Input } from '@/components/ui/input'

const MAX_RESULTS = 10

export interface FunctionInputProps {
  value: string
  onChange: (value: string) => void
  functions: string[]
  id?: string
  placeholder?: string
  required?: boolean
  className?: string
  autoComplete?: string
}

export function FunctionInput({
  value,
  onChange,
  functions,
  id,
  placeholder,
  required,
  className,
  autoComplete = 'off',
}: FunctionInputProps) {
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [prevMatchCount, setPrevMatchCount] = useState(0)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Filter: case-insensitive substring match; cap at MAX_RESULTS.
  const matches = useMemo(() => {
    const q = value.trim().toLowerCase()
    if (!q) {
      return functions.slice(0, MAX_RESULTS)
    }
    const out: string[] = []
    for (const fn of functions) {
      if (fn.toLowerCase().includes(q)) {
        out.push(fn)
        if (out.length >= MAX_RESULTS) break
      }
    }
    return out
  }, [value, functions])

  // Close the dropdown when clicking outside.
  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (!wrapperRef.current) return
      if (!wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  // Reset highlight when the matches set changes. Adjusting state during
  // render (rather than in an effect) avoids a cascading re-render.
  if (matches.length !== prevMatchCount) {
    setPrevMatchCount(matches.length)
    setHighlighted(0)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((h) => Math.min(h + 1, matches.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter' && open && matches[highlighted]) {
      e.preventDefault()
      onChange(matches[highlighted])
      setOpen(false)
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <Input
        id={id}
        required={required}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className={className}
        autoComplete={autoComplete}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={id ? `${id}-listbox` : undefined}
      />
      {open && matches.length > 0 && (
        <ul
          id={id ? `${id}-listbox` : undefined}
          role="listbox"
          className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border bg-popover py-1 text-sm shadow-md"
        >
          {matches.map((fn, idx) => (
            <li
              key={fn}
              role="option"
              aria-selected={idx === highlighted}
              className={`cursor-pointer px-3 py-1.5 font-mono text-xs ${
                idx === highlighted ? 'bg-accent text-accent-foreground' : ''
              }`}
              onMouseDown={(e) => {
                // mousedown (not click) so the input doesn't lose focus
                // before we can update state
                e.preventDefault()
                onChange(fn)
                setOpen(false)
              }}
              onMouseEnter={() => setHighlighted(idx)}
            >
              {fn}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

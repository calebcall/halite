// frontend/src/features/jobs/timeline-filters.tsx
import { Search } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'


export type TimelineFiltersValue = {
  function_filter: string
  group_by: 'function' | 'user'
  include_system: boolean
  user: string
  window: '1h' | '4h' | '24h' | '7d'
}


export function TimelineFilters({
  value,
  onChange,
}: {
  value: TimelineFiltersValue
  onChange: (next: TimelineFiltersValue) => void
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3">
      <div className="space-y-1">
        <Label className="text-xs">Window</Label>
        <Select
          value={value.window}
          onValueChange={(v) =>
            onChange({ ...value, window: v as TimelineFiltersValue['window'] })
          }
        >
          <SelectTrigger className="h-8 w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1h">1 hour</SelectItem>
            <SelectItem value="4h">4 hours</SelectItem>
            <SelectItem value="24h">24 hours</SelectItem>
            <SelectItem value="7d">7 days</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Group by</Label>
        <Select
          value={value.group_by}
          onValueChange={(v) =>
            onChange({ ...value, group_by: v as TimelineFiltersValue['group_by'] })
          }
        >
          <SelectTrigger className="h-8 w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="function">Function</SelectItem>
            <SelectItem value="user">User</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="min-w-[180px] flex-1 space-y-1">
        <Label className="text-xs" htmlFor="timeline-function-filter">
          Function filter
        </Label>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="timeline-function-filter"
            className="h-8 pl-7"
            placeholder="state, cmd, pkg…"
            value={value.function_filter}
            onChange={(e) => onChange({ ...value, function_filter: e.target.value })}
          />
        </div>
      </div>
      <div className="min-w-[140px] space-y-1">
        <Label className="text-xs" htmlFor="timeline-user-filter">
          User
        </Label>
        <Input
          id="timeline-user-filter"
          className="h-8"
          placeholder="any"
          value={value.user}
          onChange={(e) => onChange({ ...value, user: e.target.value })}
        />
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id="timeline-include-system"
          checked={value.include_system}
          onCheckedChange={(c) => onChange({ ...value, include_system: c })}
        />
        <Label htmlFor="timeline-include-system" className="text-xs">
          Include system
        </Label>
      </div>
    </div>
  )
}

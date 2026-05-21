// frontend/src/features/auth/use-has-perm.ts
import { useCurrentUser } from './use-current-user'

/**
 * Returns true iff the current user has at least one permission
 * matching (verb, resource). Matches the backend's fnmatch-style
 * semantics from halite/rbac/engine.py.
 *
 * When the current-user query is still pending or has no user (logged
 * out), this returns false — call sites should branch on the auth
 * state explicitly if they need to distinguish "no user yet" from
 * "no permission".
 */
export function useHasPerm(verb: string, resource: string): boolean {
  const { data } = useCurrentUser()
  if (!data || !data.permissions) return false
  for (const p of data.permissions) {
    if (matchesGlob(p.verb, verb) && matchesGlob(p.resource_glob, resource)) {
      return true
    }
  }
  return false
}

/** fnmatch-style glob: `*` matches any chars, `?` matches one char.
 *  Anchored — the entire string must match. */
export function matchesGlob(pattern: string, value: string): boolean {
  let regex = ''
  for (const ch of pattern) {
    if (ch === '*') regex += '.*'
    else if (ch === '?') regex += '.'
    else regex += ch.replace(/[.+^${}()|[\]\\]/g, '\\$&')
  }
  return new RegExp(`^${regex}$`).test(value)
}

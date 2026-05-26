// frontend/src/features/inventory/api.ts
//
// Typed wrappers for /api/inventory/*. Types are defined inline here rather
// than pulled from `types.gen.ts` because the backend's OpenAPI hasn't been
// regenerated yet. Once `npm run gen:types` is rerun against a backend with
// the new routes, these can be swapped for
// `paths['/api/inventory/...']['post']['responses']['200']['content']['application/json']`
// references the same way `features/run/api.ts` does it.
import { ApiError } from "@/shared/api/client";

// ---------- shared shapes ----------

export type VersionOp = "eq" | "ne" | "lt" | "lte" | "gt" | "gte";

export type NameOp = "eq" | "prefix" | "contains";

export type PackageSource = "apt" | "rpm" | "pacman";

export interface NameFilter {
  op: NameOp;
  value: string;
}

export interface VersionFilter {
  op: VersionOp;
  value: string;
}

// ---------- /packages/search ----------

export interface PackageQueryIn {
  name?: NameFilter | null;
  version?: VersionFilter | null;
  source?: PackageSource | null;
  minion_id?: string | null;
  limit?: number;
  offset?: number;
}

export interface PackageQueryHit {
  minion_id: string;
  name: string;
  version: string;
  arch: string | null;
  source: string | null;
  collected_at: string;
}

export interface PackageQueryOut {
  total: number;
  hits: PackageQueryHit[];
  truncated: boolean;
}

// ---------- /refresh ----------

export type TargetType =
  | "glob"
  | "list"
  | "pcre"
  | "grain"
  | "nodegroup"
  | "compound";

export interface RefreshIn {
  target: string;
  target_type: TargetType;
}

export interface RefreshOut {
  minions_refreshed: number;
  package_counts: Record<string, number>;
}

// ---------- aggregate views (drill-down) ----------

export interface PackageAggregate {
  name: string;
  minion_count: number;
  version_count: number;
  last_seen: string; // ISO timestamp
}

export interface PackageAggregateOut {
  total: number;
  items: PackageAggregate[];
}

export interface VersionAggregate {
  version: string;
  arch: string | null;
  source: string | null;
  minion_count: number;
}

export interface VersionAggregateOut {
  name: string;
  total: number;
  items: VersionAggregate[];
}

export interface ListPackagesQuery {
  q?: string;
  source?: PackageSource;
  limit?: number;
  offset?: number;
}

// ---------- transport ----------
//
// Mirrors the shared `request()` in `shared/api/client.ts`. Kept local so
// we can stay self-contained until types.gen.ts catches up.

async function postJson<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 204) return undefined as TRes;
  const text = await res.text();
  const parsed: unknown = text.length > 0 ? safeJson(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, parsed, extractDetail(parsed));
  }
  return parsed as TRes;
}

async function getJson<TRes>(
  path: string,
  query?: Record<string, string | number | undefined>,
): Promise<TRes> {
  const url = new URL(path, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "")
        url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), { credentials: "include" });
  const text = await res.text();
  const parsed: unknown = text.length > 0 ? safeJson(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, parsed, extractDetail(parsed));
  }
  return parsed as TRes;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractDetail(body: unknown): string | undefined {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
  }
  return undefined;
}

// ---------- React Query keys + API surface ----------

export const inventoryQueryKeys = {
  all: ["inventory"] as const,
  packages: ["inventory", "packages"] as const,
  packageList: (q: ListPackagesQuery) =>
    ["inventory", "packages", "list", q] as const,
  packageVersions: (name: string, source?: string) =>
    ["inventory", "packages", name, "versions", source ?? null] as const,
  packageSearch: (q: PackageQueryIn) =>
    ["inventory", "packages", "search", q] as const,
} as const;

export const inventoryApi = {
  listPackages: (q: ListPackagesQuery = {}) =>
    getJson<PackageAggregateOut>("/api/inventory/packages", {
      q: q.q,
      source: q.source,
      limit: q.limit,
      offset: q.offset,
    }),
  listVersions: (name: string, source?: string) =>
    getJson<VersionAggregateOut>(
      `/api/inventory/packages/${encodeURIComponent(name)}/versions`,
      source ? { source } : undefined,
    ),
  searchPackages: (q: PackageQueryIn) =>
    postJson<PackageQueryIn, PackageQueryOut>(
      "/api/inventory/packages/search",
      q,
    ),
  refresh: (body: RefreshIn) =>
    postJson<RefreshIn, RefreshOut>("/api/inventory/refresh", body),
};

// frontend/src/features/inventory/inventory-packages-page.tsx
//
// Three-level drill-down over the fleet's installed packages.
//
//   Level 1: /inventory                       — every package, with counts
//   Level 2: /inventory?name=openssh-server   — versions of that package
//   Level 3: /inventory?name=...&version=...  — minions running that version
//   Aside : /inventory?minion=web-01         — packages installed on one minion
//
// State lives entirely in the URL. The page picks one of four child views
// based on which search params are set. Back-button navigation works
// naturally; URLs are shareable.
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import {
  ArrowLeft,
  ChevronRight,
  Loader2,
  PackageSearch,
  RefreshCw,
  Server,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MustChangePassword } from "@/features/auth/guards";
import { useHasPerm } from "@/features/auth/use-has-perm";
import { ApiError, errorDetail } from "@/shared/api/client";

import type { PackageSource } from "./api";
import {
  useListPackages,
  useListVersions,
  useRefreshInventory,
  useSearchPackages,
} from "./use-inventory";

const SOURCE_OPTIONS: { value: PackageSource | "any"; label: string }[] = [
  { value: "any", label: "Any package manager" },
  { value: "apt", label: "apt (Debian/Ubuntu)" },
  { value: "rpm", label: "rpm (RHEL/Fedora/Rocky/SUSE)" },
  { value: "pacman", label: "pacman (Arch)" },
];

const PAGE_SIZE = 200;

export function InventoryPackagesPage() {
  return (
    <MustChangePassword>
      <InventoryPackagesPageInner />
    </MustChangePassword>
  );
}

function InventoryPackagesPageInner() {
  const canRefresh = useHasPerm("collect", "inventory:*");
  const search = useSearch({ from: "/app/inventory" });

  // Which view to render is purely a function of which params are present.
  const showMinionView = Boolean(search.minion);
  const showVersionMinionsView = Boolean(search.name && search.version);
  const showVersionsView = Boolean(search.name && !search.version);
  // showPackageListView = default (none of the above)

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <PackageSearch className="h-6 w-6 text-muted-foreground" />
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Inventory</h2>
            <p className="text-sm text-muted-foreground">
              Installed packages across the fleet.{" "}
              {showPackageListView({ search })
                ? "Click a package name to see its versions."
                : showVersionsView
                  ? "Click a version to see which minions have it."
                  : null}
            </p>
          </div>
        </div>
        {canRefresh && <RefreshFleetButton />}
      </header>

      {showMinionView && <MinionView minionId={search.minion!} />}
      {showVersionMinionsView && (
        <VersionMinionsView name={search.name!} version={search.version!} />
      )}
      {showVersionsView && <VersionsView name={search.name!} />}
      {!showMinionView && !showVersionMinionsView && !showVersionsView && (
        <PackageListView />
      )}
    </div>
  );
}

function showPackageListView({
  search,
}: {
  search: { minion?: string; name?: string; version?: string };
}) {
  return !search.minion && !search.name && !search.version;
}

// ============================================================
//  Level 1: package list
// ============================================================

function PackageListView() {
  const [q, setQ] = useState("");
  const [source, setSource] = useState<PackageSource | "any">("any");
  const [page, setPage] = useState(0);
  // Debouncing keeps the API quiet while the user types. 250 ms is the
  // happy medium between "feels reactive" and "doesn't refetch every keystroke".
  const debouncedQ = useDebounce(q, 250);
  const debouncedSource = source === "any" ? undefined : source;

  const query = {
    q: debouncedQ.trim() || undefined,
    source: debouncedSource,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };
  const { data, isPending, isFetching, error } = useListPackages(query);

  if (error) return <ErrorPanel error={error} />;

  const startIdx = data && data.items.length > 0 ? page * PAGE_SIZE + 1 : 0;
  const endIdx = data ? page * PAGE_SIZE + data.items.length : 0;
  const hasMore = data ? endIdx < data.total : false;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 rounded-md border bg-card p-3 md:grid-cols-[2fr_1fr]">
        <Input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(0);
          }}
          placeholder="Filter by name (substring)…"
          className="font-mono"
          aria-label="Filter packages by name"
        />
        <Select
          value={source}
          onValueChange={(v) => {
            setSource(v as typeof source);
            setPage(0);
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SOURCE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {isPending ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading…
            </span>
          ) : data ? (
            data.total === 0 ? (
              "No packages collected yet — run a refresh to populate the inventory."
            ) : (
              <>
                Showing {startIdx.toLocaleString()}–{endIdx.toLocaleString()} of{" "}
                {data.total.toLocaleString()} package
                {data.total === 1 ? "" : "s"}
                {isFetching && (
                  <Loader2 className="ml-2 inline h-3.5 w-3.5 animate-spin" />
                )}
              </>
            )
          ) : null}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasMore}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Package</TableHead>
              <TableHead className="w-32 text-right">Minions</TableHead>
              <TableHead className="w-32 text-right">Versions</TableHead>
              <TableHead className="w-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.length === 0 && !isPending && (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="h-24 text-center text-muted-foreground"
                >
                  {q ? "No packages match this filter." : "No data."}
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((p) => (
              <TableRow
                key={p.name}
                className="cursor-pointer hover:bg-muted/40"
              >
                <TableCell className="font-mono text-xs">
                  <Link
                    to="/inventory"
                    search={{ name: p.name }}
                    className="block w-full text-foreground hover:underline"
                  >
                    {p.name}
                  </Link>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.minion_count.toLocaleString()}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.version_count > 1 ? (
                    <Badge variant="warning" className="font-mono">
                      {p.version_count}
                    </Badge>
                  ) : (
                    p.version_count
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <ChevronRight className="h-4 w-4" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ============================================================
//  Level 2: versions of one package
// ============================================================

function VersionsView({ name }: { name: string }) {
  const { data, isPending, error } = useListVersions(name);
  if (error) return <ErrorPanel error={error} />;

  return (
    <div className="flex flex-col gap-3">
      <Crumbs current={{ label: name }} />

      <h3 className="font-mono text-lg font-medium tracking-tight">{name}</h3>
      <p className="text-sm text-muted-foreground">
        {isPending ? (
          <Loader2 className="inline h-3.5 w-3.5 animate-spin" />
        ) : data && data.total === 0 ? (
          "No versions of this package are currently tracked."
        ) : (
          `${data?.total ?? 0} distinct version${data?.total === 1 ? "" : "s"} across the fleet.`
        )}
      </p>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Version</TableHead>
              <TableHead className="w-24">Arch</TableHead>
              <TableHead className="w-24">Source</TableHead>
              <TableHead className="w-32 text-right">Minions</TableHead>
              <TableHead className="w-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.length === 0 && !isPending && (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="h-24 text-center text-muted-foreground"
                >
                  No data.
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((v) => (
              <TableRow
                key={`${v.version}-${v.arch ?? ""}-${v.source ?? ""}`}
                className="cursor-pointer hover:bg-muted/40"
              >
                <TableCell className="font-mono text-xs">
                  <Link
                    to="/inventory"
                    search={{ name, version: v.version }}
                    className="block w-full hover:underline"
                  >
                    {v.version}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {v.arch ?? "—"}
                </TableCell>
                <TableCell>
                  {v.source ? (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {v.source}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {v.minion_count.toLocaleString()}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <ChevronRight className="h-4 w-4" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ============================================================
//  Level 3: minions running one specific (name, version)
// ============================================================

function VersionMinionsView({
  name,
  version,
}: {
  name: string;
  version: string;
}) {
  const { data, isPending, error } = useSearchPackages({
    name: { op: "eq", value: name },
    version: { op: "eq", value: version },
    limit: 1000,
  });
  if (error) return <ErrorPanel error={error} />;

  return (
    <div className="flex flex-col gap-3">
      <Crumbs
        parent={{ label: name, search: { name } }}
        current={{ label: version }}
      />

      <h3 className="font-mono text-lg font-medium tracking-tight">
        {name} <span className="text-muted-foreground">·</span>{" "}
        <span className="text-base font-normal text-muted-foreground">
          {version}
        </span>
      </h3>
      <p className="text-sm text-muted-foreground">
        {isPending ? (
          <Loader2 className="inline h-3.5 w-3.5 animate-spin" />
        ) : (
          `${data?.total ?? 0} minion${data?.total === 1 ? "" : "s"} running this version.`
        )}
      </p>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Minion</TableHead>
              <TableHead className="w-24">Arch</TableHead>
              <TableHead className="w-24">Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.hits.length === 0 && !isPending && (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="h-24 text-center text-muted-foreground"
                >
                  No minions are currently tracked with that exact version.
                </TableCell>
              </TableRow>
            )}
            {data?.hits.map((h) => (
              <TableRow key={`${h.minion_id}-${h.arch ?? ""}`}>
                <TableCell className="font-mono text-xs">
                  <Link
                    to="/minions/$minionId"
                    params={{ minionId: h.minion_id }}
                    className="inline-flex items-center gap-2 text-foreground hover:underline"
                  >
                    <Server className="h-3.5 w-3.5 text-muted-foreground" />
                    {h.minion_id}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {h.arch ?? "—"}
                </TableCell>
                <TableCell>
                  {h.source ? (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {h.source}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ============================================================
//  Aside: packages on one minion (deep-link from minion detail)
// ============================================================

function MinionView({ minionId }: { minionId: string }) {
  const { data, isPending, error } = useSearchPackages({
    minion_id: minionId,
    limit: 5000,
  });
  if (error) return <ErrorPanel error={error} />;

  return (
    <div className="flex flex-col gap-3">
      <Crumbs current={{ label: `minion: ${minionId}` }} />

      <h3 className="font-mono text-lg font-medium tracking-tight">
        Packages on{" "}
        <Link
          to="/minions/$minionId"
          params={{ minionId }}
          className="hover:underline"
        >
          {minionId}
        </Link>
      </h3>
      <p className="text-sm text-muted-foreground">
        {isPending ? (
          <Loader2 className="inline h-3.5 w-3.5 animate-spin" />
        ) : (
          `${data?.total ?? 0} package${data?.total === 1 ? "" : "s"} installed.`
        )}
      </p>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Package</TableHead>
              <TableHead>Version</TableHead>
              <TableHead className="w-24">Arch</TableHead>
              <TableHead className="w-24">Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.hits.length === 0 && !isPending && (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="h-24 text-center text-muted-foreground"
                >
                  No package data collected for this minion yet.
                </TableCell>
              </TableRow>
            )}
            {data?.hits.map((h) => (
              <TableRow key={`${h.name}-${h.arch ?? ""}`}>
                <TableCell className="font-mono text-xs">
                  <Link
                    to="/inventory"
                    search={{ name: h.name }}
                    className="hover:underline"
                  >
                    {h.name}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs">{h.version}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {h.arch ?? "—"}
                </TableCell>
                <TableCell>
                  {h.source ? (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {h.source}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ============================================================
//  Shared building blocks
// ============================================================

type CrumbSearch = { name?: string; version?: string; minion?: string };

function Crumbs({
  parent,
  current,
}: {
  parent?: { label: string; search: CrumbSearch };
  current: { label: string };
}) {
  const navigate = useNavigate();
  return (
    <nav className="flex items-center gap-1 text-xs text-muted-foreground">
      <button
        type="button"
        onClick={() => void navigate({ to: "/inventory" })}
        className="inline-flex items-center gap-1 hover:text-foreground hover:underline"
      >
        <ArrowLeft className="h-3 w-3" />
        All packages
      </button>
      {parent && (
        <>
          <ChevronRight className="h-3 w-3" />
          <Link
            to="/inventory"
            search={parent.search}
            className="font-mono hover:text-foreground hover:underline"
          >
            {parent.label}
          </Link>
        </>
      )}
      <ChevronRight className="h-3 w-3" />
      <span className="font-mono text-foreground">{current.label}</span>
    </nav>
  );
}

function RefreshFleetButton() {
  const mutation = useRefreshInventory();
  const [result, setResult] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  function onClick() {
    setResult(null);
    setErrorMsg(null);
    mutation.mutate(
      { target: "*", target_type: "glob" },
      {
        onSuccess: (out) => {
          setResult(
            `Refreshed ${out.minions_refreshed} minion${out.minions_refreshed === 1 ? "" : "s"}.`,
          );
        },
        onError: (e) => {
          if (e instanceof ApiError && e.status === 502) {
            setErrorMsg(errorDetail(e) ?? "Salt-API returned an error.");
          } else if (e instanceof ApiError && e.status === 503) {
            setErrorMsg("Salt-API is not configured.");
          } else if (e instanceof ApiError && e.isForbidden) {
            setErrorMsg("You don't have permission to refresh inventory.");
          } else {
            setErrorMsg(e instanceof Error ? e.message : "Refresh failed.");
          }
        },
      },
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button onClick={onClick} disabled={mutation.isPending}>
        {mutation.isPending ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <RefreshCw className="mr-2 h-4 w-4" />
        )}
        {mutation.isPending ? "Refreshing…" : "Refresh fleet"}
      </Button>
      {result && <p className="text-xs text-muted-foreground">{result}</p>}
      {errorMsg && <p className="text-xs text-destructive">{errorMsg}</p>}
    </div>
  );
}

function ErrorPanel({ error }: { error: unknown }) {
  const detail = errorDetail(error);
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view inventory.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
      <p>Failed to load inventory data.</p>
      {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
    </div>
  );
}

// ----- tiny inlined helpers -----

/** Standard debounce hook — returns ``value`` only after ``delayMs`` of no
 *  changes. Cancels the pending update when ``value`` changes again before
 *  the timer fires. Keeps the filter-while-you-type input from spamming the
 *  API on every keystroke. */
function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

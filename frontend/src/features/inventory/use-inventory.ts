// frontend/src/features/inventory/use-inventory.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ListPackagesQuery,
  type PackageAggregateOut,
  type PackageQueryIn,
  type PackageQueryOut,
  type RefreshIn,
  type RefreshOut,
  type VersionAggregateOut,
  inventoryApi,
  inventoryQueryKeys,
} from "./api";

/** Level 1: list every package on the fleet, aggregated by name. */
export function useListPackages(query: ListPackagesQuery) {
  return useQuery<PackageAggregateOut>({
    queryKey: inventoryQueryKeys.packageList(query),
    queryFn: () => inventoryApi.listPackages(query),
    // Refreshes are user-initiated. Cache stays valid until invalidated.
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** Level 2: for a named package, list all distinct versions with per-version
 *  minion counts. ``enabled`` lets the caller defer the query until they
 *  actually have a name. */
export function useListVersions(name: string | null, source?: string) {
  return useQuery<VersionAggregateOut>({
    queryKey: inventoryQueryKeys.packageVersions(name ?? "", source),
    queryFn: () => {
      if (!name) throw new Error("useListVersions called with null name");
      return inventoryApi.listVersions(name, source);
    },
    enabled: name !== null && name.length > 0,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** Level 3 + power query: row-level search with name / version / minion /
 *  source filters. Used by:
 *
 *  - "minions running version V of package X" drill-down view
 *  - "show me every server with openssh-server <= 2.1.0" version comparison
 *  - "packages installed on minion M" deep-link from the minion detail page
 */
export function useSearchPackages(
  query: PackageQueryIn | null,
  enabled = true,
) {
  return useQuery<PackageQueryOut>({
    queryKey: inventoryQueryKeys.packageSearch(query ?? {}),
    queryFn: () => {
      if (!query) throw new Error("useSearchPackages called with null query");
      return inventoryApi.searchPackages(query);
    },
    enabled: enabled && query !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** Kick off a fleet (or single-minion) refresh, then invalidate every cached
 *  inventory query so all the views re-fetch fresh data. */
export function useRefreshInventory() {
  const qc = useQueryClient();
  return useMutation<RefreshOut, Error, RefreshIn>({
    mutationFn: (body) => inventoryApi.refresh(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: inventoryQueryKeys.all });
    },
  });
}

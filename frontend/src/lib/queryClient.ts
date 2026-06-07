import { QueryClient } from "@tanstack/react-query";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";

/** localStorage key holding the persisted query cache. Cleared on logout
 *  (see AuthContext) so a different user on the same browser never sees stale
 *  lists from the previous session. */
export const QUERY_PERSIST_KEY = "jockey-query-cache";

export const MAX_CACHE_AGE = 24 * 60 * 60 * 1000; // 24h

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cached data is shown INSTANTLY on mount and treated as fresh for 5 min,
      // so bouncing between pages within a session neither refetches nor flashes
      // (no API call at all). Mutations (upload/delete) invalidate explicitly and
      // the videos query self-polls while indexing, so staleness is bounded.
      staleTime: 5 * 60_000,
      gcTime: MAX_CACHE_AGE,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

/** Persists the cache to localStorage so lists render immediately even after a
 *  full page reload (not just in-session navigation). */
export const queryPersister = createSyncStoragePersister({
  storage: window.localStorage,
  key: QUERY_PERSIST_KEY,
});

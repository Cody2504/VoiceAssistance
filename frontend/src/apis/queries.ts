/**
 * Shared TanStack Query hooks for the workspace list views (Assets / Overview /
 * Indexes). Cached per-user so the lists render INSTANTLY from cache on revisit
 * (and across reloads, via the localStorage persister) and revalidate in the
 * background. The videos query self-polls while anything is still indexing, which
 * replaces the manual setInterval the pages used to run.
 */
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/contexts/AuthContext";
import { listVideos, type VideoSummary } from "./videos.api";
import { listIndexes, type IndexSummary } from "./indexes.api";
import { listS3Objects, type S3Item } from "./s3.api";

const POLL_MS = 3500;

/** Cache keys — exported so mutations (upload/delete) can invalidate precisely. */
export const qk = {
  videos: (userId?: string) => ["videos", userId] as const,
  indexes: (userId?: string) => ["indexes", userId] as const,
  s3: (userId?: string) => ["s3-objects", userId] as const,
};

export function useVideosQuery() {
  const { user } = useAuth();
  return useQuery({
    queryKey: qk.videos(user?.id),
    queryFn: listVideos,
    enabled: !!user,
    // Keep polling only while something is still indexing → the Status column
    // flips Queued/Indexing → Ready live, then polling stops on its own.
    refetchInterval: (query) => {
      const data = query.state.data as VideoSummary[] | undefined;
      const pending = data?.some((v) => v.status === "queued" || v.status === "processing");
      return pending ? POLL_MS : false;
    },
  });
}

export function useIndexesQuery() {
  const { user } = useAuth();
  return useQuery<IndexSummary[]>({
    queryKey: qk.indexes(user?.id),
    queryFn: listIndexes,
    enabled: !!user,
  });
}

export function useS3ObjectsQuery() {
  const { user } = useAuth();
  return useQuery<S3Item[]>({
    queryKey: qk.s3(user?.id),
    queryFn: async () => (await listS3Objects()).items,
    enabled: !!user,
    staleTime: 60_000,
  });
}

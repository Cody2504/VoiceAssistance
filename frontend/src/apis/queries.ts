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
import { listConversations, type ConversationSummary } from "./chat.api";
import {
  getAdminStats,
  getAdminUser,
  listAdminUsers,
  listPlans,
  listEvalRuns,
  getEvalRun,
  type AdminPlan,
  type AdminStats,
  type AdminUserDetail,
  type AdminUsersPage,
  type EvalRunRow,
  type EvalRunDetail,
} from "./admin.api";

const POLL_MS = 3500;

/** Cache keys — exported so mutations (upload/delete) can invalidate precisely. */
export const qk = {
  videos: (userId?: string) => ["videos", userId] as const,
  indexes: (userId?: string) => ["indexes", userId] as const,
  s3: (userId?: string) => ["s3-objects", userId] as const,
  conversations: (userId?: string) => ["conversations", userId] as const,
  adminStats: () => ["admin-stats"] as const,
  adminUsers: (search: string, page: number) => ["admin-users", search, page] as const,
  adminUser: (id?: string) => ["admin-user", id] as const,
  adminPlans: () => ["admin-plans"] as const,
  evalRuns: () => ["admin-eval-runs"] as const,
  evalRun: (id?: string) => ["admin-eval-run", id] as const,
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

export function useConversationsQuery() {
  const { user } = useAuth();
  return useQuery<ConversationSummary[]>({
    queryKey: qk.conversations(user?.id),
    queryFn: listConversations,
    enabled: !!user,
  });
}

export function useAdminStatsQuery() {
  const { user } = useAuth();
  return useQuery<AdminStats>({
    queryKey: qk.adminStats(),
    queryFn: getAdminStats,
    enabled: user?.role === "admin",
  });
}

export function useAdminUsersQuery(search: string, page: number) {
  const { user } = useAuth();
  return useQuery<AdminUsersPage>({
    queryKey: qk.adminUsers(search, page),
    queryFn: () => listAdminUsers({ search, page, page_size: 20 }),
    enabled: user?.role === "admin",
    placeholderData: (prev) => prev, // keep the table while paging/searching
  });
}

export function useAdminUserQuery(id?: string) {
  const { user } = useAuth();
  return useQuery<AdminUserDetail>({
    queryKey: qk.adminUser(id),
    queryFn: () => getAdminUser(id!),
    enabled: user?.role === "admin" && !!id,
  });
}

export function useAdminPlansQuery() {
  const { user } = useAuth();
  return useQuery<AdminPlan[]>({
    queryKey: qk.adminPlans(),
    queryFn: listPlans,
    enabled: user?.role === "admin",
    staleTime: 300_000,
  });
}

export function useEvalRunsQuery() {
  const { user } = useAuth();
  return useQuery<EvalRunRow[]>({
    queryKey: qk.evalRuns(),
    queryFn: listEvalRuns,
    enabled: user?.role === "admin",
  });
}

export function useEvalRunQuery(id?: string) {
  const { user } = useAuth();
  return useQuery<EvalRunDetail>({
    queryKey: qk.evalRun(id),
    queryFn: () => getEvalRun(id as string),
    enabled: !!id && user?.role === "admin",
  });
}

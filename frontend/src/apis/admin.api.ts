/**
 * Admin console API — iam's /admin router (stats, users, role/suspend) plus
 * billing's manual plan override. Auth via the global axios interceptor; all
 * endpoints are require_admin on the backend.
 */
import axios from "axios";

export interface AdminStats {
  users: number;
  videos: number;
  storage_bytes: number;
  video_minutes: number;
  conversations: number;
  cost_usd_30d: number;
  cost_usd_total: number;
  users_per_plan: Record<string, number>;
  signups_daily: { day: string; count: number }[];
  cost_daily: { day: string; cost_usd: number }[];
}

export interface AdminUserRow {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
  plan_id: string;
  sub_status: string | null;
  video_count: number;
  storage_bytes: number;
  duration_s: number;
  conversation_count: number;
  cost_usd_30d: number;
}

export interface AdminUserDetail extends AdminUserRow {
  stripe_customer_id: string | null;
  current_period_end: string | null;
  usage_daily: { day: string; prompt_tokens: number; completion_tokens: number; cost_usd: number }[];
}

export interface AdminUsersPage {
  total: number;
  items: AdminUserRow[];
}

export interface AdminPlan {
  id: string;
  name: string;
  monthly_index_minutes: number | null;
  monthly_search_queries: number | null;
  monthly_ground_calls: number | null;
  monthly_qa_calls: number | null;
  monthly_summary_calls: number | null;
}

export async function getAdminStats(): Promise<AdminStats> {
  const r = await axios.get("/admin/stats");
  return r.data?.data;
}

export async function listAdminUsers(params: {
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminUsersPage> {
  const r = await axios.get("/admin/users", { params });
  return r.data?.data;
}

export async function getAdminUser(id: string): Promise<AdminUserDetail> {
  const r = await axios.get(`/admin/users/${id}`);
  return r.data?.data;
}

export async function patchAdminUser(
  id: string,
  body: { role?: "user" | "admin"; is_active?: boolean },
): Promise<void> {
  await axios.patch(`/admin/users/${id}`, body);
}

export async function setUserPlan(userId: string, planId: string): Promise<void> {
  await axios.patch(`/billing/admin/subscription/${userId}`, { plan_id: planId });
}

export async function listPlans(): Promise<AdminPlan[]> {
  const r = await axios.get("/billing/plans");
  return r.data?.data?.plans ?? [];
}

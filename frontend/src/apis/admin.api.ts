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

export type PlanUpdate = Partial<Omit<AdminPlan, "id">>;

export async function updatePlan(planId: string, body: PlanUpdate): Promise<AdminPlan> {
  const r = await axios.patch(`/billing/admin/plans/${planId}`, body);
  return r.data?.data;
}

// ---- Chatbot evaluation dashboard (agent-service /admin/eval/*) ----

export interface EvalRunSummary {
  n: number;
  routing_f1_macro: number;
  arg_correctness_rate: number | null;
  mean_task_completion: number | null;
  mean_answer_relevancy: number | null;
  passed: number;
  thresholds_pass: boolean;
  breaches: string[];
}

export interface EvalRunRow {
  id: string;
  kind: string;
  mode: string;
  judge_on: boolean;
  status: "running" | "done" | "failed";
  created_at: string | null;
  finished_at: string | null;
  error: string | null;
  summary: EvalRunSummary | null;
}

export interface EvalCaseRow {
  id: string;
  golden_id: string | null;
  query: string;
  source: string;
  expected_tool: string | null;
  expected_args: Record<string, unknown> | null;
  reference_answer: string | null;
  predicted_tool: string | null;
  tool_correct: boolean | null;
  arg_ok: boolean | null;
  task_completion: number | null;
  answer_relevancy: number | null;
}

export interface EvalRunDetail {
  run: EvalRunRow;
  cases: EvalCaseRow[];
}

export async function listEvalRuns(): Promise<EvalRunRow[]> {
  const r = await axios.get("/admin/eval/runs");
  return r.data?.data;
}

export async function getEvalRun(id: string): Promise<EvalRunDetail> {
  const r = await axios.get(`/admin/eval/runs/${id}`);
  return r.data?.data;
}

export async function createEvalRun(body: {
  kind?: string;
  mode?: string;
  judge?: boolean;
  golden_ids?: string[];
}): Promise<EvalRunRow> {
  const r = await axios.post("/admin/eval/runs", body);
  return r.data?.data;
}

export async function editEvalCase(
  caseId: string,
  body: { expected_tool?: string; expected_args?: Record<string, unknown> | null; reference_answer?: string | null },
): Promise<EvalCaseRow> {
  const r = await axios.patch(`/admin/eval/cases/${caseId}`, body);
  return r.data?.data;
}

import axios from "axios";
import { ROUTES } from "@/constants/routes";

export interface PlanCaps {
  id: string;
  name: string;
  // null = unlimited (Developer / Enterprise)
  monthly_index_minutes: number | null;
  monthly_search_queries: number | null;
  monthly_ground_calls: number | null;
  monthly_qa_calls: number | null;
  monthly_summary_calls: number | null;
}

export interface Subscription {
  plan_id: string; // "free" | "developer" | "enterprise"
  status: string; // active | trialing | past_due | canceled | incomplete
  current_period_end: string | null;
  stripe_customer_id: string | null;
  plan: PlanCaps | null;
}

export async function getSubscription(): Promise<Subscription> {
  const r = await axios.get(ROUTES.BILLING_SUBSCRIPTION);
  return r.data?.data;
}

export interface Invoice {
  issued_at: string;
  due_at: string;
  status: string;
  total: number;
  amount_paid: number;
  currency: string;
  period_start: string;
  period_end: string;
  invoice_url: string | null;
  receipt_url: string | null;
  usage_summary: string;
}

export async function getInvoices(): Promise<Invoice[]> {
  const r = await axios.get(ROUTES.BILLING_INVOICES);
  return (r.data?.data?.invoices ?? []) as Invoice[];
}

/**
 * Create a Stripe Checkout Session (subscription mode, Developer plan) and send
 * the browser to Stripe's hosted checkout page. No card data is collected here —
 * Stripe handles it. On success/cancel Stripe redirects back to /settings/billing.
 */
export async function startCheckout(): Promise<void> {
  const r = await axios.post(ROUTES.BILLING_CHECKOUT);
  const url = r.data?.data?.url as string | undefined;
  if (!url) throw new Error("checkout session missing url");
  window.location.assign(url);
}

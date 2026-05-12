import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      nav("/workspace");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Auth failed";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid h-screen place-items-center bg-neutral-50 text-neutral-900">
      <form onSubmit={submit} className="w-full max-w-sm rounded-xl border border-neutral-200 bg-white p-8 shadow-sm">
        <div className="mb-1 flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-neutral-900 text-[11px] font-bold text-white">J</span>
          <h1 className="text-xl font-semibold">Jockey</h1>
        </div>
        <p className="mb-6 text-sm text-neutral-500">{mode === "login" ? "Sign in to your account" : "Create your account"}</p>

        <label className="mb-2 block text-[11px] font-medium uppercase tracking-wide text-neutral-500">Email</label>
        <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" required />

        <label className="mb-2 mt-4 block text-[11px] font-medium uppercase tracking-wide text-neutral-500">Password</label>
        <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" required minLength={8} />

        <Button type="submit" disabled={submitting} className="mt-6 w-full">
          {submitting ? "…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>

        <button
          type="button"
          className="mt-3 w-full text-center text-xs text-neutral-500 hover:text-neutral-900"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}

import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/contexts/AuthContext";

interface Props {
  mode: "login" | "signup";
}

export function AuthForm({ mode }: Props) {
  const { t } = useTranslation();
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const schema = z.object({
    email: z.string().email(t("auth.errors.email_invalid")),
    password: z.string().min(8, t("auth.errors.password_min")),
  });
  type FormValues = z.infer<typeof schema>;

  const {
    register: rhfRegister,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), mode: "onTouched" });

  const onSubmit = async ({ email, password }: FormValues) => {
    setSubmitting(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      nav("/workspace");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t("auth.errors.generic");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const titleKey = mode === "login" ? "auth.login.title" : "auth.signup.title";
  const submitKey = mode === "login" ? "auth.login.submit" : "auth.signup.submit";

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="w-full">
      <h1 className="text-center text-[34px] font-medium leading-tight tracking-[-0.6px] text-[var(--ink)]">
        {t(titleKey)}
      </h1>

      <div className="mt-10 space-y-5">
        <div>
          <label htmlFor="email" className="mb-2 block text-[13px] font-medium text-[var(--ink-soft)]">
            {t("auth.email")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            {...rhfRegister("email")}
            className="h-12 w-full rounded-lg border bg-white px-4 text-[15px] text-[var(--ink)] outline-none transition placeholder:text-[var(--ink-muted)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
            style={{ borderColor: errors.email ? "var(--danger)" : "var(--line)" }}
          />
          {errors.email && (
            <p className="mt-1.5 text-[12px]" style={{ color: "var(--danger)" }}>{errors.email.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="mb-2 block text-[13px] font-medium text-[var(--ink-soft)]">
            {t("auth.password")}
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPw ? "text" : "password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              {...rhfRegister("password")}
              className="h-12 w-full rounded-lg border bg-white px-4 pr-12 text-[15px] text-[var(--ink)] outline-none transition placeholder:text-[var(--ink-muted)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20"
              style={{ borderColor: errors.password ? "var(--danger)" : "var(--line)" }}
            />
            <button
              type="button"
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? t("auth.hide_password") : t("auth.show_password")}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--ink-muted)] hover:text-[var(--ink)]"
            >
              {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          {errors.password && (
            <p className="mt-1.5 text-[12px]" style={{ color: "var(--danger)" }}>{errors.password.message}</p>
          )}
        </div>

        {mode === "login" && (
          <button
            type="button"
            onClick={() => toast.info(t("auth.login.forgot_toast"))}
            className="text-[13px] font-medium text-[var(--accent)] hover:underline"
          >
            {t("auth.login.forgot")}
          </button>
        )}
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="mt-7 inline-flex h-12 w-full items-center justify-center rounded-lg bg-[var(--ink)] text-[15px] font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? t("auth.submitting") : t(submitKey)}
      </button>

      <div className="my-7 flex items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-[var(--ink-muted)]">
        <span className="h-px flex-1 bg-[var(--line)]" />
        {t("auth.or")}
        <span className="h-px flex-1 bg-[var(--line)]" />
      </div>

      <p className="text-center text-[15px] text-[var(--ink-soft)]">
        {mode === "login" ? (
          <>
            {t("auth.login.no_account")}{" "}
            <Link to="/signup" className="font-semibold text-[var(--accent)] hover:underline">
              {t("auth.login.sign_up")}
            </Link>
          </>
        ) : (
          <>
            {t("auth.signup.have_account")}{" "}
            <Link to="/login" className="font-semibold text-[var(--accent)] hover:underline">
              {t("auth.signup.log_in")}
            </Link>
          </>
        )}
      </p>
    </form>
  );
}

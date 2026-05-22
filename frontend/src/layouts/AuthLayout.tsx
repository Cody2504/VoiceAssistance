import { Link, Navigate, Outlet, useLocation } from "react-router";
import { useTranslation } from "react-i18next";

import { BlobField } from "@/components/brand/BlobField";
import { Logo } from "@/components/brand/Logo";
import { QuoteCard } from "@/components/brand/QuoteCard";
import { useAuth } from "@/contexts/AuthContext";

export default function AuthLayout() {
  const { user, loading } = useAuth();
  const { t } = useTranslation();
  const { pathname } = useLocation();

  if (loading) {
    return <div className="grid h-screen place-items-center bg-[var(--bg)] text-sm text-[var(--ink-muted)]">…</div>;
  }
  if (user) return <Navigate to="/workspace" replace />;

  const isSignup = pathname.startsWith("/signup");
  const quote = isSignup ? t("auth.signup.quote") : t("auth.login.quote");
  const who = isSignup ? t("auth.signup.quote_who") : t("auth.login.quote_who");

  return (
    <div className="grid min-h-screen bg-[var(--bg)] text-[var(--ink)] md:grid-cols-[1fr_1fr]">
      {/* Left pane: form */}
      <section className="relative flex min-h-screen flex-col px-6 py-10 md:px-16 md:py-14">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full" style={{ maxWidth: 420 }}>
            <Link to="/" className="mb-10 flex justify-center" aria-label="Jockey">
              <Logo size="md" />
            </Link>
            <Outlet />
          </div>
        </div>
      </section>

      {/* Right pane: blob field + quote (hidden on mobile) */}
      <aside className="relative hidden overflow-hidden md:block">
        <BlobField />
        <div className="absolute inset-y-0 right-8 flex items-center md:right-12 lg:right-20">
          <QuoteCard quote={quote} attribution={who} />
        </div>
      </aside>
    </div>
  );
}

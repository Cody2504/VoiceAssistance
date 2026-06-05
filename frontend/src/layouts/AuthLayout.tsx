import { Link, Navigate, Outlet, useLocation } from "react-router";
import { useTranslation } from "react-i18next";

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
    <div className="grid min-h-screen bg-white text-[var(--ink)] md:grid-cols-[7fr_3fr]">
      {/* Left pane: form */}
      <section className="relative flex min-h-screen flex-col bg-white px-6 py-10 md:px-16 md:py-14">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full" style={{ maxWidth: 400 }}>
            <Link to="/" className="mb-10 flex justify-center" aria-label="Jockey">
              <Logo size="md" />
            </Link>
            <Outlet />
          </div>
        </div>
      </section>

      {/* Right pane: branded testimonial background + centered quote (hidden on mobile) */}
      <aside
        className="relative hidden overflow-hidden bg-[#ece9e3] bg-cover bg-center md:block"
        style={{ backgroundImage: "url(/twelvelabs/testimonial-bg.png)" }}
      >
        <div className="absolute inset-0 flex items-center justify-center p-8">
          <QuoteCard quote={quote} attribution={who} />
        </div>
      </aside>
    </div>
  );
}

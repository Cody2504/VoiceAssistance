import { Link } from "react-router";
import { Logo } from "@/components/brand/Logo";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Slim top nav mirroring the ElevenLabs / TwelveLabs marketing layout:
 * eggshell background, hairline border on scroll, max-w-6xl centered.
 */
export function NavBar() {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-chalk)] bg-[var(--color-eggshell)]/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-8 px-6">
        <Link to="/" className="shrink-0" aria-label="Jockey">
          <Logo size="sm" />
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-[14px] text-[var(--color-obsidian)]">
          <a href="#capabilities" className="hover:text-[var(--color-obsidian)]/70 transition">Platform</a>
          <Link to="/pricing" className="hover:text-[var(--color-obsidian)]/70 transition">Pricing</Link>
          <a href="#tutorials" className="hover:text-[var(--color-obsidian)]/70 transition">Build</a>
          <a href="#models" className="hover:text-[var(--color-obsidian)]/70 transition">Resources</a>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <Link
              to="/overview"
              className="inline-flex h-9 items-center rounded-full bg-[var(--color-obsidian)] px-4 text-[13px] font-medium text-white transition hover:bg-neutral-800"
            >
              Open app
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="hidden sm:inline-flex h-9 items-center rounded-full border border-[var(--color-chalk)] bg-white px-4 text-[13px] font-medium text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
              >
                Log in
              </Link>
              <Link
                to="/signup"
                className="inline-flex h-9 items-center rounded-full bg-[var(--color-obsidian)] px-4 text-[13px] font-medium text-white transition hover:bg-neutral-800"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

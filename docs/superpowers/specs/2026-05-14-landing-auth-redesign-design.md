# Frontend redesign — public landing page & auth redesign

**Date:** 2026-05-14
**Scope:** `frontend/` only. Adds a public landing page at `/` and redesigns the auth pages (`/login`, new `/signup`). The authenticated app (`MainLayout`, `Workspace`, `Chat`, `VideoDetail`, `Profile`) is **not** changed in this pass.
**Reference inspiration:** TwelveLabs-style split-pane auth + gradient-blob aesthetic; ElevenLabs-style hero with a product-preview "chip" on the right.

---

## 1. Background

Current state of `frontend/`:

- Routes: `/login`, `/workspace`, `/chat[/:id]`, `/video/:videoId`, `/profile`. Root `/` redirects straight to `/workspace`, which redirects to `/login` if unauthenticated. There is **no public surface** — no landing page, no marketing copy, no visual identity beyond a black "J" pill.
- `/login` is a single plain card centered on a neutral background with a small text toggle that switches the same form between login and register modes.
- Stack (kept as-is): Vite + React 19 + TS, Tailwind v4, Radix primitives, react-router v7, react-hook-form, zod, sonner, i18next (en/vi), lucide-react, next-themes (installed but unused), `AuthContext` already exposes `login()` and `register()`.

Three things this redesign fixes:

1. No public surface to send people to.
2. Auth has no brand or social-proof element.
3. There is no "what is Jockey" answer for first-time visitors.

---

## 2. Goals & non-goals

### Goals

- Add a public landing page at `/` with hero, three feature blocks, a three-step "how it works" strip, and a footer.
- Redesign `/login` and add `/signup` as a separate route, both using a shared split-pane layout.
- Establish a single visual identity (light & playful, TwelveLabs-adjacent) — gradient blobs, gradient-text accent on H1, purple primary accent, single Inter font.
- Wire all copy through `react-i18next` so en/vi works from day one.

### Non-goals

- No changes to the authenticated app shell (`MainLayout`, sidebar, etc.).
- No dark mode (deferred — tokens are CSS variables so it's a future toggle).
- No real "Watch demo" video integration; the CTA smooth-scrolls to "How it works".
- No password-reset flow; the "Forgot password?" link on `/login` opens a `toast.info("Coming soon")`.
- No SSO (no Google / GitHub buttons that don't work).
- No backend changes. No new env vars. No new API endpoints.

---

## 3. User-visible behavior

### Routes

| Path | Public? | Renders | Behavior when **already authed** |
|---|---|---|---|
| `/` | yes | `PublicLayout` → `Landing` | Renders the same page; top-right CTA flips from "Get started" → "Open app" linking to `/workspace`. |
| `/login` | yes | `AuthLayout` → `Login` | Redirected to `/workspace`. |
| `/signup` | yes | `AuthLayout` → `Signup` | Redirected to `/workspace`. |
| `/workspace`, `/chat`, `/video/:id`, `/profile` | no | unchanged | unchanged |
| anything else | — | redirect to `/` (was `/`)| unchanged |

`PrivateRoutes` is unchanged.

### Landing page (`/`)

A vertical scroll of four sections on a `--bg` (`#f6f5f1`) paper background.

#### 3.1 Hero (Section A)

Two-column layout (60/40 on desktop, stacked on mobile).

- **Left (copy):**
  - Eyebrow: `VIDEO INTELLIGENCE` — uppercase, letter-spaced, color `--accent` (`#7a4dff`).
  - H1: `Talk to your videos.` — the word `videos` wrapped in a `<span>` with a gradient text fill (`linear-gradient(90deg, #ff8caa, #7a4dff)`).
  - Sub-paragraph: one sentence about search + summarize + locate-the-moment.
  - Two CTAs (pill buttons): primary "Get started" → `/signup`; ghost "Watch demo" → smooth-scrolls to the `#how-it-works` anchor.
- **Right (product chip on a blob field):**
  - 5 fixed-position gradient blobs (CSS only, no animation) using the palette in §6.
  - On top: a `ProductChip` card that mimics a real Jockey query result — a query bar ("when does the keeper save the penalty?"), four mini frame thumbnails (two marked as matches with a 2px accent outline), a scrubber bar with three highlighted segments, and a caption "3 matches across 12:04".

#### 3.2 Features (Section B)

Title row: "Three ways to use Jockey". One row of three `FeatureCard`s on a white surface with soft shadow:

| Title | Sub-copy | Mini illustration (CSS only) |
|---|---|---|
| Search | Drag a video into chat and ask anything. Get answers grounded in the timeline. | mini query bar + scrubber segment |
| Summarize | One-paragraph or chapter-by-chapter summaries of any video in your library. | stacked text-line placeholders |
| Find the moment | Natural-language search across your whole library. Jockey jumps straight to the second. | mini frame grid with one highlighted |

Cards stack vertically on mobile.

#### 3.3 How it works (Section C, anchor `#how-it-works`)

Title: "How it works". Three numbered `StepCard`s in a horizontal strip (stacked on mobile):

1. Upload videos
2. Ask in plain words
3. Jump to the exact moment

Each step has a small gradient-tinted illustration tile (~120×80) on top of the number.

#### 3.4 Footer (Section D)

Three columns of placeholder links + a bottom strip:

- **Product**: Features (anchor to Section B), Pricing (`/pricing` placeholder route — out of scope, link is `<a href="#">`), Docs (`<a href="#">`).
- **Company**: About, Contact.
- **Legal**: Privacy, Terms.

Bottom strip: `<Logo />`, copyright, language switcher (en/vi). The switcher calls `i18n.changeLanguage(code)` and writes `i18nextLng` to `localStorage`; on next load `i18next-browser-languagedetector` reads it. **Implementation note:** if `LanguageDetector` is not yet registered in `src/i18n/index.ts`, add it as part of this work — that file is small and adding it is in scope.

### Auth pages (`/login`, `/signup`)

Shared `AuthLayout` component, ~60/40 split on desktop.

- **Left pane** (white surface, centered column, `max-width: 360px`):
  - `<Logo size="sm" />` at top.
  - H1: `Log in to your account` / `Create your account`.
  - Email input (`type=email`, `react-hook-form` + `zod`).
  - Password input with a show/hide eye toggle (lucide `Eye`/`EyeOff`).
  - Primary button: `Log in` / `Create account`. Disabled while submitting; shows a spinner inside.
  - On `/login` only: a `Forgot password?` link below the password input. Click → `toast.info("Coming soon")`.
  - Thin horizontal divider with "OR" text.
  - Bottom line: `Don't have an account? Sign up` / `Already have an account? Log in` — links to the other route.

- **Right pane** (light surface, hidden below `md` breakpoint):
  - 5 gradient blobs at fixed positions (same palette as landing hero).
  - One floating `QuoteCard` pinned roughly center-right. Copy differs per route:
    - `/login`: "I asked when the dog jumps the fence. Jockey took me to 03:42." — *Beta user · researcher*
    - `/signup`: "Set up in five minutes. Asked my first question in seven." — *Beta user · video editor*

**Form behavior:**

- `react-hook-form` with `zod` schema:
  - `email: z.string().email()`
  - `password: z.string().min(8)`
- Submit calls `useAuth().login(email, password)` or `useAuth().register(email, password)` (both already in `AuthContext`).
- On failure: `toast.error(message)` from sonner, leaves the form populated.
- On success: `navigate("/workspace")`.
- Authed user hitting `/login` or `/signup`: `<Navigate to="/workspace" replace />` inside `AuthLayout` (reads `useAuth().user`).

### Mobile rules

- Below `md` (`<768px`), the right blob pane on auth hides; the form takes the full screen with a softer `--bg` background.
- Landing hero stacks vertically; the product chip drops below the copy.
- Feature cards and step cards stack vertically.
- The public top-nav collapses to logo + a single primary CTA. Three text links (Product / Docs / Pricing) hide; we do **not** ship a hamburger menu in this pass.

---

## 4. Architecture

### 4.1 New files

```
frontend/src/
  pages/
    landing/
      Landing.tsx
      sections/
        Hero.tsx
        Features.tsx
        HowItWorks.tsx
        Footer.tsx
    auth/
      Signup.tsx
      AuthForm.tsx
  layouts/
    PublicLayout.tsx
    AuthLayout.tsx
  components/
    brand/
      Logo.tsx
      BlobField.tsx
      QuoteCard.tsx
      ProductChip.tsx
    landing/
      NavBar.tsx
      FeatureCard.tsx
      StepCard.tsx
```

### 4.2 Edited files

- `src/App.tsx` — register the new routes; remove the root `/` → `/workspace` redirect.
- `src/pages/auth/Login.tsx` — replace internals with `<AuthForm mode="login" />`.
- `src/index.css` — add color tokens, font import, and any shared utility classes (e.g., `.gradient-text`).
- `src/layouts/MainLayout.tsx` — replace the inline `J` chip with `<Logo />` so brand is consistent across surfaces.
- `src/i18n/locales/en/common.json` and `src/i18n/locales/vi/common.json` — add `landing` and `auth` namespaces.
- `frontend/package.json` — add `@fontsource/inter`.

### 4.3 Route registration (in `App.tsx`)

```
<Routes>
  <Route element={<PublicLayout />}>
    <Route path="/" element={<Landing />} />
  </Route>
  <Route element={<AuthLayout />}>
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
  </Route>
  <Route element={<PrivateRoutes />}>
    <Route element={<MainLayout />}>
      <Route path="/workspace" element={<Workspace />} />
      <Route path="/video/:videoId" element={<VideoDetail />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="/chat/:conversationId" element={<Chat />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/library" element={<Navigate to="/workspace" replace />} />
    </Route>
  </Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```

`AuthLayout` reads `useAuth().user`; when truthy, returns `<Navigate to="/workspace" replace />` before rendering its children.

### 4.4 Component contracts

- `Logo({ size?: "sm" | "md" })` — purely presentational; no link wrapper (parent decides whether to wrap in a `Link`).
- `BlobField({ density?: "sparse" | "full" })` — absolutely-positioned div containing 5 fixed gradient blobs. Default `full`. Accepts `className` to scope positioning.
- `ProductChip()` — self-contained mini preview; no props.
- `QuoteCard({ quote: string, attribution: string })` — pure.
- `NavBar()` — reads `useAuth().user` to decide "Get started" vs "Open app" CTA. No props.
- `FeatureCard({ title, body, illustration: ReactNode })`.
- `StepCard({ number: 1|2|3, title, body, illustration: ReactNode })`.
- `AuthForm({ mode: "login" | "signup" })` — owns the form state, schema, submission, and toasts.

Each component is a single file under ~150 lines; if any exceeds that during implementation, split before merging.

### 4.5 Visual tokens (added to `src/index.css`)

```
:root {
  --bg: #f6f5f1;
  --surface: #ffffff;
  --ink: #0a0a0a;
  --ink-soft: #4a4a4a;
  --ink-muted: #888888;
  --line: rgba(0, 0, 0, 0.08);
  --accent: #7a4dff;
  --accent-soft: #ff8caa;
  --danger: #c0392b;

  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 18px;
  --radius-full: 999px;
}
```

Tailwind v4 reads these via `@theme inline { ... }` declarations also added in `index.css`.

Gradient blob pairs (used by `BlobField`):

| # | gradient |
|---|---|
| 1 | `#ff8caa → #c4a8ff` |
| 2 | `#87e3a5 → #ffd060` |
| 3 | `#ffd1b3 → #ff8caa` |
| 4 | `#87cefa → #87e3a5` |
| 5 | `#ffd060 → #ff8caa` |

### 4.6 i18n

New namespaces inside `common.json`:

```
{
  "landing": {
    "hero": { "eyebrow": "...", "h1_a": "Talk to your", "h1_em": "videos.", "sub": "...", "cta_primary": "Get started", "cta_secondary": "Watch demo" },
    "nav": { "product": "Product", "docs": "Docs", "pricing": "Pricing", "open_app": "Open app", "get_started": "Get started" },
    "features": { ... },
    "how": { ... },
    "footer": { ... }
  },
  "auth": {
    "login": { "title": "Log in to your account", "submit": "Log in", "forgot": "Forgot password?", "no_account": "Don't have an account?", "sign_up": "Sign up" },
    "signup": { ... },
    "email": "Email", "password": "Password",
    "errors": { "email_invalid": "...", "password_min": "..." }
  }
}
```

Vietnamese mirrors the same shape. All hardcoded strings in the new files must go through `t()`.

### 4.7 Font loading

Add `@fontsource/inter` as a dependency. In `src/main.tsx`:

```
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
```

Set `body { font-family: "Inter", system-ui, ...; }` in `index.css`. No Google Fonts `<link>`, no external network dependency.

---

## 5. Error handling & edge cases

- **Network failure on login/signup:** sonner `toast.error(err.response?.data?.message ?? "Auth failed")`. Form stays populated. Submit button re-enables.
- **Validation error:** inline error messages under each input (small text, default color `--ink-muted`, shifts to `--danger` when invalid). No toast for validation errors.
- **Already-authed user lands on `/login` or `/signup`:** redirected to `/workspace` before the form is shown.
- **Unauthed user lands on `/workspace`:** existing `PrivateRoutes` redirects to `/login` (no change).
- **Language detection:** `i18next-browser-languagedetector` cache means returning users see their previous language. Falls back to `en`.
- **Reduced motion:** prefers-reduced-motion media query disables the fade-in entrance.

---

## 6. Testing & verification

Manual checks during/after implementation (no new automated tests in this pass; the existing project has none for the frontend):

1. **Routes load:** `/`, `/login`, `/signup` render without console errors.
2. **Authed redirect:** with a valid token in localStorage, navigating to `/login` or `/signup` redirects to `/workspace`.
3. **Auth flows still work:** sign in with an existing test account → redirected to `/workspace`. Create a new account → redirected to `/workspace`.
4. **Validation:** empty submit shows inline errors; bad email format shows inline error; password <8 chars shows inline error.
5. **Failed auth:** wrong password shows sonner toast with backend message; form remains populated.
6. **Forgot password placeholder:** clicking shows `toast.info("Coming soon")`.
7. **Language switch:** switching en↔vi in the footer changes copy across the visible page; choice persists across reloads.
8. **Smooth scroll:** "Watch demo" CTA in hero scrolls to `#how-it-works`.
9. **Responsive:** test in chrome-devtools at 1440, 1024, 768, 375. At 375: right pane on auth is hidden; landing sections stack; nav links hide.
10. **Keyboard:** tab through both forms — focus rings visible, Enter submits.
11. **Lighthouse a11y:** target ≥ 90 on `/`, `/login`, `/signup` (color contrast, button labels, form labels).

---

## 7. Out of scope (deferred)

- App-shell redesign (sidebar grouping, top bar, theme toggle).
- Dark mode.
- Workspace/Chat/VideoDetail content redesign.
- Real password-reset flow.
- SSO.
- Pricing page content (route placeholder only).
- Docs site.
- Mobile hamburger nav (will revisit if mobile traffic matters).

---

## 8. Risks

- **Gradient blobs are CSS-heavy** — five absolutely-positioned divs with gradients are fine for performance but may render slightly differently across browsers. Mitigation: tested in chrome-devtools during implementation; no `filter: blur()` so layout is stable.
- **Inter via `@fontsource/inter` adds ~50KB to the bundle.** Acceptable for a thesis demo; if it matters later, swap for `<link>` to Google Fonts.
- **No automated tests** — manual checklist above is the safety net. Acceptable for the project's current state (no existing frontend tests).

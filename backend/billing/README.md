# billing-service

Demo-only **subscription billing** for jockey, backed by **Stripe Checkout +
Stripe Billing** running in **TEST mode** (no real money ever moves).

It is a thin FastAPI microservice cloned from `token-usage`, on port **1104**,
routed through the gateway at `/api/v1/billing`. Stripe-hosted Checkout collects
the card on Stripe's domain, so this service has **zero PCI scope** — it only
stores the resulting subscription state delivered over a signed webhook.

## What it exposes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET`  | `/api/v1/billing/plans`        | none | Seeded tiers (free / developer / enterprise) + their monthly caps |
| `GET`  | `/api/v1/billing/subscription` | user JWT | Caller's current plan/status/renewal (defaults to `free`) |
| `POST` | `/api/v1/billing/checkout`     | user JWT | Creates a Stripe Checkout Session; returns its hosted `url` |
| `POST` | `/api/v1/billing/webhooks`     | **HMAC** | Stripe → us; verifies raw-body signature, upserts subscription |

## Data model (own `alembic_version_billing`, no IAM schema change)

- **`plans`** — `id` (`free`/`developer`/`enterprise`, matches the frontend
  `pricingData.ts` TIERS), `name`, monthly cap columns mirrored from that file.
  Seeded by migration `0001_billing`.
- **`subscriptions`** — one row per `user_id` (the system is user-scoped; no
  org/account concept). Holds `plan_id`, `status`, `stripe_customer_id`,
  `stripe_subscription_id`, `current_period_end`.
- **`billing_webhook_events`** — idempotency ledger keyed on Stripe `event.id`
  (Stripe redelivers; we apply each event at most once).

---

## Demo setup (free, ~10 min)

### 1. Stripe test-mode keys
1. Create a free Stripe account, stay in **Test mode** (toggle, top-right).
2. **Developers → API keys** → copy the **Secret key** (`sk_test_…`).
3. **Product catalog → Add product** → name it `Developer`, add a **recurring
   monthly Price**, save, copy the **Price ID** (`price_…`).

Put both in `backend/.env`:
```dotenv
STRIPE_API_KEY=sk_test_xxx
STRIPE_PRICE_DEVELOPER=price_xxx
```

### 2. Webhook forwarding (no public HTTPS needed)
The gateway is bare HTTP on :80, so use the Stripe CLI to tunnel test events:
```bash
stripe login
stripe listen --forward-to localhost:8085/api/v1/billing/webhooks
```
It prints a signing secret `whsec_…` — paste it into `backend/.env`:
```dotenv
STRIPE_WEBHOOK_SECRET=whsec_xxx
```
Leave `stripe listen` running during the demo.

### 3. Build & run
`stripe` is baked into the shared base image, so rebuild it once, then start:
```bash
cd backend
make base-build          # REQUIRED after adding stripe to base_image/requirements.txt
make local-up            # or `make up`
```
On startup the service runs `alembic upgrade head`, which creates the tables and
seeds the three plans.

### 4. Drive the demo
1. Log in to the app → **Settings → Billing & plan** (`/settings/billing`).
   You start on **Free** with the seeded caps shown.
2. Click **Upgrade plan** → redirected to Stripe's hosted Checkout.
3. Pay with a **test card**:
   - `4242 4242 4242 4242` — success (any future expiry, any CVC, any ZIP)
   - `4000 0000 0000 0002` — card declined
   - `4000 0025 0000 3155` — requires 3-D Secure authentication
4. Stripe redirects back to `/settings/billing?checkout=success`. Within a second
   or two the `stripe listen` terminal shows `checkout.session.completed` /
   `customer.subscription.created`, the webhook fires, and the page flips to the
   **Developer** plan with a renewal date.

Replay events without paying again:
```bash
stripe trigger checkout.session.completed
```

---

## Demo guardrails (what NOT to do)
- **Test mode only.** Never set `sk_live_…` for the demo — that moves real money.
- **No card form / no card storage.** Stripe-hosted Checkout handles cards; we
  never receive PANs. Don't add a custom card input.
- **No public webhook.** `stripe listen` forwarding is enough; don't expose the
  webhook over the internet without TLS.
- The webhook **must** read the raw body (`await request.body()`) — never the
  parsed JSON — or HMAC verification breaks.

## Production direction (out of scope for the demo)
`docs/superpowers/research/2026-05-15-vnpay-and-token-cost-notes.md` targets
**VNPay + prepaid credit packs** for the Vietnamese market (VNPay sandbox has no
recurring API). This Stripe path is the *subscription demo*, not that roadmap.

# VNPay Sandbox + tl-jockey Token-Cost Model — Research Notes

Date: 2026-05-15
Status: Research only. To be folded into a spec by the main agent. No code.
Primary reference: VNPay sandbox docs at <https://sandbox.vnpayment.vn/apis/docs/>

---

## Executive Summary

1. VNPay sandbox onboarding is self-serve at `sandbox.vnpayment.vn/devreg/`; you get a `vnp_TmnCode` + `vnp_HashSecret` by email; the pay endpoint is `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html`.
2. One-time payment uses an HMAC-SHA512 over ASCII-sorted, URL-encoded `vnp_*` params; fulfillment must happen on the server-to-server IPN (not on the browser Return URL); sandbox IPN originates from `113.160.92.202`.
3. VNPay's sandbox has **no self-serve recurring/MIT API** — `queryDr` docs note token/periodic flows aren't supported; recommend modeling "subscription" as prepaid credit packs with auto-prompt-to-renew via repeated CIT charges.
4. Internal cost model is 8 atomic units (audio min, video min, in/out LLM tokens, premium tokens, search query, qa request, storage GB-mo); LLM token attribution flows via a `trace_id` threaded through LangChain callbacks → one batched POST per chat turn to the `token-usage` service.
5. Recommend a credit-pack UX (1 credit ≈ 500 VND) for the Vietnamese market — matches VNPay's CIT-only reality, mirrors familiar telco top-up patterns, decouples vendor-cost from front-end pricing.

---

## Topic 1: VNPay Sandbox Integration

### 1.1 Sandbox onboarding (credentials)

- Self-service developer registration: <https://sandbox.vnpayment.vn/devreg/>. Fill the form (company / website / contact / IPN URL / Return URL). After approval, VNPay emails:
  - `vnp_TmnCode` — merchant terminal code (per website).
  - `vnp_HashSecret` — HMAC secret used to sign requests and verify callbacks.
- Merchant admin (sandbox): <https://sandbox.vnpayment.vn/merchantv2/?lang=en-US> — used to update Return URL / IPN URL after issuance.
- Production credentials are obtained separately via a contract with VNPay (<https://doitac.vnpay.vn/>); they are *not* the same as sandbox credentials.

### 1.2 Flow A — One-time payment (credit-pack purchase)

**Endpoint (sandbox):** `GET https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?<signed query>`
(Production: `https://vnpayment.vn/paymentv2/vpcpay.html`.)

**Required request params (v2.1.0):**

| Param | Notes |
|---|---|
| `vnp_Version` | `2.1.0` |
| `vnp_Command` | `pay` |
| `vnp_TmnCode` | merchant code |
| `vnp_Amount` | **VND × 100** (integer); send `200000` for 2,000 VND |
| `vnp_CurrCode` | `VND` (only supported currency for VN domestic cards) |
| `vnp_TxnRef` | merchant order id; **must be unique within a calendar day** |
| `vnp_OrderInfo` | free-text description (UTF-8) |
| `vnp_OrderType` | category code, e.g. `other`, `billpayment` |
| `vnp_Locale` | `vn` or `en` |
| `vnp_ReturnUrl` | browser-facing redirect after pay |
| `vnp_IpAddr` | end-user's IP (server-captured) |
| `vnp_CreateDate` | `yyyyMMddHHmmss` in `Asia/Ho_Chi_Minh` |
| `vnp_ExpireDate` | optional, same format; default 15 min |
| `vnp_SecureHash` | HMAC-SHA512 over all `vnp_*` params (see below) |

**Sequence:**

1. Backend builds the signed URL → returns it to the SPA.
2. Browser is redirected to `vpcpay.html`. User authenticates with bank / card.
3. **Return URL** (browser GET): VNPay redirects user back with the same `vnp_*` fields + `vnp_ResponseCode` + `vnp_TransactionStatus` + `vnp_SecureHash`. *Display only* — do **not** fulfill from this.
4. **IPN URL** (server-to-server GET, sandbox: from `113.160.92.202`): same params. Must respond `{"RspCode":"00","Message":"Confirm Success"}` on accept, or matching error codes (`01` order not found, `02` confirmed already, `04` invalid amount, `97` invalid checksum, `99` unknown). **Fulfillment happens here.**

**HMAC-SHA512 signing — the canonical recipe:**

1. Collect every `vnp_*` field (exclude `vnp_SecureHash` and `vnp_SecureHashType`).
2. Drop empty values.
3. Sort keys **alphabetically (ASCII)**.
4. For each pair, build `urlencode(key) + "=" + urlencode(value)` (RFC-3986; spaces as `%20`, not `+`). Python: use `urllib.parse.quote_plus` *consistently on both sides* — mismatch between the encoder used to build the hash input vs. the URL query string is the #1 source of `97 invalid checksum`.
5. Join with `&` → this is `hashData`.
6. `vnp_SecureHash = hex( HMAC_SHA512(key=vnp_HashSecret, msg=hashData) )` — uppercase hex is conventional but VNPay accepts case-insensitive.
7. Append `&vnp_SecureHash=<hex>` to the redirect URL (NOT included in step 4's hashData).

**Common signing gotchas:**

- Encoding the hashData with one encoder (`quote`) and the URL with another (`quote_plus`) → checksum mismatch.
- Including `vnp_SecureHashType` in older docs — v2.1.0 omits it.
- Locale-sensitive sort instead of byte-wise sort.
- Including empty-string params in hashData.
- Forgetting to strip `vnp_SecureHash` when *verifying* IPN/Return.

### 1.3 Flow B — Subscription / recurring billing

**Short answer: VNPay's sandbox does not expose a public recurring-charge / MIT API.** The standard `pay`-command flow is **always customer-initiated** (CIT) and requires the user to be present on the redirect page. The sandbox `queryDr` API explicitly notes that *"token, installment, and periodic payment types are not yet compatible"*.

VNPay has a separate **"VNPAY Payment Token"** product that supports card-on-file tokenization, but enabling it requires a signed contract and is gated to specific merchants — it is not part of the default sandbox.

**Recommendation for tl-jockey:** model "subscription" as **prepaid credit packs with auto-prompt-to-renew**:

- User buys a credit pack via the one-time `pay` flow.
- Backend tracks remaining credits.
- When balance falls below a threshold (or on a calendar cadence), send an in-app / email prompt → user re-runs the CIT flow.
- Frame it in UX as "Gói tháng" (monthly plan), but the actual debit is a one-shot CIT charge each cycle.

Defer real MIT/token-vault until a production contract with VNPay is signed.

### 1.4 Test cards (sandbox)

Primary test path is the **NCB ATM test card**:

- Card number: `9704198526191432`
- Cardholder: `NGUYEN VAN A`
- Issue date: `07/15`
- OTP: `123456`

Other domestic test issuers (Vietcombank, BIDV, Agribank, Techcombank) are listed at <https://sandbox.vnpayment.vn/apis/vnpay-demo/>. International Visa/Master test cards require enabling international acquiring in the merchant profile.

### 1.5 Currency, amount, refund

- `vnp_CurrCode = VND` only (sandbox).
- Amount field is **integer × 100** — the user-facing VND amount has no decimals; ×100 keeps API uniform with currencies that have minor units.
- Per-transaction max for sandbox domestic is **500,000,000 VND** (50M × 100). Real per-card limits are bank-set and lower.
- **Refund API (`vnp_Command=refund`) is restricted in sandbox** — exists in spec but disabled for self-serve merchants; testing requires emailing VNPay support. Production has full refund + `queryDr` (transaction status lookup).

### 1.6 Webhook security

- **Always verify** the `vnp_SecureHash` on every IPN call using the same canonical recipe (strip the hash field, sort, urlencode, HMAC-SHA512). Reject with `RspCode=97`.
- **IP allowlist:** VNPay's sandbox IPN originates from `113.160.92.202`. Production IPs are issued in writing. Allowlist at the LB/WAF or in a FastAPI middleware. Do not rely on IP alone — signature is the source of truth.
- **HTTPS required** for the IPN URL.
- **Idempotency:** VNPay may resend the same IPN. Persist a `vnp_TxnRef` + `vnp_TransactionNo` uniqueness constraint; on duplicate, still respond `RspCode=02` ("order already confirmed") and do not double-credit. Don't 200-OK silently — VNPay treats absence of the expected RspCode body as failure and will retry.
- Validate **amount equality** (DB amount × 100 == `vnp_Amount`) and **status fields** (`vnp_ResponseCode == "00"` and `vnp_TransactionStatus == "00"`) — these are independent.

### 1.7 Failure modes to plan for

- **User abandons redirect** → no IPN arrives → order stays `pending`. Run a sweeper that calls `queryDr` for pending orders > N minutes old.
- **Double-IPN** (network retry) — see idempotency above.
- **Out-of-order IPN vs Return** — IPN can arrive before *or* after the Return URL hits your backend. Treat IPN as the only authoritative event; Return is UI-only.
- **Expired payment URL** (default 15 min from `vnp_CreateDate`) — needs a fresh signed URL.
- **Checksum-97 storm** during development — usually one of: (a) wrong encoder, (b) wrong key, (c) using production secret in sandbox, (d) empty-value not stripped, (e) sort wrong.

### 1.8 Minimal data model

- **`Order`** — `id`, `user_id`, `sku` (e.g. `credit_pack_500k`), `amount_vnd`, `currency`, `status` (`pending|paid|failed|expired|refunded`), `vnp_txn_ref` (uniq per day), `created_at`, `paid_at`.
- **`PaymentAttempt`** — `id`, `order_id`, `gateway` (`vnpay`), `redirect_url`, `vnp_create_date`, `vnp_expire_date`, `result_code`, `bank_code`, `card_type`, `vnp_transaction_no`, `closed_at`. One order can have multiple attempts (user retries).
- **`IPNEvent`** — `id`, `order_id`, `raw_payload` (jsonb), `signature_valid` (bool), `processed` (bool), `received_at`, `responded_with` (the `RspCode` we returned). Append-only audit log; powers idempotency check + debug.

---

## Topic 2: Token-cost model for tl-jockey

The point of this section is not to set the consumer price yet; it's to define the **internal accounting unit** that lets us answer two questions per request: *"what did this cost us in $?"* and *"what should it cost the user in credits?"*

### 2.1 Unit-economics primitives

| Atomic unit | Cost source (May 2026) | Rate (USD, rough) | Notes |
|---|---|---|---|
| `audio_minute_transcribed` | OpenAI `whisper-1` API or `gpt-4o-mini-transcribe` | **$0.006 / min** (whisper-1); $0.003/min (4o-mini-transcribe) | Self-hosted on Colab T4 (~$0.176/hr GPU × RTF≈0.1 on `large-v3` ≈ $0.0003/min) is *unreliable* for production (Colab session caps). Treat Colab as dev-only; price using API rate. |
| `video_minute_indexed` | ViCLIP frame embedding on a self-hosted GPU | Amortized **$0.002–0.004 / min** at ~8fps on a T4 | Dominated by GPU rental rate × wallclock. Assume an A100 worker on a cloud (e.g. RunPod ≈ $0.79/hr) — round to **$0.003 / video-min** in the model. |
| `llm_input_token` | OpenAI `gpt-4o-mini` (planner/supervisor) | **$0.15 / 1M tokens** | Cite the per-call model name in the usage row — pricing changes by model. |
| `llm_output_token` | same | **$0.60 / 1M tokens** | |
| `llm_input_token_premium` / `llm_output_token_premium` | `gpt-4o` for the worker that drafts long answers | **$2.50 / 1M in, $10 / 1M out** | Track separately so we can A/B downgrades. |
| `search_query` | pgvector lookup (CPU-bound) | ~**$0** at our scale | Still meter for analytics. |
| `qa_request` | composite: triggers Whisper + ViCLIP frame sampling + LLM | derived | A `qa_request` is the user-facing "burn unit"; cost is the sum of its child units. |
| `storage_gb_month` | Postgres + object store (e.g. R2 $0.015/GB-mo, B2 $0.006/GB-mo) | ~**$0.01 / GB-mo** | Embeddings ≈ 100KB/video-min at fp16 (ViCLIP 512-d × N frames). |

### 2.2 Attributing LLM tokens across a fan-out request

A single user turn fans out: **planner → supervisor → 1..N worker calls → reflection**. Each is a separate LLM call. We need to roll them up into one billable request.

Recommended pattern:

1. Mint a `trace_id` (uuid4) in `agent-service` when the chat request arrives. Stash on `langchain` `RunnableConfig.configurable.metadata`.
2. Attach a LangChain `BaseCallbackHandler` whose `on_llm_end` (or `on_chat_model_end`) pulls `response.llm_output["token_usage"]` (or `response.usage_metadata` on newer langchain-openai) plus `serialized["name"]` for the model id.
3. The handler **buffers** events in-process keyed by `trace_id`. On graph end (or on `astream_events` `on_chain_end` for the root node), it POSTs a single batched usage payload to the `token-usage` service.
4. `token-usage` service persists rows and exposes `/usage/{user_id}` + `/usage/aggregate`.
5. Non-LLM costs (Whisper minutes, ViCLIP minutes) are emitted by `video-service` against the same `trace_id` when the corresponding tool runs.

Why batched, not per-event: avoids N HTTP calls per chat turn; one POST per turn is enough granularity for billing.

### 2.3 End-user pricing presentation

**Recommendation: credit-pack model.** 1 credit ≈ 500 VND (~$0.02). A typical QA on a 10-min clip burns ~5 credits; indexing a 60-min video burns ~30 credits. Sell `100 / 500 / 2000` credit packs via VNPay one-time CIT.

Reasoning: (a) VNPay sandbox has no real MIT/subscription, so a "subscription" is fake anyway — credits map honestly. (b) Vietnamese consumers under-30 are highly familiar with the prepaid-top-up pattern from Viettel/Mobifone/MoMo, friction is near-zero. (c) Credits decouple our internal $-cost from the front-end UX — we can swap LLM vendors without re-pricing the storefront. (d) Tiered subscriptions are a fast-follow once `token-usage` ARPU data shows the right break-points.

### 2.4 `token_usage` event row shape

Append-only fact table; one row per metered unit. Roll-ups are views.

```
token_usage_event(
  id                 uuid pk,
  trace_id           uuid,                 -- groups one chat turn
  user_id            uuid,
  org_id             uuid null,
  occurred_at        timestamptz,
  service            text,                 -- 'agent-service' | 'video-service'
  node               text,                 -- 'planner' | 'supervisor' | 'worker:video_search' | 'whisper' | 'viclip'
  unit               text,                 -- enum from 2.1
  quantity           numeric,              -- tokens, minutes, GB-months
  model              text null,            -- 'gpt-4o-mini-2024-07-18', 'whisper-1', 'ViCLIP-B/16'
  unit_cost_usd      numeric(12,8),        -- snapshot at event time (price changes)
  cost_usd           numeric(12,6),        -- quantity * unit_cost_usd
  credits_charged    integer,              -- what the user paid (after rounding)
  request_id         text null,            -- chat request id, for joining to chat history
  meta               jsonb                 -- {video_id, duration_sec, prompt_hash, ...}
)
```

Indexes: `(user_id, occurred_at)`, `(trace_id)`, `(unit, occurred_at)` for unit-margin queries.

Two derived views: `v_user_balance` (sum credits purchased − sum credits charged), and `v_unit_margin` (per-unit average cost vs. average credits charged, for gross-margin monitoring).

### 2.5 Open questions for the user

- **Whisper hosting:** stick with OpenAI API ($0.006/min, predictable) or invest in a self-hosted `large-v3` on a rented GPU (cheaper at scale, ops burden)?
- **Premium-tier LLM:** is the worker allowed to escalate from `gpt-4o-mini` to `gpt-4o` for hard questions, or do we hard-cap at mini for cost predictability?
- **Free-tier policy:** new signups get N free credits? If yes, what's N — and does it survive abuse (multi-account farming)?
- **Org/team accounts:** is billing strictly per-user, or do we need org-level pooled credits in v1?
- **Refund policy:** since VNPay sandbox blocks refund-API testing, will we offer self-serve refund of unused credits, or only manual?

---

## Sources

- VNPay sandbox docs landing — <https://sandbox.vnpayment.vn/apis/docs/>
- VNPay sandbox merchant registration — <https://sandbox.vnpayment.vn/devreg/>
- VNPay sandbox merchant admin — <https://sandbox.vnpayment.vn/merchantv2/?lang=en-US>
- VNPay sandbox demo / test cards — <https://sandbox.vnpayment.vn/apis/vnpay-demo/>
- VNPay Installment Techspec PDF — <https://sandbox.vnpayment.vn/apis/files/VNPAY%20Installment%20Payment_Techspec%202.1.1-EN.pdf>
- Community SDK docs (signing, IPN, queryDr) — <https://vnpay.js.org/en/>
- OpenAI API pricing — <https://openai.com/api/pricing/>
- Google Colab pricing — <https://cloud.google.com/colab/pricing>

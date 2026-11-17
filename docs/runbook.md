# Rigby's Cloud local operations — Phase 3

This runbook currently covers local redemption and key handling only. Nothing is
deployed, no Railway schedule is activated, and no paid pass has been sold.
The original employer statement remains limited to Maxx saying this project is
definitely not part of what he does for work; no broader clearance is claimed.

## Exact Gumroad license verification

The adapter posts to the fixed HTTPS endpoint
`https://api.gumroad.com/v2/licenses/verify` with form fields:
`product_id` from the process environment's `GUMROAD_PRODUCT_ID`, the submitted
`license_key`, and `increment_uses_count=false`. No OAuth or access token is needed
for this endpoint. Requests time out after 15 seconds and never follow redirects.
Raw license keys are never placed in URLs, database rows, errors or application
logs. The generic feed HTTP client must not be used: its raw archival behavior
is intentionally unsuitable for payment credentials.

A successful HTTP status alone does not authorize a pass. Require explicit
`success: true` and a purchase receipt matching the configured product and
case-normalized submitted email. Require sale ID, exactly one unit at 9,900 USD
cents, and explicit false refund/dispute/chargeback flags. Reject subscriptions,
recurring charges, preorder authorizations and Gumroad creator/test purchases.
The optional `test` flag is present/true on test purchases and can be omitted on
ordinary receipts; no nonexistent mandatory payment-status field is assumed.
If the receipt includes a license, it must match the submitted canonical license.
Imported customers with no paid purchase receipt do not qualify. Provider errors,
malformed responses, redirects, rate limits and missing product configuration
fail closed; no API key is issued. Invalid/disabled licenses produce a plain
invalid-license message. Provider bodies and exception messages are never shown.

The adapter returns only the verified sale reference, normalized email and a
SHA-256 canonical license hash. Canonical hashing trims and uppercases the
license; the unmodified trimmed input is sent to Gumroad. Local one-time use is
enforced by the license-hash primary key plus a unique verified `gumroad:` sale
reference, atomically with hashed API-key insertion. Gumroad's `uses` counter is
not the local ledger and is not incremented by verification. An already-used
license or alias for the same sale cannot issue another pass.

References: [Gumroad license keys](https://gumroad.com/help/article/76-license-keys),
[official license controller](https://github.com/antiwork/gumroad/blob/main/app/controllers/api/v2/licenses_controller.rb),
[official receipt payload](https://github.com/antiwork/gumroad/blob/main/app/modules/purchase/ping_notification.rb).
These public sources were inspected without buyer credentials or sale requests.

## Live product remains an open item for Maxx

No MCP-pass `GUMROAD_PRODUCT_ID` is configured in this environment and no live
$99 MCP product or real sale has been verified here. Maxx must confirm/create the
separate one-time $99 MCP pass with license keys enabled and supply its product ID
through the environment. The existing snapshot product must not be used as the
MCP pass. This does not authorize a real sale, publication or deployment.

All current successful-provider tests inject `httpx.MockTransport` fixtures with
synthetic, runtime-generated test licenses and simulated ordinary-purchase
receipts. They are not requests against real buyer keys, not real Gumroad sales,
and not proof that the live product works. Genuine Gumroad test purchases are
rejected by the production adapter; no runtime fixture/test-mode bypass exists.
Live verification remains **untested** until separately authorized and checked
against a real qualifying sale. No such check is performed in Phase 3.

## Initial redemption and one-time display

After configuring `DATABASE_URL` through the environment, run the local migration
command (`uv run rigbys-feed migrate`) and service (`uv run rigbys-mcp`). Do not
put credentials into tracked files. `/redeem` takes a license and matching email,
uses same-origin/CSRF checks, and returns a key only in the successful POST.
Save that key privately when shown. GET, reload/replay and a second redemption
cannot recover or display it again. HTML contains the raw key only once; client
commands refer to `RIGBYS_API_KEY` instead of repeating it. Responses use no-store,
no-referrer and a restrictive CSP, with no third-party scripts or analytics.

Only `key_hash`, support `key_prefix`, tier, email and timestamps persist in `api_keys`;
only license hash, API-key hash, original redemption time and verified sale
reference persist in `redemptions`. Access expires exactly 90 days after initial
redemption. Purchase time does not start the clock. There is no subscription or
auto-renewal. Paid quota is 1,000 tool calls/day, free quota 20 searches/day with
seven-day delay and no scores/summaries. API keys and licenses are accepted only
in request bodies/Authorization where appropriate, never query strings.

## Replace a lost or compromised paid key

On `/redeem`, enter the original license and purchase email, then choose
**Replace my API key**. This is an explicit rotation action, not another
redemption. Gumroad eligibility is verified again; matching a stored email alone
is insufficient. A valid license/email pair permits lost-key recovery without
requiring the old raw key. No dashboard or account is created.

The transaction locks the original redemption and current key, issues a fresh
random key, revokes the old hash and moves the redemption link to the new hash.
It preserves the original redemption time and earlier effective expiry. The
90-day clock never restarts. It also copies all daily counters, including an
exhausted current-day quota; repeated rotations cannot reset limits. In-flight
old-key calls finish under the existing shared lock before usage is copied.

The replacement is shown once with the same client commands. Update the local
`RIGBYS_API_KEY` value and reconnect. The old key returns HTTP 401 immediately
on subsequent requests. Expired/revoked passes, ownership mismatches and provider
failures issue no new key. A concurrent change may return a plain retry message;
a failed database transaction leaves the previous key active. This flow rotates
paid keys redeemed through the Gumroad pass; it does not introduce free-key
issuance, renewal, subscription billing or email delivery.

## Read actual local feed health

`GET /health` reads the persisted feed-run metadata through a read-only database
transaction. It returns the last successful `feed_generated_at`, latest global
`last_build_status`, `last_build_status_per_source`, the corresponding per-source
retrieval times/cache-reuse flags in `sources`, and MCP `server_version=1.0.0`.
No API key is required and this read consumes no tool quota. Responses are not
cached and contain no credentials, buyer email, raw provider/error payloads or
connection details.

A failed refresh keeps the last good feed timestamp visible and reports failure;
it never substitutes the current time to make old data look fresh. A database
with no feed returns a null timestamp and `never_run`. An unavailable database
returns a plain HTTP 503, not invented health. The endpoint does not trigger a
feed refresh or activate the schedule. Local fixture and real Phase 1 store
checks are not evidence that the production domain is deployed.

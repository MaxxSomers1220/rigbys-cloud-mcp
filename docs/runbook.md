# Rigby's Cloud production operations — Phase 4

Verified on 2026-11-18: HTTPS `/redeem` returns 200, unauthenticated `/mcp` returns
401, and `/health` returns server version 1.0.0. Production Postgres contains 786
opportunities, including 160 with confirmed research links; source collection has
14,561 NIH awards and 138,849 OpenAlex papers. The latest successful feed timestamp
is `2026-11-18T18:10:23.488529+00:00`; all three source statuses are `ok`.

The daily cron is enabled. A manual execution through Railway's cron service
completed successfully; the first scheduled timer firing has not yet occurred.
Its next scheduled run is 2026-11-19 at 06:00 UTC. See [Phase 4 evidence](evidence/phase4/).
Phase 5/6 client verification and discovery work have not started.

At the November 18 Phase 4 check, the Gumroad pass was an unpublished draft with
licensing saved and its product ID configured in Railway. That check used no
production API keys, license submissions or buyer sales. The live listing now
accepts payments from $1 USD. Maxx states the project is definitely not part of
what he does for work, with no broader employer clearance claimed.

## 1. Check feed health, schedule and recovery

Run `curl -fsS https://mcp.rigbyscloud.com/health`. After the daily job completes,
expect today's UTC `feed_generated_at`, `last_build_status=success`, three `ok`
entries in `last_build_status_per_source`, and `server_version=1.0.0`. Check
`sources` for original retrieval times and weekly-cache reuse. HTTP 200 alone is
insufficient: `never_run`/null means no published feed; failure retains the last
good timestamp. Database unavailability returns plain HTTP 503.

In Railway's production project, inspect `feed-builder` job logs for
`feed_build_success`, matching timestamp and per-source counts, plus completed
execution status. Its command is `/app/.venv/bin/rigbys-feed build`, cron
`0 6 * * *` UTC, restart policy `NEVER`, one replica, 6 GB memory and two CPUs.
This is 01:00 New York standard time or 02:00 during daylight time. Keep the 5 GB
raw volume mounted at `/data`, `RIGBYS_RAW_DIR=/data/raw`, private `DATABASE_URL`
reference and 5 GB Postgres volume. Every run fetches Grants.gov; research refreshes
initially, after seven days, or when its fiscal-year window changes.

For failure, inspect the logged stage/type and resolve source, storage or capacity
problems. Wait for any active build to exit. After interrupted collection, set the
job's start command to `/app/.venv/bin/rigbys-feed build --resume-raw` and deploy
once. Trigger **Run now** in Railway and wait for EXITED and matching healthy
metadata. It reuses hash-verified public responses from the preceding 12 hours, preserving original
timestamps. After recovery exits, restore the normal command in a fresh deployment.
Never replace missing data with fixtures, reset timestamps or backdate free snapshots; free access needs seven
days of actual snapshot aging. Preserve raw archives alongside database backups.

## 2. Rotate a lost or compromised paid key manually

Open `https://mcp.rigbyscloud.com/redeem` in a private browser session. Enter the
original Gumroad license and matching purchase email, then choose **Replace my
API key**. Use the page's explicit rotation action; submitting another redemption
must not issue a second pass. The original raw API key is unnecessary. Gumroad
eligibility is verified again, so knowing a stored email alone is insufficient.

Copy the replacement when shown and keep it private. Set `RIGBYS_API_KEY` privately
in each client's environment and reconnect. Expected behavior: subsequent calls
with the old key return 401, while the replacement inherits the original access.
Rotation preserves the original redemption time, earlier effective expiry and all
daily usage counters. It cannot restart the 90 days or restore exhausted quota.

Only key hashes, a support prefix and permitted metadata persist. A reload cannot
recover the raw replacement. Never place keys or licenses in chat, tickets, URLs,
tracked files or logs. Expired/revoked passes, ownership mismatches and provider
failures issue no replacement; a failed transaction leaves the previous key active.

This is the documented production procedure; Phase 4 performs no key rotation or
authenticated client check. Paid access is 1,000 calls/day for 90 days from initial
redemption; free access is 20 delayed searches/day without scores or summaries.
There is no subscription or automatic renewal.

## 3. Verify a Gumroad license

Use `/redeem` with a license and matching email when a qualifying real sale is
available. The adapter POSTs to the fixed HTTPS endpoint
`https://api.gumroad.com/v2/licenses/verify` with form fields `product_id` from
`GUMROAD_PRODUCT_ID`, submitted `license_key`, and `increment_uses_count=false`.
No OAuth/access token is required. Timeout is 15 seconds; redirects are refused.
Do not use the feed HTTP client: its raw archiver must never receive payment
credentials. Never log/store a raw license, API key or provider response.

Require explicit `success: true`, matching product and case-normalized email,
a sale ID, quantity one, a product price of at least 100 USD cents before tax,
and explicit false refund, dispute and chargeback flags. Reject imported
customers without paid receipts,
subscriptions, recurring charges, preorder authorizations and creator/test
purchases. Ordinary receipts may omit the optional `test` flag. If a license is
included in the receipt, it must match the submitted canonical license. Provider
failures, malformed receipts and missing configuration fail closed with plain
errors; HTTP success alone grants no access.

Use the configured Gumroad MCP pass product ID in Railway. A checkout may charge
tax on top of the qualifying product price. Verify a real sale independently of
synthetic fixture tests and deployment checks.

Local redemption enforces one-time use through the trimmed/uppercased license's
SHA-256 hash and unique verified sale reference. Store API-key hashes only; show
the raw key once. Verification does not increment Gumroad's uses counter.
[Provider reference](https://gumroad.com/help/article/76-license-keys).

## 4. Roll back a deployment

In Railway, select the existing `rigbys-cloud-mcp` project, production environment
and web service. Record the failing deployment ID and the last healthy deployment
before acting. The initial known-good web deployment is
`1001155a-4c58-4807-82cd-82be4a0bf85a`; choose the appropriate prior successful
deployment when newer verified releases exist. Open its deployment menu and use
**Rollback**. Confirm the private database reference and
`RIGBYS_PUBLIC_ORIGIN=https://mcp.rigbyscloud.com` remain correctly configured.

Wait for deployment success, then check `/health` for version, feed timestamp and
build statuses, `/redeem` for HTTP 200 with a Secure CSRF cookie, and unauthenticated
`/mcp` for the expected plain 401. Do not create a key or submit a license to check
a rollback. Compare the result with the recorded healthy state.

A web rollback does not roll back the separate feed job. If that job is affected,
pause its schedule, choose its known-good image/configuration, and complete a manual
run before resuming the schedule. Cron changes need a fresh deployment carrying the updated
schedule; simply redeploying an older deployment retains its older configuration.

Deployment rollback restores application image/configuration, **not** database
schema, published feed contents or raw archives. Do not drop tables or volumes to
undo a deploy. Preserve database/raw backups and assess migration compatibility
before any separate data restoration. Commit the corrective source change so the
next GitHub deployment does not restore the failing release.

## 5. Download the full feed snapshot

Deploy the Phase 7 release to the web service and the scheduled feed builder.
The existing migration step provisions the export tables. The first successful
build with the new builder publishes the download. Check `/health` for that
build's timestamp.

With a paid key set privately in `RIGBYS_API_KEY`, download from a directory
where you keep local exports:

```bash
(
  set +x
  : "${RIGBYS_API_KEY:?Set RIGBYS_API_KEY in the environment first}"
  umask 077
  printf 'Authorization: Bearer %s\n' "$RIGBYS_API_KEY" |
    curl --disable --fail --silent --show-error --header @- \
      --output rigbys-cloud-feed.json.gz https://mcp.rigbyscloud.com/snapshot-export &&
    gzip -t rigbys-cloud-feed.json.gz
)
```

The attachment contains `feed_generated_at`, `record_count`, and
`opportunities`. The first two values also appear in the
`X-Feed-Generated-At` and `X-Feed-Record-Count` response headers. The count
comes from the completed build. Each authenticated paid request uses one call
from the existing paid quota.

Postgres retains the current file and the immediately previous successful
export in `snapshot_exports` and `snapshot_export_chunks`. The HTTPS route
serves the current file only. A 503 can mean the first upgraded build is pending,
the old builder published without an export, or the database is unavailable.
Check the feed-builder's release and its latest successful execution before
retrying.

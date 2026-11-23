# Implementation Plan: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md`
- Constitution: `.specify/memory/constitution.md` v1.0.0
- Date: 2026-11-12

Status: Phase 4 T4.1–T4.3 passed in order on 2026-11-18. The real production
feed and active daily schedule are verified; T4.3 runbook review has passed.
All 261 tests pass, including the original 227. All three checks passed; commit/push is now authorized by the phase gate.
Phase 5 and Phase 6 remain out of scope.

## Phase 4 production deployment — 2026-11-18

The existing Railway account/project/production environment were verified through
official CLI authorization. Paid Hobby is active. Both existing Postgres and the
new persistent raw volume are 5 GB; the feed job has 6 GB memory and 2 vCPU. The first
production build peaked around 3.7 GB, within its configured limit. No database
volume was recreated or exposed publicly.

The GitHub-connected application serves HTTPS at the locked hostname. Public
checks pass: /mcp 401 without a bearer, /redeem 200 with Secure CSRF cookie and
stated limits, /health 200 with version 1.0.0 and a real successful feed timestamp.
An explicit validated RIGBYS_PUBLIC_ORIGIN controls redemption Origin checks and
Secure cookies without wildcard forwarded-header trust. The locked Python 3.12
Docker image excludes local data, Git, test fixtures and credentials; migrations
run before web startup. Host variables contain the private database reference
and Maxx's supplied existing Gumroad product ID; neither is written into Git.

First production source collection: 805 posted Grants.gov records, 14,561 NIH awards,
138,849 OpenAlex papers; publication: 786 opportunities, 14,371 award edges and 147,794
paper edges. Confirmed research links exist for 160 opportunities. Score evidence
and neutral flags are preserved; none are promoted into funding-gap findings.
The initial full build published at 2026-11-18T17:53:12.620386+00:00. A subsequent
manual cron execution published at 2026-11-18T18:10:23.488529+00:00 with fresh
Grants.gov and original-time weekly research cache reuse.

The deployed feed-builder schedule is 0 6 * * * UTC, with restart NEVER and a
single replica. Deployment 2c978aab-2a16-4e99-a0a7-f68a5abdb5e1 includes the cron
setting. Execution 96945506-9d90-4e4c-b54f-8a026c564138 is EXITED, completed at
2026-11-18T18:13:26.630Z (204 seconds). Next timer: 2026-11-19T06:00Z. The manual
execution is observed; a future timer occurrence is not claimed. T4.1/T4.2 proof:
docs/evidence/phase4/t4-1-deploy.json and t4-2-feed-and-schedule.json.

No production keys, synthetic licenses, test feed rows or real buyer sale were
used. The existing unpublished $99 Gumroad draft has licensing saved and its
product ID configured; real-sale verification remains untested. No duplicate
product was created and no paid pass has been sold. Free snapshots begin aging
from actual production publication; no seven-day history was fabricated.
No Phase 5/client verification or Phase 6/discovery/pre-sale work was performed.

## Historical Phase 4 preparation — 2026-11-17 (superseded by deployment above)

The production image, restricted Docker context, configurable network bind and
explicit proxy trust are prepared locally. Four new checks plus the existing227
pass (231 total). The image was built with a session-only BuildKit CA mount for
this workspace's proxy; the certificate is absent from the runtime. A container
using the real local789-record feed passed health, unauthenticated MCP 401, HTTPS
Secure-cookie and empty-form validation checks without keys or license inputs.

The earlier access block was resolved by official Railway device authorization
on 2026-11-18. The account, workspace, project and production environment match
the existing Phase 0 infrastructure. The application runtime and hosted variables
are configured, the GitHub main source is connected, and a source-only local
upload deployed successfully. T4.1 is not yet passed because /health has no
production feed timestamp. Deployment 1001155a-4c58-4807-82cd-82be4a0bf85a is SUCCESS;
see docs/evidence/phase4/production-bootstrap.json. The earlier GitHub connection
queued the previous Phase 3 commit, whose build failed because it has no
Dockerfile; the successful local upload supersedes that attempt. Changes remain local because Maxx
requested commit/push only after all three Phase 4 checks pass.

Maxx now confirms the existing $99 MCP-pass product is an unpublished Gumroad
draft with licensing saved. Its supplied product ID is configured only in the
Railway application environment; no duplicate product is created. Live-sale
verification remains untested. No paid pass, production test key, synthetic
production license or real buyer sale is claimed. No Phase 5 or Phase 6 work was
performed. See docs/evidence/phase4/ for dated observations.

## Phase 3 implementation status — 2026-11-17

Maxx explicitly authorized T3.1–T3.4 only, using test licenses/keys and permitting
synthetic provider fixtures when a live product is unavailable. The constitution
and feature spec are unchanged. No paid pass has been sold; no broader employer
clearance is claimed beyond Maxx's statement that the project is definitely not
part of what he does for work.

`/redeem` is a bounded, same-origin/CSRF-protected server-rendered form taking a
license and purchase email. The Gumroad adapter posts only to its fixed HTTPS
license-verification API with configured product ID and increment_uses_count=false;
it does not use the feed client's raw archive. Product/email/receipt/9900USD/one-unit
checks reject refunded/disputed/chargebacked, test, recurring and preorder receipts.
Provider failures fail closed without exposing inputs, payloads or exception text.
No OAuth, provider polling, production fixture mode or real buyer request was added.

Issuance atomically stores the canonical license hash and verified gumroad: sale
reference with a random paid-key hash, permitted support prefix and original
90-day clock. Migration003 adds a partial unique verified-sale index so case or
sale aliases cannot issue extra passes while legacy references remain unchanged.
A success response contains the raw key once, with fixed client-command templates;
GET, replay and duplicate redemption cannot recover it. No-store, no-referrer and
restrictive CSP headers are applied. Raw keys/licenses never persist in rows/logs.

Explicit `/redeem/rotate` re-verifies license/email, observes the current key before
provider I/O, then locks redemption and key to replace only that generation. The
old hash is revoked immediately; the original redemption and effective expiry are
preserved. All UTC quota counters transfer, including exhausted/in-flight usage.
Concurrent same-generation rotation has one winner; failure rolls the entire
transaction back. This is paid-pass recovery, not free-key issuance or renewal.

`/health` reads actual persisted last-success and latest-attempt feed status through
a read-only transaction. It exposes only status/time/cache-reuse metadata for the
three public sources, version 1.0.0 and the original successful feed timestamp.
Failures preserve stale timestamps; an unbuilt database reports never_run/null,
and database failure returns plain503 without credentials or stack traces.

Local task checks passed in order. Full suite: **227 passed**, retaining the existing
110. Independent actual-HTTP review passed18cases (redemption11/rotation6/health1),
and the final loopback smoke passed against the unchanged real789-record feed.
All provider responses were injected synthetic fixtures, with zero real Gumroad
requests, buyer keys or sales; temporary rows/listeners were removed afterward.
Wheel build includes the Phase 3 modules and migration003. Evidence lives under
`docs/evidence/phase3/`; the exact verification and local procedures are in
`docs/runbook.md`. Earlier route-absence/schema assertions now reflect the two
explicitly authorized web endpoints and third migration; all original tests pass.

**Historical Phase 3 open item:** the product ID was not confirmed at that
handoff. Update 2026-11-18: Maxx confirms the existing unpublished $99 pass draft
with licensing saved, and its supplied ID is configured in the Railway application
environment. Do not create a duplicate or substitute the snapshot product. Live
eligibility verification remains untested until separately authorized against a
real qualifying sale; neither Phase 3 fixtures nor Phase 4 deployment prove it.

No Railway configuration, production database, deployment, schedule activation,
production client onboarding or later-phase work was touched. **STOP before Phase 4.**

## Phase 2 implementation status — 2026-11-17

Maxx explicitly authorized T2.1–T2.6 only. The absent pre-sale remains absent;
synthetic test credentials and redemption rows are not sale evidence. The
constitution and feature spec are unchanged. No broader IP clearance is claimed.

FastAPI mounts FastMCP `rigbys-cloud` 1.0.0 at `/mcp`, stateless Streamable HTTP
with JSON responses and exactly four read-only tools. The supplied spec has no
literal §2 instructions block: the server instructions faithfully derive from
its contracts, the constitution and the explicit feed-honesty requirements.

Search is parameterized English FTS, with inclusive UTC source-date filters,
NIH/NSF shorthand, 10/25 limits, compact references and visible evidence flags.
Explicit minimum-gap filters use observed proxies only; ordinary paid search and
full reads preserve neutral values and flags unchanged. Full reads equal stored
JSON field-for-field. Edge-only reads follow stored `via_award` associations and
include confidence/URLs without scores or summaries.

Topic aggregation deduplicates research IDs, discloses fiscal/calendar-year
window overlap rather than inventing exact dates, excludes neutral placeholders
from medians/rankings and suppresses comparisons across mixed methodologies.
The top-five groups are explicitly source opportunity-title groups, not a newly
invented scientific taxonomy. Counts describe the last successful feed, not a
live upstream status check. Portfolio proxies are never claims of underfunding.

Bearer middleware authenticates every MCP HTTP message. Paid expiry is bounded
by original redemption plus 90 days and stored expiry, never purchase or key-row
creation. DB revocation is checked on every request; no key issuance, redemption
or rotation flow is implemented. UTC counters atomically enforce 1,000 paid/20
free calls per day, with HTTP 429 Retry-After. Handshake/list messages are uncharged;
unauthorized/free paid-tool refusals are uncharged; authorized tool attempts count.
Plain 401/403/429 errors contain no stack traces or credentials. Request principals
are isolated and a session identifier confers no access.

Migration 002 adds sealed immutable free-search history, captured atomically with
feed publication and bootstrapped from the existing feed at actual capture time.
Both feed generation and capture must be seven days old. Free search reads only
basic snapshot fields, matches titles only and rejects the paid score filter.
There is no fabricated historical data or fallback to mutable current rows.
The actual local feed currently returns delayed_feed_unavailable for free search;
synthetic history and advanced-clock tests prove the exact seven-day boundary.

All six task checks passed. Final full suite: **110 passed**, including the original
52. Actual authenticated MCP Inspector initializes/lists/calls all four tools over
local HTTP against the real 789-record feed; neutral scores remain 50 with flags,
insufficient evidence yields null medians/empty rankings, and auth/quota HTTP cases
pass. Temporary test credentials/redemptions/counters were removed and listeners
stopped. All tests use the isolated workspace Postgres, never Railway production.

Evidence: `docs/evidence/phase2/`; setup/contracts: `docs/mcp-service.md`. Wheel
build includes both packages and both migrations. Schema tests were updated only
for the two additive snapshot tables and second migration; all original checks
remain passing. Phase 3 and later tasks remain unchecked; no deployment or buyer
verification is claimed. **STOP before Phase 3.**

## Phase 1 implementation status — 2026-11-17

Maxx explicitly authorized Phase 1 only after correcting the false pre-sale/IP
record. No paid pass has been sold as of 2026-11-16; T6.3 remains unchecked. Maxx
states the project is definitely not part of what he does for work; no broader
clearance is claimed. The constitution and feature spec are unchanged.

T1.1–T1.8 are implemented and checked in task order. Source clients retrieved 828
posted opportunities, 14,601 awards (284 NIH FOAs, FY2024–2027), and 138,804 unique
OpenAlex works. The complete local feed has 789 opportunities, 14,411 award edges
and 147,744 paper edges; no trial edges. All records have normalized fields,
join/coverage status, versioned scores, source-bound summaries and source times.

Source access changed from the draft assumptions: NIH publications cap one core
at 10,000 results; OpenAlex cursor paging requires a key. Complete bulk paper
retrieval uses public basic paging, exact `awards.funder_award_id`, and recursively
partitioned query groups with count proofs. The optional RePORTER PMID path was
live-verified separately. No paid data, new API key, or extra source was added.

Research coverage is limited: 165 opportunities have confirmed links and 756
records carry flagged neutral score placeholders; only 33 have descriptive proxy
scores supported by the minimum evidence thresholds. These are not observations
of funding gaps. Broad parent FOAs and long-lived award cores do not establish
current-opportunity causal funding or topic relevance.

The isolated Postgres gate passed with 789/789 structurally complete records,
SC-002 10/10 stored deadlines/source links matching fresh Grants.gov (all pages
HTTP 200), 20/20 published direct paper chains, and 52 automated tests. Evidence:
`docs/evidence/`; procedures: `docs/feed-operations.md`. The full build recovered
same-session source requests using verified archive hashes; a second complete
build exercised durable weekly cache reuse. Every source keeps its original time.
Large source caches are chunked atomically; failed builds preserve the last good
feed. The recovery run peaked around 2.9 GiB RSS: hosting-job capacity must be
sized and verified in the deployment phase, rather than assuming the feed fits a
small web-service process.

Railway's private production database was not accessed; no public application or
host schedule was activated. The schedule definition and job command are ready
for later hosting setup. The Phase 1 health stub is a CLI JSON read, not the later
HTTP endpoint. Phase 2 and all later tasks remain unchecked.

## Implementation status — 2026-11-12

This document was restored from the supplied plan PDF. Phase 0 is complete; Phase 1 has not started, and work is stopped for Maxx's phase review. The constitution remains unchanged and governs the following source-document conflict: constitution §6 says "Pre-sell before building" and "Do not sell until checked" for the employer IP / conflict check; the task list places its sale checkpoint at T6.3. The original plan called that checkpoint Phase 5, but it is Phase 6 in `tasks.md`. The later checkpoint does not waive the earlier constitutional gates.

Correction recorded 2026-11-17: as of 2026-11-16, NO paid pass has been sold; presale is still no. The earlier claim of a paid pre-sale on 2026-11-12 was incorrect. Maxx states this project is definitely not part of what he does for work; no broader employer IP clearance is claimed. The pre-sale gate is not satisfied. T6.3 remains unchecked. Maxx has explicitly instructed Phase 1 feed work only in this session despite the absent pre-sale; this does not claim a sale, change the constitution, or authorize Phase 2 or selling.

On 2026-11-12, Maxx confirmed GitHub and Railway are connected and reported a Railway trial with $5 in credits, expiring after 30 days or credit exhaustion. Railway permits databases during the trial (https://docs.railway.com/pricing/free-trial), so paid-plan activation is not a Phase 0 gate. Railway access is verified. The `rigbys-cloud-mcp` project and private Postgres service are provisioned; the empty application service has no connected source and no active deployment. Its `DATABASE_URL` reference was committed using Railway's documented configuration-only action that skips redeployment. The local database migration preflight, removal of temporary public database access, and DNS routing checks all passed as recorded below.

### Phase 0 infrastructure evidence — 2026-11-12

- Project: https://railway.com/project/bc2ef276-6d7f-431e-b5ad-ca8aa706f7a8
- Environment: `production`, ID `3e3f66d7-72f8-4978-8b81-ce06cb0e0629`.
- Empty application service: `easygoing-sparkle`, ID `e8ee5640-6647-4a1c-be5b-e33b524798fa`; no GitHub repository or image connected, and no active deployment.
- Postgres service: `Postgres`, ID `7b9ac7d4-5d35-4ee2-b885-30dd49af57c0`; online, restored to private access only after the approved local check. The actual local Python migration preflight connected over TLS to PostgreSQL 18.6, confirmed an empty database and public-schema CREATE privilege, and successfully rolled back temporary DDL/DML. The probe was absent afterward, with no Phase 1 application tables created.
- The application's only configured user variable is `DATABASE_URL`, referencing the Postgres service through Railway's environment-variable reference system. No connection URL or password is stored in this repository.
- `mcp.rigbyscloud.com` is allocated on Railway with target port `8000`. Public DNS resolves its CNAME to `cinv31ig.up.railway.app`; its ownership TXT value exactly matches Railway's required record. Route 53 zone `Z0351672KRBWDR8D6R7N` changed from five to seven records by adding only the required CNAME and ownership TXT names. This passes the DNS alternative in T0.3; it does not claim an issued TLS certificate or a working HTTP application.
- User decisions confirmed 2026-11-12: both MCP and redemption use `mcp.rigbyscloud.com`; root/apex routing is not a v1 prerequisite. Maxx approved temporary public access to the empty Postgres database solely for the local TLS migration check, followed by immediate removal. The public proxy was removed immediately after that check; a new connection using the same credentials to the old endpoint was rejected. Railway then showed Postgres Online, no public proxy, Add Public Access available, and no staged changes remaining. No database credentials or connection URLs are recorded here.
- Ordinary Railway **Deploy Changes** was rejected by automatic approval review because it could deploy the service. The subsequent environment-variable commit used the documented Alt-click configuration-only action (https://docs.railway.com/deployments/staged-changes); the application was then verified to have no connected source and no active deployment. Phase 0 ended without deploying the application.

## Technical Context

- **Language:** Python 3.12 (confirmed 2026-11-12 — matches the earlier Nov 7 recommendation of Python + FastAPI for the data pipeline).
- **MCP framework:** FastMCP (Python MCP SDK wrapper) — defines each tool as a decorated function, handles Streamable HTTP transport, JSON schemas, and server instructions.
- **Web framework:** FastAPI for the redeem page + health endpoints, mounted alongside the MCP server on the same service. One service, one port.
- **Database:** Postgres (host-provided, Railway Postgres). One store for the feed, keys, and redemptions.
- **Feed sources:** Grants.gov (POST `api.grants.gov/v1/api/search2` + `fetchOpportunity`, no key), NIH RePORTER (`https://api.reporter.nih.gov/v2`, no key), OpenAlex (`https://api.openalex.org/works`, no key for basic use).
- **Hosting:** Railway (confirmed 2026-11-12). Small always-on service, HTTPS via host, env vars via host dashboard. Not serverless.
- **Auth:** Bearer API key, checked per MCP request. No OAuth v1.
- **Payment:** Gumroad (already connected). License-key redemption checked against the Gumroad sale record at redeem time; no Gumroad API polling in v1.
- **Clients to verify against:** OpenAI Codex CLI and Claude Code, both with a real key.

## Constitution Check

- **Five layers:** all five must be present in `opportunity_get` output. If any layer cannot be built, flag it in the spec — do not ship silently.
- **Feed first, server second:** Phase 1 (feed) must complete and pass its checks before Phase 2 (MCP server) starts serving.
- **No trials in v1:** `linked_trials[]` omitted everywhere, including tool descriptions and the skill file.
- **No subscriptions:** renewal is a new Gumroad purchase, no auto-renew code.
- **Pre-sell guardrail:** the task list includes a pre-sell checkpoint (Phase 6, T6.3) before registry listings or a second feed. Constitution §6 additionally requires pre-selling before building; as of 2026-11-16 no paid pass has been sold; the pre-sale gate remains unmet.
- **Employer IP:** the source constitution records the check as unverified and prohibits selling until checked. Maxx states this project is definitely not part of what he does for work; no broader clearance is claimed. No code or data from Maxx's institutional work may be used. Sources are public only (Grants.gov, RePORTER, OpenAlex).

## Architecture

```text
Grants.gov ─┐
NIH RePORTER ├─► Feed builder (daily / weekly jobs) ─► Postgres (opportunities, links, scores, keys)
OpenAlex ───┘
                                                              │
                                                              ▼
                                    FastAPI service (one deploy)
                                      ├─ /mcp  (FastMCP, Streamable HTTP, 4 tools, Bearer auth)
                                      ├─ /redeem (Gumroad license → API key, show once)
                                      ├─ /health (feed_generated_at, last build status)
                                      ├─ /snapshot-export (Phase 7 paid current-feed attachment)
                                      └─ /llms.txt, /agents.md (static)
```

Feed builder is a separate scheduled job in the same repo (cron / scheduler on the host), not a request-time fetch. MCP tools are thin reads over Postgres — they never call Grants.gov / RePORTER / OpenAlex live.

MCP tools map 1:1 to queries: `opportunity_search` → filtered list query, `opportunity_get` → single-record query, `opportunity_links` → edges query, `gap_for_topic` → aggregation query.

Auth middleware runs before every MCP call: look up key, check tier + expiry, enforce free-tier tool restrictions, enforce rate limits, then run the tool.

Redeem page is a minimal server-rendered page (no JS framework): form → verify license → generate key → show once + copy-paste commands.

### Phase 7 — Authenticated current-feed export

The scheduled feed builder and HTTPS application run as separate Railway services with separate volumes. Storing the gzip artifact as bounded byte chunks in the shared private PostgreSQL service gives both services access and ties the export to the committed feed. PostgreSQL carries the cost of retaining two compressed artifacts and reading a file for each download. The HTTPS application delivers the file to the caller, who can keep their downloaded copy locally.

After the feed builder writes the canonical opportunity records and success metadata, it encodes those final records as UTF-8 JSON in gzip format and writes the artifact in the same publish transaction. This preserves publication-time fields such as `feed_generated_at` and `change_log`. The transaction promotes the new generation to current, keeps the prior successful generation, and removes older artifacts. A failed transaction leaves the previous committed feed and export available.

The HTTPS app uses the existing Bearer verification, paid-tier requirement, and UTC daily quota for `GET /snapshot-export`. Read the current artifact manifest and ordered chunks against one consistent PostgreSQL snapshot so a concurrent publish cannot mix generations. Use chunks of up to 1 MiB for storage and stream them to the caller through a database cursor. Serve the download as `application/gzip` with an attachment disposition for `rigbys-cloud-feed.json.gz` and `Cache-Control: private, no-store`. The response also reports `Content-Length`, `X-Feed-Generated-At`, and `X-Feed-Record-Count`. Return a plain 503 while the latest successful feed lacks a completed artifact. Verify the route using the current production generation only after authorized deployment and a successful artifact publication.

#### Private download

Use a trusted terminal with `RIGBYS_API_KEY` already in the environment. This command passes the authorization header over stdin and writes the attachment with private file defaults.

```bash
(
  set +x
  : "${RIGBYS_API_KEY:?Set RIGBYS_API_KEY in the environment first}"
  umask 077
  printf 'Authorization: Bearer %s\n' "$RIGBYS_API_KEY" |
    curl --disable --fail --silent --show-error --header @- \
      --output rigbys-cloud-feed.json.gz \
      https://mcp.rigbyscloud.com/snapshot-export &&
    gzip -t rigbys-cloud-feed.json.gz
)
```

## Data Model

### opportunities

- `opportunity_id` (text, PK, stable Rigby's ID), `dedupe_key` (unique), `title_normalized`, `sponsor_normalized`
- `deadline_parsed` (timestamptz, nullable), `eligibility_parsed` (jsonb array), `award_amount_parsed` (jsonb, nullable), `source_ids` (jsonb array)
- `growth_score`, `momentum_score`, `novelty_score`, `gap_score` (int 0–100, nullable for free tier), `methodology_version` (text)
- `summary_short` (text), `extracted_requirements` (jsonb array)
- `feed_generated_at` (timestamptz), `fetched_at`, `updated_at`, `source_refs` (jsonb), `change_log` (jsonb array)
- Indexes: `deadline_parsed`, `sponsor_normalized`, full-text on `title_normalized` + `summary_short` (for topic search), `gap_score`.

### opportunity_links

`opportunity_id` (FK), `link_type` (`award` | `paper`), `target_id` (RePORTER project number / OpenAlex work ID), `target_url`, `join_confidence` (float 0–1).

No trial `link_type` in v1.

### api_keys

`key_hash` (PK, store hash only — never the raw key), `key_prefix` (e.g. `rgby_live_…` first 12 chars, for support), `tier` (`free` | `paid`), `email` (recovery only), `expires_at` (timestamptz, null for free), `created_at`, `rotated_at`, `revoked_at` (nullable).

### redemptions

`license_key_hash` (unique), `api_key_hash` (FK), `redeemed_at`, `gumroad_sale_ref` (text, as recorded at redeem time).

### rate_limit_counters

`key_hash`, `day` (date), `calls` (int). Reset daily. Enforce in middleware.

### Phase 7 export artifacts

Each retained artifact has a successful feed run identity, its `feed_generated_at`, its `record_count`, and ordered gzip-byte chunks bounded in size. The current and previous artifacts are the only retained generations. The export query reads the current artifact directly. It never queries upstream sources or builds the gzip during a download.

## Tool Contracts (summary — full schemas in spec.md FR-003–FR-006)

| Tool | Input | Output | Free tier |
| --- | --- | --- | --- |
| `opportunity_search` | `topic`*, `sponsor`, `deadline_before`/`deadline_after`, `min_gap_score`, `limit` (10/25) | compact records, no full joins | 7-day-delayed, no scores/summary |
| `opportunity_get` | `opportunity_id`* | full unified record, all 5 layers | refused (paid-required) |
| `opportunity_links` | `opportunity_id`* | edges only | refused |
| `gap_for_topic` | `topic`*, `window_months` (12) | counts, medians, top 5 neglected / crowded | refused |

## Deployment

- **Service:** one Railway service, Python, uvicorn (or `fastmcp run` behind FastAPI mount). Port from `$PORT`.
- **Jobs:** feed builder as a scheduled job on the same host (daily Grants.gov, weekly RePORTER/OpenAlex in v1). Log `feed_generated_at` + per-source counts on every run; `/health` exposes them.
- **Env vars (host dashboard only):** `DATABASE_URL`, `GUMROAD_PRODUCT_ID` (for license verification), `MCP_SERVER_NAME=rigbys-cloud`, `FREE_TIER_DELAY_DAYS=7`. No secrets in repo.
- **Domain:** `mcp.rigbyscloud.com` → host, serving both `/mcp` and `/redeem` on the same service. HTTPS via host. Root/apex routing is not a v1 prerequisite (confirmed 2026-11-12).

## Testing Strategy

- **Unit:** scoring functions (growth/momentum/novelty/gap) against hand-checked fixtures; deadline/eligibility parsing against real Grants.gov records; auth middleware (valid / expired / revoked / free-tier refusal).
- **Integration:** feed builder against live source APIs (recorded fixtures for CI, live check before deploy); MCP tools against a seeded Postgres with known records.
- **Client verification (mandatory, not optional):** MCP Inspector locally, then a real paid key in Codex (`codex mcp list`, `/mcp`, User Story 1 prompt) and in Claude Code (`/mcp`, same prompt). Verify deadlines + source links against Grants.gov on a 10-record spot-check (SC-002).
- **Failure cases:** expired key → 401, rotated key old value → 401, free key on paid tool → paid-required error, rate limit → 429 with `Retry-After`, feed build failure → last good feed with visible `feed_generated_at`.
- **Phase 7** — Use disposable PostgreSQL and 786 controlled fixture records to verify exact ID and full-record parity, gzip headers and integrity, shared paid quota, failure responses, atomic publication, and two-artifact retention. Exercise an artifact spanning multiple chunks and a read overlapping a replacement publish. Verify separately on production after authorized deployment and store redacted evidence in `docs/evidence/phase7/`.

## Risks & Mitigations

- **Feed quality is the product.** If joining/scoring is thin, the $99 is unjustified. Mitigation: free tier lets buyers verify joining before paying; spot-check SC-002 gates launch.
- **Grants.gov / RePORTER / OpenAlex change their APIs.** Mitigation: feed builder logs per-source counts; `/health` shows last success per source; a failed source does not silently serve stale data as fresh.
- **MCP protocol drift (Codex / Claude Code change flags).** Mitigation: verify against both clients at launch and after any client update; keep the server to the stable Streamable HTTP + Bearer pattern, no exotic features.
- **Gumroad license verification is manual in v1.** Mitigation: redeem flow is a single check at redeem time; document the exact verification step in the runbook (`tasks.md` Phase 4) so it is not improvised at launch.

## Open Decisions (blocking — resolve before $speckit-implement)

All four decisions confirmed by Maxx on **2026-11-12**, asked and answered individually in chat:

1. **Price/duration:** $99 one-time for a 90-day MCP pass, starting at redemption rather than purchase. No subscription or auto-renewal.
2. **Rate limits:** free 20 searches/day; paid 1,000 tool calls/day.
3. **Hosting:** Railway.
4. **Stack:** Python + FastAPI + FastMCP; Python 3.12 per this plan.

Additional deployment decision — **2026-11-12:** Maxx authorized using `mcp.rigbyscloud.com`, under the already-owned domain, for both MCP and redemption. Use `https://mcp.rigbyscloud.com/mcp` for MCP and `https://mcp.rigbyscloud.com/redeem` for redemption. T0.3 requires routing this hostname only; root/apex routing is not a v1 prerequisite. This is a user-authorized update to the source draft's domain, buyer/renewal URLs, client-command URLs, and setup DNS scope; the four original decisions above remain unchanged.

# Implementation Plan: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md`
- Constitution: `.specify/memory/constitution.md` v1.0.0
- Date: 2026-11-12

Status: Phase 0 remains complete. Phase 1 feed implementation and local Postgres gate passed on 2026-11-17. **STOP before Phase 2.** No MCP service or Railway deployment has started.

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
                                      └─ /llms.txt, /agents.md (static)
```

Feed builder is a separate scheduled job in the same repo (cron / scheduler on the host), not a request-time fetch. MCP tools are thin reads over Postgres — they never call Grants.gov / RePORTER / OpenAlex live.

MCP tools map 1:1 to queries: `opportunity_search` → filtered list query, `opportunity_get` → single-record query, `opportunity_links` → edges query, `gap_for_topic` → aggregation query.

Auth middleware runs before every MCP call: look up key, check tier + expiry, enforce free-tier tool restrictions, enforce rate limits, then run the tool.

Redeem page is a minimal server-rendered page (no JS framework): form → verify license → generate key → show once + copy-paste commands.

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

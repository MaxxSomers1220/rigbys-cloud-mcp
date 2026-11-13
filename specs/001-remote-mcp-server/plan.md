# Implementation Plan: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md`
- Constitution: `.specify/memory/constitution.md` v1.0.0
- Date: 2026-11-12

Status: Draft plan for Codex (`$speckit-implement` target). Nothing built yet. The four Open Decisions were confirmed on 2026-11-12; setup checks remain pending.

## Implementation status — 2026-11-12

This document was restored from the supplied plan PDF. No implementation phase has started. The constitution remains unchanged and governs the following source-document conflict: constitution §6 says "Pre-sell before building" and "Do not sell until checked" for the employer IP / conflict check; the task list places its sale checkpoint at T6.3. The original plan called that checkpoint Phase 5, but it is Phase 6 in `tasks.md`. The later checkpoint does not waive the earlier constitutional gates.

On 2026-11-12, Maxx confirmed in chat that both gates are complete: the employer IP / conflict check is cleared, and one paid pre-sale is recorded. This is user-confirmed status, not an independent audit of clearance or sale evidence. These confirmations satisfy the constitutional gates for proceeding once Phase 0 checks pass; no constitutional amendment or waiver is made. T6.3 remains unchecked until its Phase 6 review in task order.

On 2026-11-12, Maxx confirmed GitHub and Railway are connected and reported a Railway trial with $5 in credits, expiring after 30 days or credit exhaustion. Railway permits databases during the trial (https://docs.railway.com/pricing/free-trial), so paid-plan activation is not a Phase 0 gate. The browser session available to Codex is still awaiting Railway sign-in/authorization. Domain ownership is user-confirmed; DNS routing, hosting project, and Postgres connectivity remain unchecked in Phase 0.

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
- **Pre-sell guardrail:** the task list includes a pre-sell checkpoint (Phase 6, T6.3) before registry listings or a second feed. Constitution §6 additionally requires pre-selling before building; Maxx confirmed the paid pre-sale on 2026-11-12 as recorded above.
- **Employer IP:** the source constitution records the check as unverified and prohibits selling until checked. Maxx confirmed clearance on 2026-11-12 as recorded above. No code or data from Maxx's institutional work may be used. Sources are public only (Grants.gov, RePORTER, OpenAlex).

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
- **Domain:** `mcp.rigbyscloud.com` → host. `rigbyscloud.com/redeem` → same service. HTTPS via host.

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

Additional deployment decision — **2026-11-12:** Maxx authorized using the already-owned `rigbyscloud.com` domain in place of the draft domain. Use `https://mcp.rigbyscloud.com/mcp` for MCP and `https://rigbyscloud.com/redeem` for redemption. This is a user-authorized update to the source draft's domain and client-command URLs; the four original decisions above remain unchanged.

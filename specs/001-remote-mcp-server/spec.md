# Feature Specification: Remote MCP Server for Grants Feed #1

- Feature Branch: `001-remote-mcp-server`
- Created: 2026-11-12

Status: Draft for implementation — converted from `Rigbys_Cloud_Remote_MCP_Spec_v1.md`

Input: User description: "Remote MCP first — hosted remote MCP server so Codex and Claude Code users can get to Rigby's Cloud grants feed with one command, no install, no SDK."

Source specs: `Rigbys_Cloud_Remote_MCP_Spec_v1.md`, `Rigbys_Cloud_Grants_Feed_API_Spec_v1.md`, `Rigbys_Cloud_AI_Enhanced_Feeds_Product_Definition.md`

Constitution: `.specify/memory/constitution.md` v1.0.0 — governs this spec. Conflicts resolve in favour of the constitution.

## User Scenarios & Testing (mandatory)

### User Story 1 — PI finds open grants in plain English (Priority: P1)

A PI (or small-builder agent user) working in Codex or Claude Code wants open NIH grants for their topic, due soon, without learning an API.

Why this priority: This is the core paid use case — the PI daily RFP check. If this does not work in one prompt, nothing else matters.

Independent Test: Connect with a real paid key in Codex, run the prompt below, and get correct deadlines + source links + gap scores back, with no code written by the user.

Acceptance Scenarios:

1. Given a paid key is connected in Codex, When the user prompts "Find open NIH grants for pediatric rare disease, due in the next 60 days, and tell me which ones are actually underfunded. Show the deadline and source link for each.", Then the agent calls `opportunity_search` then `opportunity_get` on the top 2–3 results, and answers with deadline, sponsor, gap score, and a Grants.gov source link for each.
2. Given the same prompt in Claude Code, When the user runs it, Then the same tools are called and the same fields are returned.
3. Given a topic with no open opportunities in the window, When the user searches, Then the agent says so plainly and suggests widening the deadline window — it does not invent an opportunity.

### User Story 2 — Buyer redeems a Gumroad pass and connects in one minute (Priority: P1)

A buyer purchases the MCP pass on Gumroad and needs to go from license key to a working agent connection without an account system or a dashboard.

Why this priority: If redemption is confusing, the $99 test fails for onboarding reasons, not product reasons.

Independent Test: Take a real Gumroad license key, redeem it, copy the two commands, connect in Codex, and run User Story 1.

Acceptance Scenarios:

1. Given a valid Gumroad license key, When the buyer pastes it at `https://rigbyscloud.com/redeem`, Then the page shows a single API key once, with the Codex and Claude Code copy-paste commands beside it.
2. Given the key is shown, When the buyer copies it into `RIGBYS_API_KEY` and runs the Codex command, Then `codex mcp list` shows `rigbys-cloud` and `/mcp` inside Codex shows it connected.
3. Given an invalid or already-redeemed license key, When the buyer submits it, Then the page shows a plain error ("That license key isn't valid / has already been redeemed") — no stack trace, no key issued.

### User Story 3 — Free user verifies the joining is real (Priority: P2)

A sceptical PI wants to check the feed is actually cleaned and joined before paying $99.

Why this priority: The free tier is the lead magnet. It must prove value without giving away the paid layers.

Independent Test: Connect with a free key and run a search; confirm the data is 7 days delayed and unscored, and that paid tools refuse cleanly.

Acceptance Scenarios:

1. Given a free key, When the user calls `opportunity_search`, Then results return with no scores and no `summary_short`, and every record carries a `feed_generated_at` at least 7 days old.
2. Given a free key, When the agent tries `opportunity_get`, `opportunity_links`, or `gap_for_topic`, Then the server returns a plain error stating that tool requires a paid pass, with a link to buy — not an empty result.

### User Story 4 — Funder gets a gap read for a topic (Priority: P2)

A funder (or PI thinking like one) wants to know what is neglected vs crowded in a topic, from the same data.

Why this priority: This is the two-sided promise — same map, grantseekers and funders. It is also the paid-insight funnel.

Independent Test: With a paid key, call `gap_for_topic` for a real topic and verify the counts and top-5 lists are traceable to source counts.

Acceptance Scenarios:

1. Given a paid key and a topic, When the agent calls `gap_for_topic`, Then the result includes open-opportunity count, awarded-grant count, paper count, median growth/momentum/novelty/gap, top 5 neglected sub-topics, and top 5 crowded sub-topics, each with `methodology_version` and source counts.
2. Given a topic with very little data, When the gap read runs, Then it says the sample is thin and shows the counts — it does not present a confident gap score from a handful of records.

### Edge Cases

- Expired key: server returns 401 with "Key expired — renew at rigbyscloud.com". No stack trace.
- Revoked / rotated key: old key dies immediately on rotation; new key works at once.
- Feed build fails on a given day: tools return the last good feed with its `feed_generated_at` visible — never silently serve stale data as fresh.
- Rate limit hit: server returns 429 with `Retry-After`. Paid: 1,000 tool calls/day. Free: 20 searches/day (confirmed 2026-11-12).
- No trials in v1: `linked_trials[]` is omitted from all outputs. Do not return it empty with a promise, and do not claim trial linkage in tool descriptions.

## Requirements (mandatory)

### Functional Requirements

- **FR-001:** System MUST expose a remote MCP server over Streamable HTTP at `https://mcp.rigbyscloud.com/mcp`, server name `rigbys-cloud`, version `1.0.0`. No SSE transport in v1.
- **FR-002:** System MUST expose exactly four tools in v1: `opportunity_search`, `opportunity_get`, `opportunity_links`, `gap_for_topic`. No additional tools without a named user story.
- **FR-003:** `opportunity_search` MUST accept `topic` (required string), `sponsor` (optional), `deadline_before` / `deadline_after` (optional ISO dates), `min_gap_score` (optional 0–100), `limit` (default 10, max 25), and MUST return compact records with `opportunity_id`, `title_normalized`, `sponsor_normalized`, `deadline_parsed`, `award_amount_parsed`, scores, `summary_short`, and `source_refs`.
- **FR-004:** `opportunity_get` MUST accept `opportunity_id` (required) and MUST return the full unified record: all five layers (cleaned, joined, scored, summarized, fresh/traceable), with `linked_awards[]` and `linked_papers[]` each carrying `join_confidence`, scores 0–100 with `methodology_version`, `summary_short`, `extracted_requirements[]`, `feed_generated_at`, per-field `source_refs`, and `change_log`.
- **FR-005:** `opportunity_links` MUST accept `opportunity_id` (required) and MUST return edges only — opportunity → awards (NIH RePORTER project numbers) → papers (OpenAlex work IDs) — each with `join_confidence` and source URL. No scores, no summaries.
- **FR-006:** `gap_for_topic` MUST accept `topic` (required) and `window_months` (default 12), and MUST return open-opportunity count, awarded-grant count, paper count, median growth/momentum/novelty/gap, top 5 neglected sub-topics, top 5 crowded sub-topics, source counts, and `methodology_version`.
- **FR-007:** System MUST authenticate with `Authorization: Bearer <RIGBYS_API_KEY>`. No OAuth in v1. Keys are `rgby_live_…` (paid) / `rgby_free_…` (free).
- **FR-008:** System MUST enforce the free tier: `opportunity_search` only, 7-day-delayed data, no scores, no `summary_short`. The other three tools MUST refuse free keys with a plain paid-required error.
- **FR-009:** System MUST enforce expiry: a key's clock starts at redemption, not purchase. Expired keys return 401 with a plain renewal message.
- **FR-010:** System MUST support key rotation from the redeem page: new key works immediately, old key is revoked immediately. No dashboard in v1.
- **FR-011:** System MUST provide a redeem page at `https://rigbyscloud.com/redeem` that accepts a Gumroad license key (plus an email for key recovery) and shows the API key once, with the Codex and Claude Code commands beside it. No account creation beyond that email.
- **FR-012:** System MUST serve the feed from Grants.gov + NIH RePORTER + OpenAlex only in v1. Open opportunities refresh daily; awards/papers weekly in v1 (daily is the goal).
- **FR-013:** Every record MUST carry `feed_generated_at`, per-field `source_refs`, and `methodology_version` on every scored record.
- **FR-014:** System MUST be read-only in v1. No write tools.
- **FR-015:** System MUST ship a one-page `SKILL.md`, `llms.txt`, `agents.md`, and a GitHub README that leads with the two copy-paste client commands (see §Client Setup below).

### Client Setup (normative — print exactly these)

Codex:

```bash
export RIGBYS_API_KEY="rgby_live_…"
codex mcp add rigbys-cloud --url https://mcp.rigbyscloud.com/mcp --bearer-token-env-var RIGBYS_API_KEY
```

Verify: `codex mcp list`, then `/mcp` inside Codex.

Claude Code:

```bash
export RIGBYS_API_KEY="rgby_live_…"
claude mcp add --transport http rigbys-cloud https://mcp.rigbyscloud.com/mcp --header "Authorization: Bearer $RIGBYS_API_KEY" --scope user
```

Verify: `/mcp` inside Claude Code — server should say Connected.

### Key Entities

- Opportunity (unified record): one open federal opportunity, joined across Grants.gov + NIH RePORTER + OpenAlex. Fields per FR-004. Stable `opportunity_id`, `dedupe_key`, `source_ids[]`.
- Award link: NIH RePORTER project number + URL + `join_confidence`.
- Paper link: OpenAlex work ID + URL + `join_confidence`.
- API key: `rgby_live_…` / `rgby_free_…`, with `expires_at`, tier, email (recovery only), `rotated_at`. One key per buyer.
- Gumroad license: license key as issued by Gumroad, redeemed once, mapped to one API key.

### Non-Functional Requirements

- **NFR-001:** Server MUST be a small always-on Railway service (confirmed 2026-11-12), not a serverless function that sleeps. HTTPS provided by the host.
- **NFR-002:** Secrets (API keys, database URL, Gumroad verification) MUST live in environment variables only, never in code, config, or git.
- **NFR-003:** Errors MUST be plain messages, no stack traces, for 401 / 403 / 429 / paid-required cases.
- **NFR-004:** Paid rate limit 1,000 tool calls/day, free 20 searches/day (confirmed 2026-11-12). Limits are abuse protection, stated on the redeem page, not per-call billing.

## Success Criteria (mandatory)

- **SC-001:** A new buyer can go from Gumroad purchase to a working Codex connection and a correct answer to the User Story 1 prompt in under 10 minutes, with no support contact.
- **SC-002:** The User Story 1 prompt returns correct deadlines and Grants.gov source links for at least 90% of returned opportunities on a spot-check of 10, verified against Grants.gov.
- **SC-003:** Free-tier search returns no scores and no summaries, and paid tools refuse free keys cleanly, in 100% of tested cases.
- **SC-004:** An expired key returns 401 with the renewal message, and a rotated key's old value stops working immediately, in 100% of tested cases.
- **SC-005:** One paid pass is sold (the pre-sell validation signal) before subscription/API machinery or a second feed is built.

## Scope

In scope (v1): feed build (Grants.gov + NIH RePORTER + OpenAlex), Postgres store, remote MCP server with 4 tools, Bearer auth, Gumroad redeem page, free tier, SKILL.md / llms.txt / agents.md / README, deployment to Railway (confirmed 2026-11-12), testing from Codex + Claude Code.

Out of scope (v1): local/stdio MCP server, OAuth, subscriptions / auto-renew, dashboard, write tools, bulk-dump tool, trials linkage (ClinicalTrials.gov), patents/global coverage, second feed, MCP registry listings before the server is live and tested, snapshot file build (separate product — its listing draft already exists).

## Open Decisions (for Maxx — do not guess)

All four decisions confirmed by Maxx on **2026-11-12**, asked and answered individually in chat:

1. **Price/duration:** $99 one-time for a 90-day MCP access pass. The 90 days start at redemption, not purchase. No subscription or auto-renewal.
2. **Rate limits:** paid 1,000 tool calls/day; free 20 searches/day.
3. **Hosting:** Railway.
4. **Stack:** Python + FastAPI + FastMCP; Python 3.12 per the plan.

Additional deployment decision — **2026-11-12:** Maxx authorized using the already-owned `rigbyscloud.com` domain in place of the draft domain. The MCP endpoint is `https://mcp.rigbyscloud.com/mcp` and redemption is `https://rigbyscloud.com/redeem`. This user-authorized deviation updates all URLs and normative client commands above; it does not add a fifth Open Decision.

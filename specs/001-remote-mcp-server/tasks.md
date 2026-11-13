# Tasks: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md` | Plan: `plan.md`

How to run: In Codex, from the project root, use the Spec Kit skills mode: `$speckit-tasks` to regenerate, `$speckit-implement` to build. Work phases in order — do not start a phase until the previous phase's checks pass. Mark each task [x] only when its check passes.

## Implementation status — 2026-11-12

Restored from the supplied task-list PDF. T0.1 and T0.2 have passed: all four decisions are dated in `spec.md` and `plan.md`, and the public GitHub repository contains committed copies of the constitution, spec, plan, and tasks. DNS routing (T0.3) and Railway/Postgres setup (T0.4) remain pending. Phase 1 has not started. Stop after each phase and show Maxx what passed its checks before moving on.

Constitution §6 requires "Pre-sell before building" and says "Do not sell until checked" for the employer IP / conflict check. This conflicts with postponing sale validation to T6.3. T6.3 remains in its original phase as a later verification checkpoint; it does not waive the constitution's earlier gates.

On 2026-11-12, Maxx confirmed in chat that the employer IP / conflict check is cleared and one paid pre-sale is recorded. These are user confirmations, not independently audited clearance or sale evidence. The constitutional gates are satisfied by these confirmations; Phase 1 may begin once Phase 0 checks pass and its results have been shown to Maxx. No constitutional amendment or waiver is made. T6.3 remains unchecked until its Phase 6 review in task order.

Domain update confirmed 2026-11-12: use Maxx's already-owned `rigbyscloud.com`. Maxx reports the Railway account still needs creating. T0.3 and T0.4 remain unchecked until DNS routing and database connectivity checks pass; T0.2 remains unchecked until the restored documents are committed and pushed to the public repo.

## Phase 0 — Decisions & setup (blocking)

- [x] **T0.1** Resolve Open Decisions 1–4 in `plan.md`: price/duration, rate limits, hosting, stack. Confirmed 2026-11-12: $99 one-time / 90 days from redemption; paid 1,000 tool calls/day and free 20 searches/day; Railway; Python 3.12 + FastAPI + FastMCP.
  - Check: decisions recorded in `spec.md` Open Decisions section, dated. **Passed 2026-11-12.**
- [x] **T0.2** Create GitHub repo `rigbys-cloud-mcp` (public), add `.specify/` + `specs/001-remote-mcp-server/` from this folder.
  - Check: repo exists, constitution + spec + plan + tasks are committed.
  - **Passed 2026-11-12:** public repository https://github.com/MaxxSomers1220/rigbys-cloud-mcp, commit `97c1f8c`. All four committed documents were fetched from GitHub and matched the reviewed local files.
- [ ] **T0.3** Buy / confirm domain `rigbyscloud.com`, point DNS at the chosen host (do not deploy yet).
  - Check: DNS resolves to host (or host placeholder page loads over HTTPS).
  - Status 2026-11-12: Maxx confirmed ownership and approved using this existing domain. Public NS lookup confirms AWS Route 53 nameservers. `mcp.rigbyscloud.com` does not yet resolve; Railway routing has not been configured.
- [ ] **T0.4** Create Railway hosting project + Postgres, set env vars `DATABASE_URL` only for now — no secrets in repo.
  - Check: empty Postgres reachable from a local migration run.
  - Status 2026-11-12: Maxx needs to create a Railway account. No project or database has been provisioned, `DATABASE_URL` is not configured locally, and the database connection check has not run.

## Phase 1 — Feed build (feed first, server second)

- [ ] **T1.1** Implement Grants.gov fetcher: POST `search2` + `fetchOpportunity`, paginated, store raw responses.
  - Check: fetcher returns ≥ 100 open opportunities with deadlines, run logged with count.
- [ ] **T1.2** Implement NIH RePORTER fetcher (`/v2`, awards) and OpenAlex fetcher (`/works`, papers/linkage).
  - Check: both return records with IDs that join to at least one Grants.gov opportunity in a sample.
- [ ] **T1.3** Implement cleaning: normalize titles/sponsors, parse `deadline_parsed` (ISO), `eligibility_parsed[]`, `award_amount_parsed`, `dedupe_key`, `source_ids[]`.
  - Check: 20 hand-checked Grants.gov records parse correctly (deadline + amount + eligibility match the source page).
- [ ] **T1.4** Implement joining: link opportunities → awards → papers with `join_confidence` per link; store in `opportunity_links`.
  - Check: sample of 20 joined records — at least 80% of links are correct on manual review; no trial links created.
- [ ] **T1.5** Implement scoring: `growth_score`, `momentum_score`, `novelty_score`, `gap_score` (0–100), with `methodology_version` stamped on every record. Document the methodology in one page (`docs/scoring-methodology.md`).
  - Check: scores are deterministic for the same input; corn-in-a-rut fixture (high funding + papers, low novelty/momentum) scores low on novelty/momentum.
- [ ] **T1.6** Implement summarizing: `summary_short` + `extracted_requirements[]` per opportunity.
  - Check: 10 summaries read correctly against their source opportunity — no invented deadlines or amounts.
- [ ] **T1.7** Create Postgres schema (`opportunities`, `opportunity_links`, `api_keys`, `redemptions`, `rate_limit_counters`) + indexes from `plan.md`.
  - Check: migrations run clean on a fresh database.
- [ ] **T1.8** Wire the feed builder as a scheduled job: daily Grants.gov, weekly RePORTER/OpenAlex in v1. Log `feed_generated_at` + per-source counts every run.
  - Check: a full build runs end-to-end and `/health` (stub) would report its timestamp.

**Phase 1 gate:** a full feed exists in Postgres with all five layers, and SC-002 spot-check (10 records vs Grants.gov) passes. Do not start Phase 2 until it does.

## Phase 2 — MCP server

- [ ] **T2.1** Scaffold FastAPI + FastMCP service, server name `rigbys-cloud`, version `1.0.0`, Streamable HTTP at `/mcp`, server instructions from `spec.md` §2.
  - Check: server starts locally, MCP Inspector connects and lists 4 tools.
- [ ] **T2.2** Implement `opportunity_search` (FR-003) as a thin read over Postgres.
  - Check: topic + deadline filters return the right records from seeded data; limit caps at 25.
- [ ] **T2.3** Implement `opportunity_get` (FR-004) — full unified record, all five layers.
  - Check: returned record matches the seeded record field-for-field, including `methodology_version` and `source_refs`.
- [ ] **T2.4** Implement `opportunity_links` (FR-005) — edges only.
  - Check: edges match `opportunity_links` table; no scores/summaries in output.
- [ ] **T2.5** Implement `gap_for_topic` (FR-006) — aggregation query.
  - Check: counts and top-5 lists match a hand-computed aggregation on seeded data.
- [ ] **T2.6** Implement auth middleware (FR-007–FR-010): Bearer check, tier + expiry, free-tier tool refusal, rate limits (paid 1,000 tool calls/day, free 20 searches/day, confirmed 2026-11-12), 401/429 plain messages.
  - Check: valid key passes; expired key → 401; free key on `opportunity_get` → paid-required error; rate limit → 429 with `Retry-After`.

## Phase 3 — Redeem page + keys

- [ ] **T3.1** Implement `/redeem`: form (Gumroad license key + email), verify license against Gumroad sale record (document the exact verification step in `docs/runbook.md`), generate API key, show once with Codex + Claude Code commands.
  - Check: valid license → key shown once; invalid/redeemed license → plain error, no key issued.
- [ ] **T3.2** Implement key storage: store `key_hash` only, never the raw key; `key_prefix` for support; `expires_at` = redemption + 90 days (confirmed 2026-11-12).
  - Check: raw key is not present in the database or logs after redemption.
- [ ] **T3.3** Implement rotation: new key works immediately, old key revoked immediately.
  - Check: old key returns 401 after rotation; new key passes.
- [ ] **T3.4** Implement `/health`: `feed_generated_at`, last build status per source, server version.
  - Check: endpoint returns JSON with all three fields.

## Phase 4 — Deploy

- [ ] **T4.1** Deploy service to Railway, `mcp.rigbyscloud.com` + `rigbyscloud.com/redeem` over HTTPS, env vars set in host dashboard.
  - Check: `https://mcp.rigbyscloud.com/mcp` responds; `/health` returns live feed timestamp.
- [ ] **T4.2** Run a full feed build in production; verify `/health` timestamp is today.
  - Check: production Postgres has a fresh feed (not seeded test data).
- [ ] **T4.3** Write `docs/runbook.md`: how to check feed health, rotate a key manually, verify a Gumroad license, and roll back a deploy.
  - Check: runbook covers all four procedures in under one page each.

## Phase 5 — Client verification (mandatory)

- [ ] **T5.1** MCP Inspector: connect to production URL with a paid key, call all 4 tools, verify outputs.
  - Check: all 4 tools return correct data, no errors.
- [ ] **T5.2** Codex: `codex mcp add rigbys-cloud --url https://mcp.rigbyscloud.com/mcp --bearer-token-env-var RIGBYS_API_KEY`, `codex mcp list`, `/mcp`, run User Story 1 prompt.
  - Check: SC-001 (under 10 min from purchase to answer) and SC-002 (90% deadlines/links correct on 10-record spot-check).
- [ ] **T5.3** Claude Code: `claude mcp add --transport http rigbys-cloud https://mcp.rigbyscloud.com/mcp --header "Authorization: Bearer $RIGBYS_API_KEY" --scope user`, `/mcp`, run User Story 1 prompt.
  - Check: same as T5.2, in Claude Code.
- [ ] **T5.4** Free tier + failure cases: free key search (no scores, 7-day delay), free key on paid tool (paid-required), expired key (401), rate limit (429).
  - Check: SC-003 and SC-004 pass 100%.

## Phase 6 — Discovery files + pre-sell

- [ ] **T6.1** Write `SKILL.md` (one page, see `spec.md` §6) + `llms.txt` + `agents.md`, install paths documented for Codex and Claude Code.
  - Check: skill file states when to use Rigby's, when not to, the 4 tools, how to read scores, and the "always show source URL + deadline" rule.
- [ ] **T6.2** Write GitHub README leading with the two copy-paste commands, then the skill file, then the tool table.
  - Check: a new user can connect from the README alone, without opening another doc.
- [ ] **T6.3** Pre-sell checkpoint: one paid pass sold (SC-005) before any registry listing or second feed.
  - Check: Gumroad sale recorded; do not list in registries until this passes.
- [ ] **T6.4** (After T6.3 only) List in MCP registries / directories.
  - Check: listings point at the live URL and the README, and were verified live after listing.

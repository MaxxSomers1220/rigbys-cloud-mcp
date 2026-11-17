# Tasks: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md` | Plan: `plan.md`

How to run: In Codex, from the project root, use the Spec Kit skills mode: `$speckit-tasks` to regenerate, `$speckit-implement` to build. Work phases in order — do not start a phase until the previous phase's checks pass. Mark each task [x] only when its check passes.

## Current status — 2026-11-17

Phase 1 completed under Maxx's explicit instruction after the correction below.
T1.1–T1.8 and the local Postgres gate passed; **STOP before Phase 2**. Automated
checks: 52 passed. No paid pass has been sold as of 2026-11-16, and T6.3 remains
unchecked. Maxx states this project is definitely not part of what he does for
work; no broader employer IP clearance is claimed. No production deployment.

## Implementation status — 2026-11-12

Restored from the supplied task-list PDF. **All four Phase 0 tasks passed on 2026-11-12:** decisions are dated, the public GitHub repository contains the committed governing documents, DNS routes the approved hostname to Railway, and the local empty-Postgres TLS migration preflight passed with temporary public access removed afterward. **STOP before Phase 1 and show Maxx these results for phase review. Phase 1 has not started; all 29 later tasks remain unchecked.** Stop after each phase and show Maxx what passed its checks before moving on.

Constitution §6 requires "Pre-sell before building" and says "Do not sell until checked" for the employer IP / conflict check. This conflicts with postponing sale validation to T6.3. T6.3 remains in its original phase as a later verification checkpoint; it does not waive the constitution's earlier gates.

Correction recorded 2026-11-17: as of 2026-11-16, NO paid pass has been sold; presale is still no. The earlier claim of a paid pre-sale on 2026-11-12 was incorrect. Maxx states this project is definitely not part of what he does for work; no broader employer IP clearance is claimed. The pre-sale gate is not satisfied. T6.3 remains unchecked. Maxx has explicitly instructed Phase 1 feed work only in this session despite the absent pre-sale; this does not claim a sale, change the constitution, or authorize Phase 2 or selling.

Domain update confirmed 2026-11-12: use `mcp.rigbyscloud.com`, under Maxx's already-owned domain, for both `/mcp` and `/redeem`; root/apex routing is not a v1 prerequisite. Maxx confirmed GitHub and Railway are connected and reported an existing Railway trial with $5 in credits for up to 30 days. Paid-plan activation is not required for Phase 0 setup. Maxx approved temporary public access to empty Postgres for the local TLS migration check, with immediate removal afterward. DNS routing, local database connectivity, and public-access removal are now verified; T0.1–T0.4 have passed. The application remains undeployed.

## Phase 0 — Decisions & setup (blocking)

- [x] **T0.1** Resolve Open Decisions 1–4 in `plan.md`: price/duration, rate limits, hosting, stack. Confirmed 2026-11-12: $99 one-time / 90 days from redemption; paid 1,000 tool calls/day and free 20 searches/day; Railway; Python 3.12 + FastAPI + FastMCP.
  - Check: decisions recorded in `spec.md` Open Decisions section, dated. **Passed 2026-11-12.**
- [x] **T0.2** Create GitHub repo `rigbys-cloud-mcp` (public), add `.specify/` + `specs/001-remote-mcp-server/` from this folder.
  - Check: repo exists, constitution + spec + plan + tasks are committed.
  - **Passed 2026-11-12:** public repository https://github.com/MaxxSomers1220/rigbys-cloud-mcp, commit `97c1f8c`. All four committed documents were fetched from GitHub and matched the reviewed local files.
- [x] **T0.3** Confirm hostname `mcp.rigbyscloud.com` under the already-owned domain and point its DNS at the chosen host (do not deploy yet). Maxx authorized this amendment on 2026-11-12: both `/mcp` and `/redeem` use this hostname; root/apex routing is not a v1 prerequisite.
  - Check: `mcp.rigbyscloud.com` DNS resolves to the allocated Railway host (or its host placeholder page loads over HTTPS).
  - **Passed 2026-11-12:** public DNS resolves `mcp.rigbyscloud.com` CNAME to `cinv31ig.up.railway.app`, and the ownership TXT value exactly matches Railway's requirement. Only the two required DNS records were added to the Route 53 zone (five records became seven). Railway target port is `8000`; the application has no connected source and no active deployment. This passes the DNS check without claiming TLS certificate issuance or a working HTTP application.
- [x] **T0.4** Create Railway hosting project + Postgres, set env vars `DATABASE_URL` only for now — no secrets in repo.
  - Check: empty Postgres reachable from a local migration run.
  - **Passed 2026-11-12:** project `rigbys-cloud-mcp` and Postgres are provisioned, and the empty application's only user variable is its `DATABASE_URL` reference, committed through the configuration-only action without deploying the application. The actual local Python migration preflight connected to hosted PostgreSQL 18.6 over TLS, verified an empty database and public-schema CREATE privilege, and rolled back temporary DDL/DML; its probe was absent afterward and no Phase 1 tables were created. The approved temporary public proxy was immediately removed; a connection using the same credentials to the old endpoint was rejected. Railway showed Postgres Online, no public proxy, Add Public Access available, and no staged changes remaining. Infrastructure IDs and evidence are recorded in `plan.md`; no credentials or connection URLs are stored here.

**Phase 0 gate passed — STOP:** show Maxx the four passed checks above and wait for phase review before starting Phase 1.

## Phase 1 — Feed build (feed first, server second)

- [x] **T1.1** Implement Grants.gov fetcher: POST `search2` + `fetchOpportunity`, paginated, store raw responses.
  - Check: fetcher returns ≥ 100 open opportunities with deadlines, run logged with count.
  - **Passed 2026-11-17:** 828 posted records, 781 source deadlines, paginated raw archives. `docs/evidence/t1-1.json`.
- [x] **T1.2** Implement NIH RePORTER fetcher (`/v2`, awards) and OpenAlex fetcher (`/works`, papers/linkage).
  - Check: both return records with IDs that join to at least one Grants.gov opportunity in a sample.
  - **Passed 2026-11-17:** 14,601 scoped awards and 138,804 unique OpenAlex works; exact identifier sample and complete partition counts. Bulk works use explicit OpenAlex award-core metadata; optional RePORTER PMID route separately verified. `docs/evidence/t1-2.json`.
- [x] **T1.3** Implement cleaning: normalize titles/sponsors, parse `deadline_parsed` (ISO), `eligibility_parsed[]`, `award_amount_parsed`, `dedupe_key`, `source_ids[]`.
  - Check: 20 hand-checked Grants.gov records parse correctly (deadline + amount + eligibility match the source page).
  - **Passed 2026-11-17:** 20/20 source reviews; expired/unresolved calls excluded, rolling dates and zero/unknown amounts preserved. `docs/evidence/t1-3-review.json`.
- [x] **T1.4** Implement joining: link opportunities → awards → papers with `join_confidence` per link; store in `opportunity_links`.
  - Check: sample of 20 joined records — at least 80% of links are correct on manual review; no trial links created.
  - **Passed 2026-11-17:** 20 joined-record reviews plus 20 complete chains; final published direct edges 20/20 correct, no trial links. All edges stored in Postgres. `docs/evidence/t1-4-review.json`, `t1-4-chains-supplement.json`, `t1-4-published-direct.json`.
- [x] **T1.5** Implement scoring: `growth_score`, `momentum_score`, `novelty_score`, `gap_score` (0–100), with `methodology_version` stamped on every record. Document the methodology in one page (`docs/scoring-methodology.md`).
  - Check: scores are deterministic for the same input; corn-in-a-rut fixture (high funding + papers, low novelty/momentum) scores low on novelty/momentum.
  - **Passed 2026-11-17:** Determinism, bounds and saturated corn-in-a-rut fixture pass; thin/unsupported coverage flagged neutral. `docs/evidence/t1-5.json` and `tests/test_scoring.py`.
- [x] **T1.6** Implement summarizing: `summary_short` + `extracted_requirements[]` per opportunity.
  - Check: 10 summaries read correctly against their source opportunity — no invented deadlines or amounts.
  - **Passed 2026-11-17:** 10/10 source-bound summaries; no invented deadlines or amounts. `docs/evidence/t1-6-review.json`.
- [x] **T1.7** Create Postgres schema (`opportunities`, `opportunity_links`, `api_keys`, `redemptions`, `rate_limit_counters`) + indexes from `plan.md`.
  - Check: migrations run clean on a fresh database.
  - **Passed 2026-11-17:** Fresh PostgreSQL migrations, indexes, checksum/rollback and chunked-cache checks pass (9 database tests). `docs/evidence/t1-7.json` and `tests/test_database.py`.
- [x] **T1.8** Wire the feed builder as a scheduled job: daily Grants.gov, weekly RePORTER/OpenAlex in v1. Log `feed_generated_at` + per-source counts every run.
  - Check: a full build runs end-to-end and `/health` (stub) would report its timestamp.
  - **Passed 2026-11-17:** Complete Postgres build and weekly-cache rerun passed; health JSON reports the successful timestamp and source counts. Daily schedule definition in `deploy/feed.crontab`; not activated on host. `docs/evidence/t1-8-build.json`.

**Phase 1 gate passed locally — 2026-11-17:** 789/789 records carry the five pipeline layers; 14,411 award links and 147,744 paper links are stored. SC-002: 10/10 stored deadlines/links match fresh Grants.gov, all source pages HTTP 200 (`docs/evidence/sc-002.json`). Feed timestamp: `2026-11-17T04:54:38.690560+00:00`. Confirmed research links exist for 165 opportunities; 756 records have explicitly flagged neutral scores for insufficient evidence, not observed gaps. Source retrieval times and coverage remain visible. Railway production and HTTP/client verification are later-phase work. **STOP before Phase 2.**

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

- [ ] **T4.1** Deploy service to Railway, serving `https://mcp.rigbyscloud.com/mcp` and `https://mcp.rigbyscloud.com/redeem` over HTTPS, env vars set in host dashboard.
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

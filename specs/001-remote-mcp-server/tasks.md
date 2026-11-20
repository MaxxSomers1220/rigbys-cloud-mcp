# Tasks: 001 Remote MCP Server

- Feature: `001-remote-mcp-server`
- Spec: `specs/001-remote-mcp-server/spec.md` | Plan: `plan.md`

How to run: In Codex, from the project root, use the Spec Kit skills mode: `$speckit-tasks` to regenerate, `$speckit-implement` to build. Work phases in order — do not start a phase until the previous phase's checks pass. Mark each task [x] only when its check passes.

## Current status — 2026-11-18

Phase 4 T4.1 and T4.2 production checks passed in order. The live feed contains 786
opportunities, and a real cron execution completed successfully with daily
Grants.gov retrieval and weekly research-cache reuse. T4.3 runbook review passed. Full suite: 261 passed, including all 227 Phase 3 tests. Earlier handoffs
below are historical. Phase 5 and Phase 6 remain unchecked and out of scope.

The existing one-time $99 Gumroad product is an unpublished draft with licensing
saved and its supplied product ID configured in Railway. No second product was
created. Live real-sale verification remains untested. No production test key,
synthetic license, seeded feed/history or real buyer sale was used. T6.3 stays
unchecked. Maxx states this project is definitely not part of what he does for
work; no broader employer IP clearance is claimed.

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

- [x] **T2.1** Scaffold FastAPI + FastMCP service, server name `rigbys-cloud`, version `1.0.0`, Streamable HTTP at `/mcp`, server instructions from `spec.md` §2.
  - Check: server starts locally, MCP Inspector connects and lists 4 tools.
  - **Passed 2026-11-17:** Actual MCP Inspector connected to local /mcp, initialized rigbys-cloud 1.0.0 and listed exactly four read-only tools; stateless Streamable HTTP JSON. `docs/evidence/phase2/t2-1-inspector.json`, `final-inspector.json`.
- [x] **T2.2** Implement `opportunity_search` (FR-003) as a thin read over Postgres.
  - Check: topic + deadline filters return the right records from seeded data; limit caps at 25.
  - **Passed 2026-11-17:** Seeded topic/sponsor/inclusive UTC-deadline filters, 10/25 limits, observed-only gap threshold and neutral flags pass; actual feed search returns source-backed results. `tests/test_mcp_search.py`, `test_mcp_review.py`, `docs/evidence/phase2/t2-2-search.json`.
- [x] **T2.3** Implement `opportunity_get` (FR-004) — full unified record, all five layers.
  - Check: returned record matches the seeded record field-for-field, including `methodology_version` and `source_refs`.
  - **Passed 2026-11-17:** Every seeded full record equals persisted JSON field-for-field; actual neutral record gg-355219 also matches exactly with all scores 50 and evidence flag retained. `tests/test_mcp_get.py`, `docs/evidence/phase2/t2-3-get.json`, `final-inspector.json`.
- [x] **T2.4** Implement `opportunity_links` (FR-005) — edges only.
  - Check: edges match `opportunity_links` table; no scores/summaries in output.
  - **Passed 2026-11-17:** Edges match stored fields and via_award topology, with confidence/URLs and no scores/summaries; actual six-edge graph verified by Inspector. `tests/test_mcp_links.py`, `docs/evidence/phase2/t2-4-links.json`.
- [x] **T2.5** Implement `gap_for_topic` (FR-006) — aggregation query.
  - Check: counts and top-5 lists match a hand-computed aggregation on seeded data.
  - **Passed 2026-11-17:** Hand-computed fixture: 8 opportunities, 6 distinct awards, 6 papers; score medians 35/45/55/65 and both top-five lists match. Neutral/mixed/empty/year-window cases pass; real thin topic produces no invented rankings. `tests/test_mcp_gap.py`, `docs/evidence/phase2/t2-5-gap.json`.
- [x] **T2.6** Implement auth middleware (FR-007–FR-010): Bearer check, tier + expiry, free-tier tool refusal, rate limits (paid 1,000 tool calls/day, free 20 searches/day, confirmed 2026-11-12), 401/429 plain messages.
  - Check: valid key passes; expired key → 401; free key on `opportunity_get` → paid-required error; rate limit → 429 with `Retry-After`.
  - **Passed 2026-11-17:** Valid keys and all four paid calls pass; missing/expired/revoked keys HTTP 401, free paid tools HTTP 403, caps 20/1000 HTTP 429 with Retry-After. Twenty concurrent paid attempts at 999 yield one success and nineteen 429s. Genuine sealed snapshots obey the exact seven-day boundary and exclude paid fields; current real history is honestly unavailable. `tests/test_mcp_auth.py`, `test_mcp_snapshots.py`, `test_mcp_http.py`, `docs/evidence/phase2/t2-6-http-review.json`, `final-inspector.json`.

**Phase 2 checks passed locally — STOP before Phase 3.** All 110 tests pass. No
public deployment or real buyer/key-issuance flow is claimed; temporary synthetic
credentials were cleaned up. The 789-record feed and its coverage limitations are
preserved. Free history must age naturally before real free results are available.

## Phase 3 — Redeem page + keys

- [x] **T3.1** Implement `/redeem`: form (Gumroad license key + email), verify license against Gumroad sale record (document the exact verification step in `docs/runbook.md`), generate API key, show once with Codex + Claude Code commands.
  - Check: valid license → key shown once; invalid/redeemed license → plain error, no key issued.
  - **Passed locally with synthetic credentials — 2026-11-17:** Synthetic Gumroad API and actual local form checks pass: valid receipt shows one key and both commands; invalid/refunded/wrong-owner/replayed licenses and sale aliases issue no extra key. Exact verification and missing live-product open item are documented in docs/runbook.md. `docs/evidence/phase3/t3-1-redemption.json`, `final-http-review.json`, `local-http-smoke.json`.
- [x] **T3.2** Implement key storage: store `key_hash` only, never the raw key; `key_prefix` for support; `expires_at` = redemption + 90 days (confirmed 2026-11-12).
  - Check: raw key is not present in the database or logs after redemption.
  - **Passed locally with synthetic credentials — 2026-11-17:** All database tables and captured logs were scanned: no full API key or license remains; hashes/prefix only. Expiry equals original redemption plus90days, not purchase time. `tests/test_key_storage.py`, `docs/evidence/phase3/t3-2-storage.json`.
- [x] **T3.3** Implement rotation: new key works immediately, old key revoked immediately.
  - Check: old key returns 401 after rotation; new key passes.
  - **Passed locally with synthetic credentials — 2026-11-17:** Actual HTTP old key401/new key200; original clock and quotas preserved, concurrency single winner, late-failure rollback and in-flight counters verified. 16service tests plus independent HTTP checks pass. `docs/evidence/phase3/t3-3-rotation.json`, `t3-3-http-review.json`, `local-http-smoke.json`.
- [x] **T3.4** Implement `/health`: `feed_generated_at`, last build status per source, server version.
  - Check: endpoint returns JSON with all three fields.
  - **Passed locally with synthetic credentials — 2026-11-17:** HTTP JSON includes actual feed_generated_at, per-source build status and server1.0.0; failures retain last successful timestamp and redact details. Actual real-feed timestamp remains2026-11-17T04:54:38.690560+00:00. `docs/evidence/phase3/t3-4-health.json`, `local-http-smoke.json`.

**Phase 3 local checks passed — STOP before Phase 4.** All227 tests pass. Live
Gumroad product/real-sale verification remains explicitly open; fixture success
is not sale evidence. No deployment or Railway schedule was activated.

## Phase 4 — Deploy

- [x] **T4.1** Deploy service to Railway, serving `https://mcp.rigbyscloud.com/mcp` and `https://mcp.rigbyscloud.com/redeem` over HTTPS, env vars set in host dashboard.
  - Check: `https://mcp.rigbyscloud.com/mcp` responds; `/health` returns live feed timestamp.
  - **Passed 2026-11-18:** GitHub source is connected; production HTTPS /redeem 200, unauthenticated /mcp 401, /health 200/server 1.0.0 with live feed_generated_at 2026-11-18T17:53:12.620386+00:00. First full production source build published 786 opportunities, 14,561 awards and 138,849 papers; all three sources ok. Both volumes 5 GB, job 6 GB memory; 261 tests pass. No production test keys, license submissions or seeded data. `docs/evidence/phase4/t4-1-deploy.json`.
- [x] **T4.2** Run a full feed build in production; verify `/health` timestamp is today.
  - Check: production Postgres has a fresh feed (not seeded test data).
  - **Passed 2026-11-18:** Production feed has 786 real opportunities, 14,371 award edges and 147,794 paper edges; source counts 14,561 awards/138,849 papers. The daily 06:00 UTC cron is active in the deployment manifest and next run is 2026-11-19T06:00Z. Manual cron execution 96945506-9d90-4e4c-b54f-8a026c564138 is EXITED with completedAt 2026-11-18T18:13:26.630Z; fresh Grants.gov and reused weekly research are confirmed by logs and /health. No timer occurrence is claimed yet. `docs/evidence/phase4/t4-2-feed-and-schedule.json`.
- [x] **T4.3** Write `docs/runbook.md`: how to check feed health, rotate a key manually, verify a Gumroad license, and roll back a deploy.
  - Check: runbook covers all four procedures in under one page each.
  - **Passed 2026-11-18:** The existing runbook now covers all four production procedures, each under 300 words/one page. Exact verification, hash-only handling, expiry/quota-preserving rotation, live feed/schedule checks and application-versus-data rollback limits are explicit. The existing Gumroad draft is configured; real-sale verification remains untested. `docs/evidence/phase4/t4-3-runbook.json`.

**Phase 4 gate passed — STOP before Phase 5/6.** All 261 tests pass, including the original 227. The real 786-record production feed, HTTPS endpoints and completed cron execution are verified. No production test keys, synthetic licenses, seeded history or buyer sale was used. T6.3 remains unchecked.

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

## Phase 7 — Paid current-feed export

- [x] **T7.1** Store the current and previous gzip exports in bounded PostgreSQL chunks. Publish each export in the transaction that publishes the final opportunity records and marks the build successful.
  - Check that a failed build or an export write failure preserves the last committed feed and artifact. After three successful publishes, confirm only the most recent two export artifacts remain. Verify a read that overlaps publication receives a single complete generation.
- [x] **T7.2** Serve `GET /snapshot-export` over the existing HTTPS service with Bearer auth, paid-tier enforcement, and shared UTC daily quota. Keep the MCP tool inventory at four.
  - Check gzip attachment filename, media type, gzip integrity, and private no-store caching. Confirm missing, malformed, invalid, revoked, and expired keys return 401, a free key returns the existing paid-required 403, and shared quota exhaustion returns 429 with `Retry-After`. Confirm an authorized paid caller receives 503 when no artifact exists and a token in the URL cannot grant access.
- [x] **T7.3** Verify User Story 5 and SC-006 locally with a controlled 786-record fixture, including an export that spans multiple chunks. Store test evidence under `docs/evidence/phase7/`.
  - Check unique IDs, total count, `feed_generated_at`, and full object equality for each fixture ID with the canonical record used by `opportunity_get`. Spot-check equality through MCP calls. Verify the four named tools remain discoverable and prove an export and an MCP request share the same paid counter. Label fixture evidence as controlled local data. Record measurements and redacted responses, excluding keys and full export files.
  - **Passed locally 2026-11-20:** T7.1–T7.3 results are in `docs/evidence/phase7/t7-3-local.md`.
- [ ] **T7.4** Verify the live behavior after an authorized Railway deployment and successful artifact publication. Test the HTTPS attachment with a real paid key supplied via the environment.
  - Check gzip integrity, unique IDs, matching JSON count, and `feed_generated_at` against the actual production run. Spot-check 10 records with `opportunity_get`, confirm the four-tool inventory, verify the free and expired responses with available credentials, and confirm retention after the next successful build. Record the production timestamp, observed count, and redacted evidence separately from the fixture report under `docs/evidence/phase7/`.

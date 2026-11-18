# Rigby's Cloud — Remote MCP Server (Spec Kit project)

Converted Nov 12, 2026 from `Rigbys_Cloud_Remote_MCP_Spec_v1.md`. Phases 1–3 implemented and locally verified on 2026-11-17. Phase 4 production service and scheduled feed verified on 2026-11-18; all three deployment checks passed. Live Gumroad verification is untested.

This folder is a Spec Kit project, ready for Codex. It follows GitHub Spec Kit layout: a constitution, one feature spec, a plan, and a task list.

Setup draft restored from the supplied README PDF on 2026-11-12. The final buyer-facing README is a Phase 6 deliverable. The HTTPS service and real production feed are live; buyer client verification has not started. All four Open Decisions were confirmed in chat on 2026-11-12 and recorded in the spec and plan. Correction recorded 2026-11-17: as of 2026-11-16, no paid pass has been sold; presale is still no. Maxx states this project is definitely not part of what he does for work. No broader employer IP clearance is claimed. All four Phase 0 setup checks passed on 2026-11-12. Phases 1–3 were explicitly authorized and their local checks are complete. Phase 4 is authorized; deployment and feed/schedule checks have passed, and the runbook check has passed. See the evidence in the plan and tasks.

## Phase 4 deployment — 2026-11-18

The Railway application is connected to this repository's main branch and serves
`https://mcp.rigbyscloud.com/mcp` and `/redeem` over HTTPS. A clean client verified
unauthenticated MCP 401, redeem 200 with a Secure cookie, and health 200/version 1.0.0.
`/health` now reports a real successful production feed, not a stub or seeded data.

Production collection retrieved 805 posted Grants.gov opportunities, 14,561 NIH
awards and 138,849 OpenAlex papers. The published feed contains 786 opportunities,
14,371 award edges and 147,794 paper edges; 160 opportunities have confirmed research
links. Evidence flags and neutral scores remain visible; missing coverage is not
a funding-gap finding. The latest verified feed timestamp is
`2026-11-18T18:10:23.488529+00:00`.

The separate `feed-builder` service uses 6 GB memory, 2 vCPU and a 5 GB raw-data volume;
Postgres also has 5 GB storage. Daily cron is `0 6 * * *` UTC: 01:00 Eastern during
standard time and 02:00 during daylight saving time. A manually triggered cron
execution completed successfully (`EXITED`, 204 seconds), proving fresh Grants.gov
retrieval and weekly research-cache reuse. The next timer run is
2026-11-19 at 06:00UTC (01:00 America/New_York); that future occurrence is not
claimed as observed. The schedule is enabled in the deployed configuration.

**261 tests pass**, retaining all 227 Phase 3 tests. T4.1–T4.3 passed; the
four-procedure operations runbook is reviewed and complete. No production test keys,
license submissions, real buyer sales or synthetic feed/history data were used.
Genuine free-search history must age seven days before delayed results exist.

The existing $99 MCP-pass Gumroad draft is unpublished with licensing saved. Its
supplied product ID is configured only in Railway; no second product was created.
**Real-sale verification remains untested.** No paid pass has been sold and T6.3
stays unchecked. Phase 5 and Phase 6 have not started.

[Deploy check](docs/evidence/phase4/t4-1-deploy.json) ·
[Feed and cron check](docs/evidence/phase4/t4-2-feed-and-schedule.json) ·
[Operations runbook](docs/runbook.md).
Earlier readiness/bootstrap reports and phase handoffs below are historical.

## Phase 3 handoff — 2026-11-17

The local `/redeem` page accepts a Gumroad license and matching email, verifies
the configured one-time $99 pass, and shows a new paid API key exactly once beside
the Codex/Claude Code commands. Only key/license hashes, support prefix and allowed
metadata persist. Expiry is exactly 90 days from original redemption.

Explicit replacement at `/redeem/rotate` immediately revokes the old key and
preserves the original expiry and daily quotas. `/health` now reads real feed-run
status, including last good timestamp and per-source statuses, with server1.0.0.
There are still exactly four read-only MCP tools; none of their evidence flags or
feed data was changed.

**All 227 tests pass**, including the existing 110. Independent local HTTP checks
and a smoke test against the real 789-record local feed passed. Every Gumroad
success was an injected synthetic fixture, not a real license check or sale.
Temporary test credentials were cleaned up and local test listeners stopped.

**Updated Gumroad status — 2026-11-18:** Maxx confirms the existing $99 MCP-pass
product is an unpublished draft with licensing saved. Its supplied product ID is
now configured in the Railway application environment; do not create a second
product. Live verification remains **untested**: no real license or sale is used
in Phase 4. Missing or invalid configuration fails closed. No paid pass has been
sold; T6.3 remains unchecked.

[Local runbook and exact verification](docs/runbook.md) · [Phase 3 evidence](docs/evidence/phase3/).
**Stop before Phase 4.** No deployment, Railway schedule activation or later-phase
work was performed. Earlier handoffs below are historical checkpoints.

## Phase 2 handoff — 2026-11-17

The local FastAPI/FastMCP service is implemented: `rigbys-cloud` version `1.0.0`,
stateless Streamable HTTP JSON at `/mcp`, exactly four read-only tools. Search,
full-record reads, stored edges and source-backed portfolio aggregation pass their
seeded Postgres checks. Neutral evidence flags and source timestamps are retained;
neutral placeholders are never turned into gap findings.

Bearer verification, redemption-based expiry, immediate revocation, free-tier
restrictions and atomic daily quotas are verified over real HTTP. Immutable basic
search snapshots implement genuine seven-day delay. The current real snapshot is
not old enough yet: free search returns `delayed_feed_unavailable` rather than
backdating data or falling back to current rows. Synthetic aged-snapshot tests
verify the eventual allowed response has no scores or summaries.

**All 110 automated tests pass**, including the original 52. Authenticated MCP
Inspector initializes the server, lists exactly four tools and calls all four
against the real 789-record Phase 1 feed. Test credentials/redemptions are synthetic
and are not sales; they were removed afterward. No paid pass has been sold and
T6.3 remains unchecked.

[Local setup and contracts](docs/mcp-service.md) · [Phase 2 evidence](docs/evidence/phase2/).
Stop before Phase 3: there is no redemption/key-issuance/rotation page, HTTP health
endpoint, public deployment or later-phase client verification. Railway remains
unchanged. The Phase 1 handoff below is the historical feed checkpoint.

## Phase 1 handoff — 2026-11-17

The feed builder, source clients, cleaning, exact-identifier joins, versioned
scoring, extractive summaries, Postgres migrations and daily job are implemented.
Run/setup instructions: [feed operations](docs/feed-operations.md). Data meaning:
[data contract](docs/feed-data-contract.md) and [scoring methodology](docs/scoring-methodology.md).

Live source collection: 828 posted Grants.gov records, 14,601 NIH awards and
138,804 OpenAlex papers. The isolated workspace Postgres feed contains **789**
current/rolling opportunities (39 expired or unresolved records excluded),
14,411 award links and 147,744 paper links. All 789 carry the five pipeline layers,
traceability and methodology version. SC-002 data spot-check: **10/10**, with all
10 source pages HTTP 200. Automated checks: **52 passed**.

Coverage is not complete research intelligence: **165** opportunities have
confirmed research links; **756** records have explicitly flagged neutral score
placeholders because evidence is insufficient. Only 33 have observed descriptive
proxy scores. Missing NIH/OpenAlex coverage does not mean an opportunity is
underfunded. See [evidence](docs/evidence/) for task checks and sampled source proof.

This is a local Postgres validation using live public data; Railway production
was not accessed or deployed and the host schedule is not activated. No Phase 2
MCP/auth code or later-phase redemption/client work has started. No paid pass has
been sold as of 2026-11-16; T6.3 remains unchecked. Maxx states this project is
definitely not part of what he does for work; no broader clearance is claimed.

## Layout

```text
rigbys-cloud-mcp/
├── README.md                          ← this file
├── .specify/
│   └── memory/
│       └── constitution.md            ← governing rules (v1.0.0) — outranks the spec on conflict
├── specs/
│   └── 001-remote-mcp-server/
│       ├── spec.md                    ← what to build (user stories, FR-001–FR-015, success criteria)
│       ├── plan.md                    ← how to build it (stack, data model, deployment, testing)
│       └── tasks.md                   ← phased checklist for $speckit-implement
└── .agents/
    └── skills/
        └── rigbys-cloud-grants/
            └── SKILL.md               ← skill file to ship with the server (draft in tasks Phase 6)
```

The diagram includes the planned Phase 6 skill path; it has not been created during setup.

## How to use it with Codex

Spec Kit supports Codex CLI in skills mode — the commands start with `$`, not `/`:

```bash
# 1. From this project folder, in Codex:
#    (if you haven't installed the Spec Kit skills for Codex yet)
specify init . --ai codex --ai-skills
#    — or, on newer Spec Kit: specify init . --integration codex --integration-options="--skills"

# 2. Review the constitution + spec first:
$spec-kit-constitution   # read .specify/memory/constitution.md
#    (or just open the files — the point is Codex works from these, not from chat)

# 3. When the Open Decisions in plan.md are resolved, build it:
$speckit-implement
#    — works through specs/001-remote-mcp-server/tasks.md, phase by phase.
#    Do not skip Phase 1 (feed) — the MCP server is a thin read over a working feed.
```

Do not run `$speckit-implement` until the four Open Decisions in `plan.md` are resolved. Confirmed 2026-11-12: $99 one-time / 90 days from redemption; paid 1,000 tool calls/day and free 20 searches/day; Railway; Python 3.12 + FastAPI + FastMCP. These decisions do not waive the constitution or the remaining phase checks. Stop after each phase and show its passed checks before moving on.

## What this is

- **Product:** Rigby's Cloud Grants Feed #1, served as a hosted remote MCP server.
- **Server:** Streamable HTTP at `https://mcp.rigbyscloud.com/mcp`, server name `rigbys-cloud`.
- **Auth:** one Bearer API key per buyer, from a Gumroad license redeemed at `https://mcp.rigbyscloud.com/redeem`. Maxx confirmed on 2026-11-12 that MCP and redemption share this hostname; root/apex routing is not a v1 prerequisite.
- **Tools (4 only):** `opportunity_search`, `opportunity_get`, `opportunity_links`, `gap_for_topic`. Read-only.
- **Pay:** timed MCP pass ($99 one-time / 90 days from redemption, confirmed 2026-11-12) + $99 one-time snapshot file (separate product). No subscriptions for now.
- **Free tier:** `opportunity_search` only, 7-day-delayed, no scores/summaries; 20 searches/day (confirmed 2026-11-12).

## Source specs (the pre-Spec Kit versions)

- `../../files/Rigbys_Cloud_Remote_MCP_Spec_v1.md` — the MCP spec this was converted from
- `../../files/Rigbys_Cloud_Grants_Feed_API_Spec_v1.md` — unified record + API reads
- `../../files/Rigbys_Cloud_AI_Enhanced_Feeds_Product_Definition.md` — product definition, five layers, pay layer
- `../../files/Gumroad_Snapshot_Listing_Draft.md` — snapshot listing (separate product, still live)

These are historical references from the supplied README PDF; those original source files are not present in this checkout.

## Guardrails (from the constitution)

- Outside chance only, narrow and consulting-first — pre-sell before building. One paid pass is the validation signal.
- Employer IP / conflict check: the source constitution records it as unverified and says do not sell until checked. Maxx states this project is definitely not part of what he does for work; no broader clearance is claimed.
- Dropped directions stay dropped: research-ops, governance/catalog, adherence.
- No trials in v1. No subscriptions for now. Secrets in env vars only.

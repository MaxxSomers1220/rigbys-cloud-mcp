# Rigby's Cloud — Remote MCP Server (Spec Kit project)

Converted Nov 12, 2026 from `Rigbys_Cloud_Remote_MCP_Spec_v1.md`. Phase 1 feed and Phase 2 local MCP service implemented and verified on 2026-11-17. Nothing is deployed.

This folder is a Spec Kit project, ready for Codex. It follows GitHub Spec Kit layout: a constitution, one feature spec, a plan, and a task list.

Setup draft restored from the supplied README PDF on 2026-11-12. The final buyer-facing README is a Phase 6 deliverable; the production service and buyer client connections are not live or verified. All four Open Decisions were confirmed in chat on 2026-11-12 and recorded in the spec and plan. Correction recorded 2026-11-17: as of 2026-11-16, no paid pass has been sold; presale is still no. Maxx states this project is definitely not part of what he does for work. No broader employer IP clearance is claimed. All four Phase 0 setup checks passed on 2026-11-12. Phase 1 and Phase 2 were explicitly authorized and are complete; work stops before Phase 3. See the evidence in the plan and tasks.

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

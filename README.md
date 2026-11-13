# Rigby's Cloud — Remote MCP Server (Spec Kit project)

Converted Nov 12, 2026 from `Rigbys_Cloud_Remote_MCP_Spec_v1.md`. Nothing built yet.

This folder is a Spec Kit project, ready for Codex. It follows GitHub Spec Kit layout: a constitution, one feature spec, a plan, and a task list.

Setup draft restored from the supplied README PDF on 2026-11-12. The final buyer-facing README is a Phase 6 deliverable; the service and client connections are not live or verified. All four Open Decisions were confirmed in chat on 2026-11-12 and recorded in the spec and plan. Maxx also confirmed employer IP clearance and one paid pre-sale on 2026-11-12; these statements have not been independently audited. All four Phase 0 setup checks passed on 2026-11-12. Work is stopped before Phase 1 for phase review; see the evidence in the plan and tasks.

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
- Employer IP / conflict check: the source constitution records it as unverified and says do not sell until checked. Maxx confirmed clearance on 2026-11-12, as recorded in the plan and tasks.
- Dropped directions stay dropped: research-ops, governance/catalog, adherence.
- No trials in v1. No subscriptions for now. Secrets in env vars only.

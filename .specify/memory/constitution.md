# Rigby's Cloud — Constitution

Version 1.0.0 — Nov 12, 2026. Ratified by Maxx's decisions in chat Nov 6–12, 2026. This file is the governing constitution for all Spec Kit work under Rigby's Cloud. It outranks individual specs when they conflict. Amend it only with Maxx's explicit approval.

## 1. What Rigby's Cloud is

Rigby's Cloud is a feed company. Its purpose is AI-enhanced data feeds, plus access to them — so agents (and humans) can consume the feeds directly.

Grants Feed #1 is the first feed, not the only one. Future feeds get the same five-layer treatment, different domain.

## 2. The five layers — non-negotiable

"AI-enhanced" means an agent can trust the feed and use it without doing the hard work itself. All five layers are the product, not a pick-and-choose list:

1. Cleaned — deduped, normalized, deadlines and eligibility actually parsed out of messy source text, not just copied.
2. Joined — one record, linked across sources and traceable back to them.
3. Scored — growth, momentum, novelty, gap (0–100, versioned methodology). Signals an agent cannot get from the raw source.
4. Summarized — a short, structured plain-language read: what it is, who it's for, key dates and requirements.
5. Fresh and traceable — updated daily for open opportunities, with a timestamp and a source link on every claim, so an agent can cite it and a human can check it.

If a build drops a layer, it is not a Rigby's Cloud feed. Say so in the spec, do not ship it silently.

## 3. Feed #1 scope

Sources (v1): Grants.gov (open opportunities) + NIH RePORTER (awarded grants) + OpenAlex (papers / linkage). All free, no key needed for v1.

Scope: public-facing US-federal grant opportunities anyone can see — open RFPs / calls / deadlines. Two-sided: grantseekers and funders, from the same data.

No narrow topic baked into v1. Build broad-but-federal; let usage + a funder conversation pick the domain.

No trials in v1. The three v1 sources include no trials registry. linked_trials[] must be omitted, not returned empty with a promise. ClinicalTrials.gov is a later fourth source, not a v1 promise.

No narrow-subject default. Pediatric cancer was raised and explicitly rejected as the default narrow subject. Do not re-impose it.

## 4. Garden is a demo, not the product

Arden's Grants Garden is one example graphic layer placed on top of the feed. It proves the feed is clean and joined. It is not the product, not a moat, and not a substitute for the feed working.

## 5. Pay — one-time / timed, no subscriptions (for now)

Maxx does not want to manage subscriptions right now. Subscriptions are parked for later, not killed.

Snapshot file: $99 one-time, buy today's full feed as a file, yours to keep.

Remote MCP (first live-agent shape, chosen Nov 12): timed access pass, proposed $99 / 90 days — price/duration still to confirm. Same $99 as the snapshot so the choice is format, not price.

Free tier: garden demo + delayed/sample feed (~7 days old, limited fields, no scores). For MCP: opportunity_search only, 7-day-delayed, no scores/summaries, 20 searches/day proposed.

What the paywall gates: freshness + scores + the other MCP tools. A stale, unscored feed is free; a fresh, scored feed is paid. Raw public data itself is never the thing being sold.

Paid insight (separate, funders): gap reads / landscape reports, consulting-first, $750–$1,750 test range. One-time, not a subscription.

## 6. Guardrails

Verdict (Nov 6, unchanged): funding-intelligence monetization is outside chance only, narrow and consulting-first. Pre-sell before building. One paid pass / snapshot is the validation signal before building subscription/API machinery or a second feed.

Employer IP / conflict check: unverified. Do not claim it is fine. Do not sell until checked.

Dropped directions stay dropped (Nov 6): research-ops, governance/catalog, adherence. Do not re-raise unless Maxx does.

Distinct from day job: the side project must be a little different from research IT / REDCap, not more of the same. Institutional REDCap data belongs to the institution; published research is the world's and can seed it. Do not build on institutional data.

Honesty in every output: scores are one versioned methodology, not an oracle or a funding prediction. Stale data must carry its feed_generated_at — never serve stale data as fresh.

Limits (US federal only, no trials/patents/global in v1) must be stated where a buyer or agent will see them.

## 7. Engineering principles

Feed first, server second. The MCP server is a thin read layer over a working feed. No feed, no server.

Read-only v1. No write tools. No tracking, saving, or submitting.

Four MCP tools only in v1. Every extra tool costs agent context. Add a tool only with a named user story.

Secrets in env vars only. API keys, Gumroad license checks, and database URLs live in environment variables, never in code, config files, or git.

Traceability over cleverness. Every claim carries source ID + URL + timestamp. If a claim cannot be traced, it does not ship.

Test as a buyer. Every feature must be verified from Codex and Claude Code with a real key, not just with a unit test or MCP Inspector.

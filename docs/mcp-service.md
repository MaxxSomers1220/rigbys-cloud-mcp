# Local MCP service

Python 3.12, FastAPI and FastMCP. The MCP identity is `rigbys-cloud`, version
`1.0.0`. The only transport is Streamable HTTP at `/mcp`, with stateless sessions
and JSON responses. There is no legacy SSE endpoint. Exactly four read-only
tools are registered. Phase 3 adds the separate `/redeem`, `/redeem/rotate` and
`/health` HTTP routes; see [the local runbook](runbook.md). Nothing is deployed and
no live Gumroad sale is claimed.

Install with `uv sync --extra test`. Supply `DATABASE_URL` in the process
**environment**, run `uv run rigbys-feed migrate`, then `uv run rigbys-mcp`.
It binds to `127.0.0.1:8000` by default (`PORT` changes the local port).
MCP authorization reads hashed keys from Postgres. The separate redemption page
can issue a key only after configured Gumroad verification; without the live
product configuration it fails closed. Tests generate temporary credentials in memory/environment
and mark synthetic redemption references explicitly as test data, never sales.
Do not put real credentials in commands saved to a file, config, or Git.

## Tools and evidence

- `opportunity_search`: required nonempty topic; sponsor and inclusive ISO-date
  filters; `min_gap_score` 0–100; default limit 10, capped at 25. Topic matching
  uses PostgreSQL English full-text search over title and summary. Sponsor
  shorthand NIH/NSF maps to the source's canonical agency name; other sponsor
  filters are literal case-insensitive substrings. Dates use UTC date-index
  conventions, not a claimed submission hour. Search returns compact source refs,
  coverage, methodology and score-evidence flags. Neutral scores remain unchanged
  in ordinary paid searches. An explicit `min_gap_score` filter considers observed
  `descriptive_proxy` records only; it never qualifies a neutral placeholder.
- `opportunity_get`: returns the persisted unified JSON record exactly, including
  all source refs, coverage, neutral flags, confidence, summaries and change log.
- `opportunity_links`: returns stored award/paper edge fields, confidence and URLs.
  `source_id` is the opportunity for award edges and the stored `via_award` for
  paper edges. No scores or summaries are copied into this response.
- `gap_for_topic`: counts unique source IDs across matching opportunities, not a
  sum of overlapping graphs. Window is 1–120 calendar months, default 12. Award
  fiscal-year and paper calendar-year intervals are included when they overlap
  that window. This is explicitly **year precision**, not exact rolling-date
  research counts. Undated links are counted separately as unknown. Medians use
  observed descriptive proxies only and preserve their original methodology;
  scores are not recalculated for the requested window. Neutral 50 placeholders
  are disclosed and excluded from medians/rankings. Mixed/missing methodologies
  suppress comparisons. Top-five 'subtopics' are explicitly normalized
  opportunity-title groups, not an invented scientific taxonomy. Rankings are
  heuristic portfolio comparisons, never proof of neglect or underfunding.

All reads use a repeatable-read, read-only database transaction. No MCP tool calls
Grants.gov, RePORTER or OpenAlex live. Source/API failures are handled by the feed
builder; the tools preserve the last successful feed timestamp. Counts describe
opportunities open in that recorded feed, not a live source check. Broad FOAs and
long-running award cores do not establish topic relevance or causal funding of
papers by the current call. See the Phase 1 data contract and scoring methodology.

The supplied `spec.md` does not contain a literal §2 server-instructions block.
The initialization instructions in `rigbys_mcp/app.py` are a faithful derivation
of its tool contracts, the constitution and the explicit Phase 1 honesty rules.

## Bearer access and quotas

Every `/mcp` HTTP request requires `Authorization: Bearer <API key>`, including
initialization, listing and other protocol messages. Query-string credentials
are not accepted as authentication. A session header conveys no privileges.
Keys must match their stored tier and their SHA-256 hash; revocation/expiry is
checked on every request, without a credential cache. Paid access expires at the
earlier of stored `expires_at` and the original redemption plus 90 days. Purchase
or key-row creation does not start or reset that clock. Rotation state is verified
through database records updated by the Phase 3 license/email-verified rotation
transaction, which preserves the original expiry and quotas.

Only authorized `tools/call` attempts consume quota, including paid invalid-argument,
unknown-tool or not-found attempts. Initialization/listing and protocol notifications (`notifications/*`) do not.
Unauthorized and free paid-tool refusals consume none. Counters update atomically
per key and UTC calendar day: paid 1,000/day, free 20/day. HTTP 429 includes
`Retry-After` to the next UTC midnight. Invalid/expired/revoked keys return HTTP
401; free attempts on paid tools or the paid score filter return HTTP 403. Errors
are plain JSON without credentials or stack traces. Oversized requests (>64 KiB)
and batch/malformed JSON are rejected. A trailing `/mcp/` is normalized before
charging so redirects cannot count a single call twice.

## Genuine delayed free data

Migration `002` adds sealed, immutable basic-field search snapshots. A successful
feed publication captures a snapshot atomically with its records and success
status; failed transactions leave neither partial feed nor snapshot. Bootstrap
captures the existing feed **now**, never pretends it was historically held.
Both the original feed timestamp and actual database capture time must be at
least seven days old. Inserts into an already committed snapshot are blocked,
as are updates, deletes and truncation. A row-count check detects incomplete
history. The newest eligible whole snapshot is selected; there is no current-row
fallback or backdating.

Free search matches titles only and returns a field whitelist. Scores, methodology,
score evidence, summaries, requirements, description and their nested references
are absent. No hidden paid score/summary participates in free filtering. If no
snapshot has aged seven days, the response is empty with status
`delayed_feed_unavailable` and an explanation. That is the expected initial state
of the real local feed; aged-snapshot behavior is verified using synthetic records
and an advanced test clock. Snapshots continue accumulating on subsequent builds.

## Verification scope

Seeded Postgres fixtures test each tool against known records and hand-computed
aggregations. Actual HTTP and independent MCP SDK tests cover all tools, access
failures, context isolation, exact delay boundaries and concurrent quota races.
MCP Inspector also checks the authenticated server against the real Phase 1 feed.
These are local checks with synthetic credentials, not buyer verification or sale
evidence. Codex/Claude Code production checks remain Phase 5, and hosting remains
Phase 4. There is no claim that the production domain serves this app yet.

# Feature specification: reviewed nationwide AHA opportunities

- Branch: `feature/aha-nationwide-integration`
- Baseline: `bb30f93f1c5b92cc139f8a1ee640ca7451455be2`
- Status: implementation and 475-test native regression complete; live gates blocked; no production activation
- Source of truth: user-authorized nationwide AHA specification and supplied reviewed pilot

This is a narrow additive extension to the historical federal v1 scope. It does not amend `.specify/memory/constitution.md`, create another feed/product, or relax its traceability, five-layer, read-only or secret-handling rules. The current user request authorizes these two reviewed nonfederal programs; historical CPRIT/PR #8 evidence remains unchanged.

## User stories

1. A grantseeker sees two reviewed nationwide U.S.-nonprofit AHA cardiovascular/cerebrovascular calls alongside unchanged federal opportunities, with the real first required deadline and all material eligibility restrictions.
2. An operator can explicitly opt into the reviewed AHA manifest in a disposable rehearsal, and receives a nonzero failure with the whole previous generation retained if any source/prerequisite cannot be freshly verified.
3. A paid MCP reader gets faithful detail/export; a free reader receives only genuinely aged basic fields and safe issuer citations. Neutral AHA scores never masquerade as observed gaps.
4. A maintainer cannot accidentally erase a previously published source by omitting its manifest or rolling back the scheduled builder.

## Functional requirements

- **AHA-001 — Bound scope.** Source-specific `aha.py` and one reviewed manifest cover standard 2027 Career Development and Innovative Project awards only. No plugin registry, discovery service or generic PDF framework. Nationwide geography is an eligible-U.S.-nonprofit/no-state-restriction interpretation; other qualifications and state-limited supplements remain explicit.
- **AHA-002 — Terms.** Career Development: $231,000 total, 36 months, full application December 1, 2026 at 15:00 America/Chicago (21:00Z). Innovative: $200,000 total, 24 months, mandatory pre-proposal December 9, 2026 at 15:00 Central (21:00Z); invited full March 4, 2027 at 15:00 Central. Both totals already include stated 10% indirect costs; floor stays unknown. The later invited stage never reopens new entry.
- **AHA-003 — Date semantics.** Preserve date-index fields and exact first-gate UTC/local/IANA-timezone detail separately. Close at the instant, retain ordered stage/required/invitation flags, do not invent an opening hour, and reject an unknown or contradictory required gate. Test DST independently of the examples' standard-time dates.
- **AHA-004 — Fresh proof.** Ordinary public GET only to reviewed official URLs; bounded size/time/retries and approved redirects. Archive raw bytes before semantics outside Git/resume scan. Verify byte identity, cover/cycle, material terms and prerequisite documents on every enabled run. Changed/missing/403/login/oversized/ambiguous sources fail the complete batch. No cached-source freshness, authentication or challenge bypass.
- **AHA-005 — Activation block.** General application requirements are material. Prior pilot HTML 403 and current environment ProxyError do not establish reliable source access. Without a freshly verifiable reviewed prerequisite the committed manifest refuses activation/publication; do not silently drop the prerequisite.
- **AHA-006 — Identity.** Derived provider/cycle/program IDs and dedupe keys remain stable across edits; new cycles rekey. Validate duplicate IDs/keys. Review explicitly proven cross-provider mirrors, retain the federal canonical record, and never dedupe/join by topic/title/amount/date similarity or coincident federal numbers.
- **AHA-007 — Five-layer fidelity.** Retain field-level issuer URLs, IDs, original retrieval times, raw/envelope/document hashes and section locators. Preserve substantive eligibility and factual summaries. Initialize empty out-of-coverage research evidence separately, then use shared neutral scoring; four 50s with insufficient-data flags are not rankings or funding predictions.
- **AHA-008 — Strict union.** Preserve federal cleaning/joins/minimum 100 and exclusion semantics. Append validated AHA candidates separately, validate the whole union and publish once under the existing lock/transaction. AHA reviewed/admitted/excluded and total counts are distinct. Any enabled-source/publication failure retains last good rows, graph, caches, sealed history, exports and success time.
- **AHA-009 — Default off / omission guard.** `--aha-manifest PATH` or optional `RIGBYS_AHA_MANIFEST` enables the explicit attempt. Neither means no AHA traffic for a fresh federal installation. Persistent prior-source detection refuses accidental omission even after all AHA calls expire.
- **AHA-010 — Consumers.** Keep exactly four MCP tools and auth/rotation/quota/free-delay behavior. Correct provider opportunity counts and safe source health. Add migration 005 only for exact safe AHA free citations; preserve migrations 001–004, field/scalar whitelist and sealed snapshots.
- **AHA-011 — Honesty and release.** Supplied pilot 63 is historical scoped evidence, not the final suite. A real federal-candidate/checksummed-artifact comparison is required before activation; unavailable historical 769 remains blocked. No production DSN, config, deployment or activation change in this task.

## Acceptance and evidence

The final report must identify actual native PostgreSQL/psycopg results for existing plus new tests, synthetic versus real inputs, ordinary source retrieval outcomes, and unresolved gates. Required cases include source failures/change/conflicts, all 50 geographic screens plus a restricted supplement, exact stage boundaries/DST, ID edits/cycles/collisions, federal invariance, repeated full-union publication, every transaction rollback boundary, safe migration/free citations and unchanged HTTP auth/access limits.

Live activation remains separately blocked until source prerequisites, real federal comparison, complete union rehearsal and an authorized release are evidenced. See [design/operations](../../docs/nonfederal-aha.md) and [plan](plan.md).

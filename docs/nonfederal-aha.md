# Reviewed nationwide AHA extension

## Status and boundary

This feature adds an **opt-in, source-specific AHA path**, not a general nonfederal registry, directory crawler, or PDF interpretation framework. Scope is the two reviewed standard 2027 American Heart Association cardiovascular/cerebrovascular research programs below. Nationwide means eligible U.S. nonprofit institutions have no stated state restriction; it is not approval for every institution, investigator, subject, visa status, or partner supplement. State-restricted supplements and CPRIT are outside this default. The [historical CPRIT pilot](evidence/research-sources/cprit-dry-run.md) is retained unchanged; its real-snapshot comparison does not transfer to AHA.

**AHA remains disabled by default. No AHA production configuration, deployment or activation is performed by this change.** The existing federal service is distinct from this prepared extension. The final branch passed 475 automated tests on disposable native PostgreSQL 16.2; [results and limits](evidence/research-sources/aha-implementation/report.md) distinguish those checks from blocked live activation. Older phase test totals are historical.

## Reviewed programs and first entry gates

| Reviewed program | Stated total / term | First required action for new entry |
| --- | --- | --- |
| 2027 Career Development Award | $231,000 total; $77,000/year; 36 months | Full application: December 1, 2026, 15:00 America/Chicago = 21:00 UTC |
| 2027 Innovative Project Award | $200,000 total; $100,000/year; 24 months | Mandatory pre-proposal: December 9, 2026, 15:00 America/Chicago = 21:00 UTC |

Both published totals **already include the stated 10% institutional indirect costs**. Do not add another 10%, multiply the total by the term, or infer a minimum award. The existing amount shape retains `currency=USD`, `floor=null`, `ceiling=the stated total`, `award_amount_basis=total`, and `award_period_months`.

The Innovative award's invited full proposal is due March 4, 2027 at 15:00 America/Chicago (21:00 UTC); invitations are dated January 21. This later invitation-only stage never extends or reopens new entry after the pre-proposal closes. New entry closes **at** the exact first-gate instant. `deadline_parsed` remains a UTC-midnight **date index**, not the actual submission hour. Detail retains `submission_deadline_at`, local timestamp/timezone, `deadline_stage`, and ordered `application_stages` with required/invitation flags. Opening dates do not imply an invented opening hour. IANA timezone rules, including DST, govern conversion.

The manifest must preserve all material qualifications: nonprofit host; degree and employment/career stage; prior-award exclusions; immigration/status conditions; membership and institutional sign-off; and the program-specific mentoring/effort, reviewer participation, preliminary-data and blinding restrictions. The concise table is not an eligibility substitute.

## Source verification, not automatic discovery

`config/sources/aha-reviewed.json` is a versioned review manifest for these programs. `src/rigbys_feed/aha.py` collects an `AhaBatch` of records, scope, references, verification and counts. It does not publish or execute SQL. The reviewed URLs and document-byte hashes are fixed inputs; a changed document at the same filename requires review, not silent acceptance of the newest file. Verify cover/cycle, first gate, geography, totals/units and material conditions as well as SHA-256.

The manifest's `review_binding_sha256` binds its reviewed facts, source bytes and assertion map against accidental edits. It is an integrity check, **not an authentication signature or automated interpretation of eligibility**. Prose conditions remain a human-reviewed boundary. Source-local checks bind each Key Dates label to its date and reject unknown or contradictory gates, including a later invited date substituted for entry. A substantive review revision requires a deliberate new binding and source verification; merely recomputing the binding cannot bypass these source checks. The first adapter requires the complete two-program scope, with each program bound to its official page, PDF and original-byte hash.

Only ordinary unauthenticated public GETs to the reviewed official `professional.heart.org` URLs are allowed. Reject unexpected redirects, login/HTML responses at PDF URLs, oversized/truncated bodies, changed bytes and material contradictions. Retries for transport/429/5xx are bounded; a 403 is a source-access failure, not permission to use credentials, cookies, ProposalCentral, a mirror, or a challenge workaround. Actual downloaded bytes and metadata are archived outside Git before semantic parsing, in nested document storage separate from the existing resume-cache envelope scan.

Every enabled run must freshly verify **all required program and general-application prerequisites**. Federal weekly research reuse or `--resume-raw` must not turn old AHA bytes/timestamps into a new successful verification. Preserve actual retrieval time, document revision/review metadata, raw-envelope checksum/path, original document `content_sha256`, official URL, source ID and field section/page locator separately from `feed_generated_at`. Refetching unchanged content is not a substantive opportunity revision.

The supplied pilot's HTML directory/program/general-resource requests returned **403**, while its two public PDFs returned **200**. The implementation session's ordinary six-request replay was blocked by environment **ProxyError**; it does not re-establish either source status. The general application requirements remain a material prerequisite. Without an accessible reviewed public prerequisite and successful fresh verification, the committed manifest is **activation-blocked and must fail closed**. Manual review and successful PDF-only pilot tests do not waive this gate.

## Identity, union publication and evidence

Stable derived IDs are `aha-2027-career-development-award` and `aha-2027-innovative-project-award`; they are internal identifiers, not issuer solicitation numbers. Dedupe hashes `aha|2027|program-slug`. Edits to title/deadline/revision do not rekey a cycle; a new annual cycle does. Source IDs and citations retain `source=aha` and the cycle/program identity.

Keep federal cleaning, exact research joins and scoring unchanged. AHA is initialized separately with empty award/paper/trial/NSF links, `join_status=outside_current_research_coverage`, explicit research-not-collected coverage, existing neutral 50 scores and `insufficient_data_neutral_placeholder`. Neither absence of AHA research data nor those placeholders establish a research or funding gap. Never join by shared title/topic/amount/date or a coincident solicitation number. A cross-provider mirror requires explicit issuer/solicitation/identity evidence and review; retain the federal canonical record rather than silently replacing it.

The builder validates unique IDs/dedupe keys and the **complete federal + enabled AHA union**, then calls the existing publisher once. Grants.gov's minimum 100 and federal exclusion counts stay federal-only; AHA reviewed/admitted/excluded counts and the union total are separate. An AHA source failure cannot publish a federal-only partial replacement. Source/validation/insert/cache/snapshot/export failures retain the entire last good feed, graph, caches, immutable free history, export generations/bytes and successful timestamp. Failure metadata may record a sanitized stage/type.

A persistent source guard prevents a later invocation without the previously published AHA configuration from silently erasing AHA. It must survive even when all reviewed calls expire. Verified expiry in an enabled complete batch differs from forgetting the source. Do not disable the flag or roll back to an old federal-only builder as a removal mechanism.

## Read contracts and migration

The four read-only MCP tools, Bearer checks, expiry/revocation/rotation, quotas and seven-day free delay remain unchanged. Detail/export retain issuer-specific eligibility, stages and citations; search dates are still indexed dates. Aggregations count opportunity providers accurately and exclude neutral placeholders from observed min-gap filters, medians and rankings. Health reports safe known source statuses/timestamps including AHA when applicable; a fixed three-source success assumption is insufficient. No URLs, raw upstream errors or credentials belong in public health.

Additive migration `005_nonfederal_source_refs.sql` changes only the existing restricted free-citation projection. Preserve migrations 001–004 bytes, projection signature, field whitelist and four citation scalars (`source`, `source_id`, `url`, `fetched_at`). Add only exact reviewed AHA program/PDF paths on the real official host, with the reviewed optional `sc_lang=en` query; reject lookalikes, userinfo, extra query data and fragments. No paid eligibility, stages, scores, summaries, raw hashes/paths or review terms become free fields. Do not rewrite sealed old snapshots or fabricate aged history.

## Local rehearsal and later activation

Only against a disposable non-production database with `DATABASE_URL` supplied privately:

```sh
uv run rigbys-feed migrate
uv run rigbys-feed build --aha-manifest config/sources/aha-reviewed.json
uv run rigbys-feed health
```

`--aha-manifest PATH` is explicit; `RIGBYS_AHA_MANIFEST` is its optional environment default. With neither, fresh installations retain federal-only behavior and make no AHA request. The example AHA build is expected to refuse publication while prerequisites remain blocked. Setting a manifest is not evidence of verification or permission to activate production.

The wheel includes the reviewed manifest and all five migrations. `default_manifest_path()` locates that packaged resource for an explicitly configured deployment; it does not enable AHA. Docker build inputs admit only the exact reviewed JSON, in addition to the existing source/migrations. No runtime setting, source-enablement variable, schedule or deployment is changed by those packaging additions.

Later activation requires fresh source access and open-cycle review, comparison against a real current federal candidate or a retained checksummed federal snapshot, a complete union rehearsal, full native regression results, and an explicit separate production decision. The actual historical 769-record November 23 federal snapshot was not supplied; no AHA zero-duplicate or verified 771-total comparison is claimed. A synthetic sentinel or 100+2 test verifies mechanics only.

Back up the database, raw archive and exports; prepare compatible web, builder and additive migration before enabling. On failure retain the successful generation and pause the job while diagnosing. An old federal-only builder may delete AHA at its next full replacement: pause it or retain a compatible guarded builder. Rolling back only the web service neither reverses data nor rolls back the feed job.

## Verification ledger

| Evidence | Scope / current result |
| --- | --- |
| Supplied pilot | 63 native PostgreSQL tests (50 modeled state cases + 13 checks) at baseline `bb30f93`; focused reviewed data, not an installed adapter or full regression run |
| Supplied supplementary pilot | Earlier 62-case PGlite result; not native transport/concurrency evidence |
| Implementation baseline | Unchanged baseline: 280 passed on disposable native PostgreSQL |
| Final implementation suite | 475 passed, 0 failures/errors/skips (280 existing + 195 new), 130.76s, PostgreSQL 16.2 / psycopg 3.3.9; [machine results](evidence/research-sources/aha-implementation/results.json) |
| Current public-source replay | Six ordinary requests blocked by environment ProxyError; required HTML access unresolved |
| Real retained 769-record comparison | Blocked: artifact unavailable; no fabricated zero-duplicate/771 claim |
| Deployment / AHA activation | Not performed; default remains disabled |

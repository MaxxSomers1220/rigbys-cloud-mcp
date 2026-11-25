# Implementation plan: nationwide AHA extension

Status: branch implementation/native verification pending; production remains disabled. The detailed user contract is captured in [spec.md](spec.md) and [the source/operations contract](../../docs/nonfederal-aha.md).

## Ownership and data flow

1. `config/sources/aha-reviewed.json` declares the two reviewed programs, exact public URLs, original-byte identities, source locators and material terms. It is not a source registry. Keep the original pilot evidence and fixed hashes separate from newly retrieved evidence.
2. `src/rigbys_feed/aha.py`: `collect(manifest_path, raw_dir, now, client=None) -> AhaBatch(records, scope, references, verification, counts)`. Use shared text/amount helpers where appropriate, never the Grants.gov cleaner. No database/publication logic here.
3. `builder.transform(..., additional_records=())` retains federal-only clean/join/trial/NSF paths, initializes AHA research coverage separately, then applies shared scores/summaries/timestamps. `build` preserves positional-call compatibility and adds the optional keyword manifest. CLI resolves explicit flag/environment default without enabling by default.
4. Persistent source guard plus candidate validation prevent accidental prior-AHA omission, collisions, mirrors and partial union publication. Existing lock and one publisher transaction remain authoritative. Failure-stage reporting adds only controlled `source_configuration`, `aha` and `candidate_validation` stages with sanitized exception types.
5. `005_nonfederal_source_refs.sql` replaces only the existing restricted basic-citation projection; prior migration checksums and immutable history stay intact. MCP aggregation/health/instructions learn the narrow AHA scope without new tools or access changes.

## Retrieval and provenance

Use ordinary unauthenticated public GET; bound attempts/time/body size and redirects. Treat 403 as failure; retry only allowed transient categories. Store raw bytes and JSON metadata in nested document storage outside Git and the resume-cache glob. Verify document identity, cycle, fixed SHA and every reviewed material assertion. General application prerequisites are required, not optional because access fails. Enabled runs reverify them freshly even when federal research caches or raw-resume are reused.

Separate source retrieval time, review/revision date, original document hash, archived envelope checksum, and feed transformation time. Stable internal identity is source/cycle/program; unchanged content refetched later must not manufacture a substantive change.

## Preservation and tests

Use a disposable native PostgreSQL database and psycopg; never production credentials. Run the full existing suite plus adapter, pipeline, migration/consumer and failure tests. Tests may use frozen clocks for the historical 2027 examples and explicitly synthetic verified batches to exercise strict union when real source prerequisites remain inaccessible. Neither fixtures nor the pilot 63 replace final integration evidence.

Required publication rehearsal: synthetic 100 federal +2 reviewed-shaped AHA records publishes 102 repeatedly with stable identities; federal minimum 100 is not satisfied by AHA. Compare identical federal input with feature disabled/enabled to prove all federal record/research/score/summary fields are unchanged. Inject failures at AHA collection, record insert, caches, sealed snapshots and export chunks; verify all prior successful artifacts and timestamps remain. Include identity collisions, migration poison URLs, old sealed-snapshot preservation and seven-day free boundaries. Keep auth, expiry, rotation and quota tests unchanged.

## Release gates and rollback

The supplied pilot verified PDF bytes but not reliable general-requirements access. This implementation session's ordinary source attempts are environment ProxyError outcomes, distinct from the pilot's earlier HTML 403. The checked-in manifest must fail closed until a reviewed public prerequisite can actually be verified. A real current federal-candidate or retained checksummed snapshot comparison and a complete full-source rehearsal remain prerequisites; the actual historical 769 artifact is unavailable.

A later separately authorized release needs database/raw/export backups, compatible web and feed-builder versions and additive migration before enablement. Pausing or retaining a compatible guarded feed builder is essential: rolling back to a federal-only publisher can erase AHA, and a web-only rollback does not roll back the data/job. No release/config/activation action occurs in this task.

## Evidence record

- Supplied historical pilot: 63 native tests, 50 modeled state cases + 13 checks; earlier 62 PGlite supplementary run.
- Existing native baseline:280 passed as reported by root.
- Final existing+new implementation suite: **pending actual branch report**.
- Real historical 769 comparison: **blocked; artifact not supplied**.
- Reliable fresh general-prerequisite access: **blocked**.
- AHA production activation/deployment: **not performed**.

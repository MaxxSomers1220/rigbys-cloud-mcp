# Phase 1 feed job

Python 3.12. From the repository root, install with `uv sync --extra test`.
Supply `DATABASE_URL` through the process/host environment; never put credentials
in a tracked file. No MCP, redemption, authentication, or HTTP service is built
in this phase. Railway service deployment remains a later phase.

```sh
uv run rigbys-feed migrate
uv run rigbys-feed build
uv run rigbys-feed health
uv run pytest -q
```

`health` prints the data for the later health endpoint: last successful feed
timestamp, latest attempt status, per-source retrieval status/times, counts, and
feed-only version. It does not start an HTTP server.

## Schedule and storage

`deploy/feed.crontab` wires the installed command at 06:00 UTC every day. On
Railway, configure a separate scheduled job from this repository with cron
`0 6 * * *` and start command `uv run rigbys-feed build`. Supply the database
variable and a persistent raw volume; set `RIGBYS_RAW_DIR` to its mount path.
This configuration is supplied for later hosting setup; it is not activated or
deployed by Phase 1. No user-facing application is deployed.

Every run refreshes Grants.gov. Research refreshes on the first run and once its
oldest response is at least seven days old (also when the fiscal-year window
changes). Complete awards, papers, coverage, and source retrieval times are
cached durably in Postgres. A manual `--force-research` overrides weekly reuse.
ClinicalTrials.gov NIH-identified studies and NSF same-program awards each use
an independent weekly cache. Explicitly cited NCT identifiers absent from the
clinical cache are looked up on the day of the build. NSF refreshes when the
set of supported open opportunities or their program codes changes.
Full builds refuse an empty research source, an incomplete source page set, or
fewer than 100 posted Grants.gov records rather than erasing the last good feed.

Raw archives are content-hashed JSON envelopes, outside Git. Public wrapper
session tokens are removed; all substantive source data and request criteria
remain. Preserve the raw volume alongside database backups so field references
remain inspectable. Data-source fields retain their original retrieval time even
when the feed is transformed again. The Postgres cache is not a raw-volume backup.

After an interrupted large source run, `build --resume-raw` can reuse successful
raw requests from the last 12 hours. It verifies filename hashes, preserves the
original timestamps, and validates source pagination again. Normal scheduled
builds use live daily fetches and the weekly database cache instead.

Publication uses one transaction for opportunities, links, research cache, and
success status. A failed refresh leaves the previous feed/timestamp unchanged,
records failure stage/type, and exits nonzero. A session advisory lock refuses a
concurrent build. No database credentials or arbitrary upstream exceptions are
printed to logs.

## Reading the feed

See `feed-data-contract.md` for date precision, eligibility restrictions, source
coverage, and join meaning; see `scoring-methodology.md` before interpreting any
scores. Records without enough research evidence have explicitly flagged neutral
placeholders and must not be described as observed funding gaps. Publication
linkage does not prove current-opportunity funding or topic relevance.

The existing `linked_opportunities` count measures records with exact award or
paper links. `any_research_linked_opportunities` also includes confirmed trial
and same-program NSF award links. The build reports each relationship's edge
count and opportunity count separately.

Phase 1 checks use an isolated workspace PostgreSQL instance. Railway's private
production database is not accessed by these checks. The generated local feed is
live public-source data, not test fixtures. `docs/evidence/` records inspection
samples and task checks. SC-002 here verifies stored source deadlines/links; client
prompt checks remain in their later phases.

## Reviewed AHA extension: disabled until separate activation

The source-specific adapter uses `config/sources/aha-reviewed.json`. The optional `--aha-manifest PATH` flag overrides its environment default `RIGBYS_AHA_MANIFEST`; with neither, a fresh federal-only installation makes no AHA request. Only use an explicit AHA rehearsal against a disposable non-production database. See [source/release gates](nonfederal-aha.md).

Every enabled run freshly verifies the reviewed PDF and required general/application prerequisites, even if federal weekly caches or `--resume-raw` are reused. No old document/manual-review timestamp becomes a new verification. The pilot's HTML 403 and the current environment's ProxyError are unresolved source-access observations, not empty successful collections; the committed manifest fails closed until required prerequisites can actually be reviewed and retrieved.

Federal minimum 100 and exclusions remain federal-only. Validate and publish the entire union once under the existing lock/transaction. Source/candidate/publication failure must leave old rows, graph, cache, free snapshots, both export slots/bytes and successful timestamp unchanged; only sanitized failure metadata changes. A persistent source guard refuses omission of previously published AHA even after expiry. Do not remove the manifest to force a federal-only publication.

Before any later enablement, back up raw/database/export state, install compatible web/builder/migration 005, verify actual current sources/open cycle, perform a real federal comparison and full union rehearsal, and obtain the separate release decision. Pausing the job or retaining a compatible guarded builder is required for safe rollback; an old federal-only publisher can erase AHA. No Railway variables, schedules or activation are changed by this implementation task.

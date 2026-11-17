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

Phase 1 checks use an isolated workspace PostgreSQL instance. Railway's private
production database is not accessed by these checks. The generated local feed is
live public-source data, not test fixtures. `docs/evidence/` records inspection
samples and task checks. SC-002 here verifies stored source deadlines/links; client
prompt checks remain in their later phases.

# AHA implementation verification

Baseline: `bb30f93f1c5b92cc139f8a1ee640ca7451455be2`. Branch: `feature/aha-nationwide-integration`. Implementation/test scope was the November 24 nationwide specification; the final suite ran November 25, 2026. No production database, source-enablement setting, authorization rule or deployment was changed.

## Actual results

| Check | Result |
| --- | --- |
| Unchanged baseline | 280 passed, no failures/skips, disposable native PostgreSQL |
| Final complete repository suite | **475 passed, 0 failures/errors/skips, 130.76s**; four dependency deprecation warnings |
| Source adapter | 106 deterministic cases, including 50 modeled state screens, exact entry gates/DST, bounded transport/status/MIME/length/hash/identity failures and source-bound date roles |
| Consumer/citation extension | 48 cases: upgrade001–004→005, immutable snapshots, safe/poison URLs/scalars, provider counts and sanitized health |
| Union/rollback extension | 35 cases: unchanged federal output, 100+2 twice, research isolation, cache cadence, source omission/expiry, distinct next-day refetches, duplicate/mirror checks and five fault stages |
| Persisted reads | AHA detail/export retain eligibility and stages; neutral scores excluded by observed min-gap/ranking filters; truly aged free title search exposes only basic fields and safe citations |
| Summary/CLI extension | Five cases: exact mandatory versus invited action, inclusive total/term citations, unchanged federal summary, environment default and explicit override |
| Wheel | Built from the exact Docker COPY inputs, installed in a separate environment; imports/resources resolve from site-packages; all five packaged migrations applied twice to a new native database |
| Local container | Built and inspected in a disposable `--network=none` container; packaged resources match, two reviewed programs, five migrations, AHA disabled by default |

Python 3.12.14, PostgreSQL 16.2, psycopg 3.3.9 and pgserver 0.1.4 powered the full suite. The local container used Python 3.12.16. These are native PostgreSQL tests, not an embedded-database substitute. [JUnit results](native-results.xml) retain the actual cases/counts; only the local machine hostname was removed. [Machine summary](results.json) includes input and package checksums and counts per module.

The full run used the existing per-test disposable database/HTTP fixtures with production-facing environment variables removed. Equivalent installed-dependency command: `python -m pytest -q --tb=short`. No real paid key or live licensing transaction was used.

## Evidence boundaries

The input ZIP SHA-256 is `ff38f122787f165519b1cfa4dc76220311756d1e3a4777fd36c2ce20fa01a306`. All 18 listed bundle files and all 13 pinned baseline source identities matched. The supplied pilot's 63 native cases remain historical reviewed-data evidence, separate from this implementation's 475 cases.

The adapter tests author their own small PDF/HTML fixtures. They test fresh-byte verification and extraction against reviewed facts; they do **not** establish successful retrieval or semantic replay of the original AHA PDFs from this host. The 100+2 records are synthetic pipeline fixtures, not a real 102-record federal collection. The review digest binds operator-reviewed prose/material facts; it is not an authentication signature or autonomous eligibility interpretation.

The implementation's ordinary unauthenticated GET replay of the directory, both program pages, general application resources and both RFPs encountered **ProxyError for all six**. No access restriction was bypassed, and no fresh endpoint status or original-byte hash was established. The pilot's earlier HTML403/PDF200 observations are distinct. The committed prerequisite remains explicitly unverified, so an enabled attempt fails closed rather than publishing an incomplete or falsely fresh subset.

The normal local Docker build encountered the managed session's proxy CA trust restriction during package installation. The successful validation build used a temporary Dockerfile with the host CA mounted as a BuildKit secret for pip/uv, keeping TLS verification enabled. This validation-only adjustment and CA were not committed or baked into the runtime image. No image was pushed or deployed. All original locked dependencies remain identical; only `pypdf==6.21.4` was added. Build-input changes admit only the exact reviewed JSON; runtime settings and schedules remain untouched.

## Corrections verified during review

- Bind general requirements to their own reviewed official source; a program PDF cannot substitute for that prerequisite.
- Require the complete reviewed two-program/document scope and matching program/PDF/canonical identity.
- Bind each first-page Key Dates label to its reviewed date. An award-start date, invited deadline, unknown label or contradictory duplicate cannot become an entry gate, even after recomputing a review digest.
- Recheck exact admission at final transformation in case verification spans the closing instant.
- Keep unchanged AHA refetches semantically stable, including the shared scorer's daily observation date; retain that date in published evidence and preserve federal comparison behavior.
- Include the manifest in the wheel and Docker build inputs.

Existing regression synchronization changed only synthetic opportunity IDs to the federal namespace, expected migration counts/list for additive005, and the SQL mock for the new omission check. Authentication, quotas, seven-day delay and other behavioral assertions were preserved. Migrations001–004 and historical CPRIT evidence remain byte-identical.

## Still blocked before activation

1. Fresh public program/general prerequisite verification from the intended job host, including semantic replay of the actual original source documents. Accessible authoritative general rules must be reviewed and pinned; manual-only evidence is insufficient.
2. Comparison with an actual current federal candidate or a retained checksummed artifact. The historical 769-opportunity snapshot was not supplied; there is no zero-duplicate or verified771-record claim.
3. Two complete real-source union builds using a disposable staging native database, followed by a separate release decision with backups and a compatible rollback guard.

The full live federal build, multi-source staging activation and Codex/Claude buyer checks with real keys were not performed. AHA remains disabled by default and activation-blocked. A web rollback does not reverse database content or the independent feed job; an old federal-only replacement builder can delete AHA rows, so pause the job or retain a compatible guard during rollback.

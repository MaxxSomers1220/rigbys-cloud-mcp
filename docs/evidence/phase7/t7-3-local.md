# Phase 7 local snapshot export verification

Verified on November 20, 2026 with Python 3.12, isolated PostgreSQL, and the actual FastAPI and MCP app. The controlled fixture has 786 generated opportunities. Its date and count exercise the export contract independently of the live feed.

| Check | Result | Evidence |
| --- | --- | --- |
| Export completeness and canonical fields | Passed locally | The downloaded gzip contained 786 distinct IDs. Every decoded object equaled its stored `opportunities.record` object, including deadlines, scores, summaries, linked awards and papers, confidence and source URLs. The envelope and header generation were `2026-11-17T05:00:00+00:00` in the fixture. The file spanned multiple chunks. |
| Ten MCP comparisons | Passed locally | The full `opportunity_get` responses matched the exported objects for `fixture-0001`, `fixture-0007`, `fixture-0012`, `fixture-0084`, `fixture-0171`, `fixture-0272`, `fixture-0416`, `fixture-0549`, `fixture-0702`, and `fixture-0786`. |
| HTTP attachment and access | Passed locally | Paid access returned 200 and one gzip attachment named `rigbys-cloud-feed.json.gz`. Response metadata matched the decoded file and downloaded byte length. Free access returned the existing paid-required 403. Missing, malformed, unknown, revoked and expired keys returned 401. A valid key supplied only as a query parameter returned 401. |
| Shared quota and tool inventory | Passed locally | One export and one `opportunity_get` advanced the same counter from 998 to 1,000. The next export returned 429 with `Retry-After`. The MCP SDK test listed and called the original four tools. |
| Rotation and failure retention | Passed locally | Three sequential publishes with fixture counts 9, 8, and 9 advanced the generation and record count. The previous slot was byte-identical to the preceding download. After the third build only run 2 and run 3 had artifact chunks. A failed publish, an injected export write failure after a partial chunk, and an aborted outer transaction preserved the committed export and backup. |
| Download during rotation | Passed locally | A download started on run 1, read a chunk, then streamed its remaining bytes unchanged after two successful publishes removed run 1 from the retained slots. |
| Missing or stale export | Passed locally | Paid access returned a plain 503 before a build created an artifact and when an old-builder-style success superseded the artifact. |
| Production verification | Pending | T7.4 requires the Phase 7 web service, upgraded feed builder, a successful real run and production verification credentials. The live count is established by that build. |

Commands run from the repository with the project test environment:

```sh
python -m pytest -q
python -m pytest -q tests/test_snapshot_export.py
```

The full regression run passed 269 tests. The final focused run passed seven Phase 7 integration tests, including the added quota check and changed-count rollover. Existing dependency deprecations and the local runtime directory warning were reported.

[Test source](../../../tests/test_snapshot_export.py) · [Download and deployment instructions](../../runbook.md#5-download-the-full-feed-snapshot)

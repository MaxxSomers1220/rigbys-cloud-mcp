# Workstream 1 linkage verification

This replay used the 769 opportunities from the Nov 21, 2026 export generated at
06:00:54 UTC. It froze the opportunity population and existing award and paper
joins, then fetched public registry and NSF data on Nov 21. The unit of the
coverage measures is a distinct published opportunity ID.

| Comparison | Linked opportunities | Share |
|---|---:|---:|
| Nov 19 reported award or paper baseline, approximate | 165 of 786 | 20.99% |
| Nov 21 exact award or paper baseline | 156 of 769 | 20.29% |
| Nov 21 replay with trial and same-program evidence | 167 of 769 | 21.72% |

The replay adds 11 opportunities to combined coverage, a gain of 1.43 percentage
points over the Nov 21 snapshot. The exact award-or-paper measure remains 156
of 769. The Nov 19 comparison uses a different record population and the
narrower historical measure.

## Sources and spot checks

- **NSF Award Search** added 1,109 links to 1,108 distinct awards across 11 of
  the snapshot's 116 NSF opportunities. Each link has an active NSF award ID
  and a program element code published under “Awards made through this program”
  on the NSF program page tied to the solicitation. All 11 newly linked
  opportunities passed the spot check. For each, the check retrieved the
  Grants.gov source and followed its NSF solicitation URL, checked the official
  program award search, opened the sample award page, and queried the individual
  NSF award record by ID to confirm the code. The relationship is same-program
  evidence. The NSF FAQ and public data listings identify the award provenance
  and scope. [NIH RePORTER coverage](https://report.nih.gov/faqs) ·
  [NSF Award Search](https://www.nsf.gov/funding/award-search)
- **ClinicalTrials.gov** evaluated 31,069 studies with NIH-typed secondary
  identifiers. The exact NIH core match added 1,131 trial links across 39
  already-linked opportunities and 1,118 distinct trials. Five independently
  fetched trial records matched the stored RePORTER core and opportunity
  evidence. The dated feed had no direct NCT references in opportunity titles
  or synopses. That join path is covered by tests.
  [ClinicalTrials.gov identifier definitions](https://clinicaltrials.gov/policy/protocol-definitions)
- **Score evidence** reconciled the per-link input tags with the recorded
  year and total counts for all 769 records. All four score values matched the
  original export for every record. The audit counted 33 descriptive records
  and 736 explicitly flagged neutral placeholders.

The NSF scope uses 11 explicitly reviewed program mappings. The code 541400
appeared inconsistently in the official Oceanographic Facilities and Equipment
Support program link and was excluded. The revised scope reproduced the
same 82 verified awards for that program.

The record-level results, per-program counts, and source URLs are in
[nov21-replay.json](nov21-replay.json). The reproducible public-data checks
are in [verify.py](verify.py).

```sh
uv run python docs/evidence/workstream1-linkage/verify.py \
  /path/to/rigbys-cloud-feed.json.gz /path/to/local/raw-archive \
  /path/to/nov21-replay.json
```

## Service verification

The full suite passed 276 tests. The final targeted suite passed 20 tests
after the NSF scope adjustment and the addition of the NSF persistence check.
The SDK integration test reported four tools. PostgreSQL integration covered
weekly cache reuse, retention of the last successful publication after a
source refresh failure, and publication of the new detail fields.

The read-only production health check returned HTTP 200 and the original
Nov 21 generation with the three previous source statuses. The new counts
above are replay results. Production publication and verification remain open.
[Production health](https://mcp.rigbyscloud.com/health)

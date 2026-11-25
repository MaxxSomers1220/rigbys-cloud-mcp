# Feed data contract

The feed uses public Grants.gov opportunities, NIH RePORTER awards and
publications, OpenAlex works, and ClinicalTrials.gov study records. NSF Award
Search supplements award coverage where NSF publishes an explicit program
crosswalk.

## Cleaning and openness

Grants.gov `posted` is a source status, not proof that the deadline is current.
The builder excludes elapsed dates and future posting dates. If a structured
closing date is absent, explicit dates in the deadline description are parsed;
an expired description or unresolved multiple/attachment-only dates is excluded.
An explicitly rolling call can have a null deadline. The source description is
retained, including constraints on individual rounds. Excluded records remain in
raw archives for review; the builder reports input and published counts.

`deadline_parsed` has **date precision**. UTC midnight is an indexing convention,
not a claim about the submission hour. Check the original announcement for the
hour, local timezone, letters of intent, and recurring application rounds.
Explicitly rolling descriptions override sentinel-like far-future closing dates;
the original date remains in `source_deadline_date`. Other far-future dates are
preserved with a quality flag, rather than silently corrected.

Title and sponsor whitespace/entities/HTML are normalized. Structured agency
metadata supplies the sponsor, since a synopsis agency-name field sometimes
contains a person's name. Eligibility includes both categories and the entire
additional qualifications/restrictions text. Contradictory source boilerplate
is retained with a restrictions warning; categories alone do not establish an
applicant's eligibility. Award floor and ceiling are source-stated USD bounds.
Unknown `none` becomes null; literal zero is preserved and is not an estimate.

Stable IDs use Grants.gov IDs. The dedupe key hashes agency code and opportunity
number. Field references include the source field, ID, source page URL, retrieval
time, raw-envelope path, and SHA-256 hash. Raw public data is stored outside Git;
credential-like session fields in public API wrappers are omitted.

## Coverage and joining

Research coverage is declared with each build. The default is the current US
federal fiscal year and three previous fiscal years. NIH linkage uses exact NIH
opportunity numbers, not sponsor or title similarity. NIH coverage naturally does
not cover every federal agency. A record with no confirmed link states that fact;
it is not evidence of no funding or no research. The full refresh uses OpenAlex works whose funding metadata explicitly names an
award core project number. This avoids RePORTER publication pagination caps for
large projects. The optional publication-PMID path is also supported and was
live-checked. Core projects span renewal cycles; neither path proves a paper was
funded by the current opportunity or is specifically about its topic. Unmatched
records and missing source coverage are reported explicitly.

### Study registry and NSF program evidence

- `linked_trials` identifies ClinicalTrials.gov studies by NCT number. The
  opportunity can cite that exact NCT identifier in its title or synopsis. It
  can also be linked through an existing RePORTER award when the registry
  lists the same NIH core project in an NIH-typed secondary identifier. The
  entry gives the original registry identifier, study page, registry source
  reference, and matching award where applicable.
- `linked_nsf_program_awards` lists active awards that report an element code
  published in “Awards made through this program” on the official NSF program
  page. The opportunity number must be in the verified NSF crosswalk. The
  entry gives the official solicitation, program, award page, reported code,
  and source reference. This evidence establishes a shared program.
  Historical awards may have been issued through an earlier solicitation.
- Each entry carries its relationship and join confidence. Trial and NSF
  program links provide context. They are separate from the exact award and
  paper lists used for the published scores and graph.

In record detail, `score_evidence_detail` explains each score's input fields
and which link arrays contain the evidence. Each linked award and paper tags
its contributing inputs in `score_inputs`, alongside its source URL and
join confidence. The published counts and years remain in `score_evidence`.

## Storage

Full public source envelopes remain in the raw archive. The durable research cache
projects only fields consumed by this feed and retains raw references for the
complete responses. Large caches are stored in bounded chunks with a manifest
and checksums. `opportunities.record` retains the unified record and its
`linked_awards`, `linked_papers`, `linked_trials`, and
`linked_nsf_program_awards` evidence. The temporary exact award and paper graph
projection is stored once in `opportunity_links`.
Field-level join references point to each linked entry's evidence references.

## Opt-in reviewed AHA opportunities

The nationwide nonfederal extension is limited to two named 2027 AHA cardiovascular/cerebrovascular programs, not every AHA listing or a general registry. See [the complete contract](nonfederal-aha.md) for source verification, material restrictions and activation blocks. Default feed behavior remains federal-only unless the explicit manifest is configured; this task does not activate it in production.

`eligibility_geography` records the eligible-U.S.-nonprofit/no-state-restriction interpretation without promising individual eligibility. Stable derived AHA IDs/dedupe use provider/cycle/program, not a Grants.gov number or mutable title/date. Field citations retain official URLs, source IDs, actual retrieval times, raw-envelope/document hashes and section locators. Shared text/amount helpers do not make an AHA record a Grants.gov record.

AHA date indexes retain `deadline_precision=date`; exact `submission_deadline_at`, local timestamp/timezone, `deadline_stage` and `application_stages` control first-entry closure. The December 9 mandatory pre-proposal closes new entry even though an invited full proposal is due March 4. Published totals 231000/200000 already include stated 10% indirect costs, are not annual amounts, and retain an unknown floor; terms are 36/24 months.

AHA research arrays are empty with explicit outside-current-coverage status and neutral 50 placeholders. Missing AHA awards/papers is not a gap finding, and shared titles or number collisions do not establish research links. Counts distinguish federal input/exclusions, AHA reviewed/admitted/excluded and union publication. Every enabled source must verify before a single complete publication; failed verification or omitted prior configuration retains the whole last-good generation.

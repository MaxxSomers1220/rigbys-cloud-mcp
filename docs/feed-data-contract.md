# Feed data contract (Phase 1)

Only public Grants.gov opportunities, NIH RePORTER awards/publications, and
OpenAlex works are used. No institutional data or trial registry is accessed.

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

## Storage

Full public source envelopes remain in the raw archive. The durable research cache
projects only fields consumed by this feed and retains raw references for the
complete responses. Large caches are stored in bounded chunks with a manifest
and checksums. `opportunities.record` retains the unified record and its
`linked_awards`/`linked_papers` evidence. The temporary builder `links` projection
is stored once in `opportunity_links`, rather than duplicated in the JSON record.
Field-level join references point to each linked entry's evidence references.

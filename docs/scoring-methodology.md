# Research signals 1.0.0

These deterministic 0–100 **descriptive proxies** summarize the retrieved research
portfolio associated with an exact NIH opportunity number. They do not predict
funding success, measure scientific merit, or establish underfunding. Broad parent
opportunities describe broad portfolios; these are not topic-specific gap reads.
Sources, join confidence, coverage, and input counts accompany each record.

Only **complete** years are compared. For a build in November 2026, publication
years are 2025 vs 2024 and federal fiscal years are 2026 vs 2025. Research retrieval
covers current FY and previous three FYs; publication histories are OpenAlex works explicitly naming those awards' core
project numbers in funding metadata (or the optional RePORTER publication-PMID
intersection), potentially dating from earlier renewal cycles. OpenAlex coverage is incomplete and citation lag is
not adjusted. No title similarity or inferred causal paper attribution is used.

Let P be unique linked works, A unique linked fiscal-year project numbers, p1/p0
the complete calendar-year paper counts and a1/a0 complete fiscal-year award
counts. Scores round to the nearest integer after clamping to [0,100]:

- **Growth:** `100 * max(0, p1-p0) / max(1,p0)`, capped at 100. Nonpositive change
  is zero; this score does not distinguish flat from declining output.
- **Momentum:** the same positive-change formula for a1/a0. This counts awards,
  not dollars. An unchanged, heavily funded portfolio has zero momentum.
- **Novelty:** `100 * (1 - min(1, log(1+P)/log(1001)))`. This is inverse publication
  saturation, not a claim that the opportunity or its ideas are scientifically new.
- **Gap:** `100 * P / max(1, P+5*A)`. This is publication-to-award imbalance. The
  multiplier 5 is an explicit heuristic scaling constant, not empirically fitted
  evidence of funding need. High values must not be sold as proven underfunding.

With fewer than **5 awards OR 10 papers**, all four values are neutral **50** and
`score_evidence.status` is `insufficient_data_neutral_placeholder`. This includes
non-NIH opportunities outside research-source coverage. A neutral placeholder
must not be ranked or described as an observed score; counts and status must be
shown alongside it. This preserves a numeric field without inventing evidence.

Every record has `methodology_version=research-signals-1.0.0`, input counts,
comparison periods, per-field methodology references, and source-backed edges.
Identical records and as-of dates produce identical scores. These are early,
unvalidated portfolio signals; calibration and domain comparisons need separate
validation. Formula or threshold changes require a new methodology version.

# CPRIT research opportunity dry run

Checked November 24, 2026. The pilot admits direct scientific research awards
that an eligible institution can still start applying for. The Texas funder’s
public directory showed 14 open listings, 11 under Academic Research. Two
qualified for this pilot. [Source directory](https://www.cprit.texas.gov/funding-opportunities)

| Opportunity | Research and eligibility | Close and award ceiling | Official sources |
| --- | --- | --- | --- |
| Catalyst Pilot Research Award, `R-27.2-CPRA` | Pilot cancer research. Eligible Texas entities include research nonprofits and eligible companies. The PI needs a doctorate, qualifying appointment, Texas residency during the research, and at least 5% effort. | Dec. 8, 2026 at 5 p.m. Central (23:00 UTC). Up to $250,000 total over two years. | [Live call](https://grants.cprit.texas.gov/Grants/FundingOpportunity/119Wj000004auHXIAY) · [Nov. 12 revised RFA, §§6–7 and 9.1](https://grants.cprit.texas.gov/Grants/sfc/servlet.shepherd/document/download/069Wj00001jNh58IAC?operationContext=S1) |
| Clinical Investigator Award, `R-27.2-CIA` | Patient-oriented cancer research with protected time for an eligible mid-career MD or DO. The Texas applicant must provide cancer care and training and conduct clinical cancer research. An institutional nomination, qualifying appointment, current clinical research support, and Texas residency during the appointment apply. | Dec. 8, 2026 at 5 p.m. Central (23:00 UTC). Up to $1.5 million total over five years. | [Live call](https://grants.cprit.texas.gov/Grants/FundingOpportunity/119Wj000004auHWIAY) · [Nov. 12 revised RFA, §§7–8 and 11.1](https://grants.cprit.texas.gov/Grants/sfc/servlet.shepherd/document/download/069Wj00001jOsw6IAC?operationContext=S1) |

The live application pages and both revised RFAs agree on the December 8
submission deadline. The revision logs explicitly update that deadline,
superseding the November 18 date in older copies. Both revised RFAs give the
closing hour. Award notification is omitted from the preview because the
public listing gives May 2027 and the revised RFAs give August 2027.

The other 12 entries were excluded from this pilot.

| Reason | Count | Entries |
| --- | ---: | --- |
| Required letter of intent already closed | 2 | Texas Regional Excellence in Cancer Award and Texas Regional Training Award. The first supports direct research, but both had a September 4 LOI gate. |
| Recruitment or retention | 4 | Clinical Trialists, Established Investigators, First-Time Tenure-Track Faculty Members, and Rising Stars. |
| Shared infrastructure | 2 | Clinical Trials Network and Core Facility Support. |
| Institutional training | 1 | Research Training Award for Workforce Development. |
| Prevention service delivery or implementation | 3 | Dissemination of CPRIT-Funded Cancer Control Interventions, Cancer Screening and Early Detection, and Primary Prevention of Cancer. |

## Data checks

- Compared normalized titles, RFA numbers, portal IDs, source URLs, and
  funder against the 769-record federal snapshot generated November 23 at
  `06:04:01.855076 UTC`. There were zero exact duplicates. The closest
  federal title matches had different sponsors and solicitation numbers.
- Published the two verified records twice to a disposable local PostgreSQL
  database using the existing schema. Both runs stored exactly two records.
  Search found both. Detail preserved the eligibility, award ceilings, source
  URLs, and recorded closing time. The date index follows the existing UTC-date
  convention, and detail retains the original Central timestamp.
- The source is traceable by portal ID and RFA number. SHA-256 for the revised
  Catalyst RFA is
  `a261acfdf8a015e2c707af61ac084aa41f49dedbeed32f50498ee7d18eeab69f`
  and for the revised Clinical Investigator RFA is
  `f8e3aad00eb80e978b76dbc3caea3a01aa0aecb5812a8e2f32557ce3dad2e309`.

The preview uses factual summaries, field-level citations, and full links to
the issuer. Award and paper joins were outside this dry run, so the existing
scoring methodology marks both records neutral. [CPRIT site and link policy](https://www.cprit.texas.gov/about-us/site-policies/)

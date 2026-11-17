# Final published-feed source checks — 2026-11-17

SC-002 feed-data spot-check: **10/10 correct** deadlines and Grants.gov links in actual Postgres records. All ten public source-page links returned HTTP200. Fresh source IDs and decoded titles also matched, including the repaired NCSES title gg-355219.

| Opportunity | Deadline in Postgres and fresh source | Link |
| --- | --- | --- |
| [24-587](https://www.grants.gov/search-results-detail/355219) | 2027-01-19 | HTTP200, ID verified |
| [W911QY25R0023](https://www.grants.gov/search-results-detail/360012) | 2030-02-27 | HTTP200, ID verified |
| [DOW2027APEXACCELERATORCLOSED](https://www.grants.gov/search-results-detail/364213) | 2027-07-04 | HTTP200, ID verified |
| [AFPMB-BAA-27-01](https://www.grants.gov/search-results-detail/363946) | 2027-03-17 | HTTP200, ID verified |
| [HHS-2026-ACF-ECD-TP-0039](https://www.grants.gov/search-results-detail/363047) | 2026-11-20 | HTTP200, ID verified |
| [HHS-2026-ACF-ORR-ZU-0019](https://www.grants.gov/search-results-detail/361822) | 2027-10-01 | HTTP200, ID verified |
| [DE-FOA-0003467](https://www.grants.gov/search-results-detail/356623) | 2029-09-29 | HTTP200, ID verified |
| [USDA-AMS-TM-SCMP-G-26-0020](https://www.grants.gov/search-results-detail/361876) | 2026-12-04 | HTTP200, ID verified |
| [FA2391-23-S-2403](https://www.grants.gov/search-results-detail/349554) | 2043-05-10 | HTTP200, ID verified |
| [NOFOAFRLAFOSR20260004](https://www.grants.gov/search-results-detail/363526) | 2027-04-05 | HTTP200, ID verified |

The same ten published summaries were inspected: no invented deadlines or award amounts. Twenty direct paper edges sampled from twenty distinct published opportunities matched RePORTER FOA/award core identifiers and OpenAlex funding metadata. A core association does not establish that the current FOA caused or funded a paper.

This is Phase1 feed-data verification in isolated workspace PostgreSQL. No Railway production deployment, MCP client verification, or independent human sign-off is claimed. Detailed evidence is in `sc-002.json`, `t1-4-published-direct.json`, and `t1-6-published.json`.

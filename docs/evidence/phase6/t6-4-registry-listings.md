# T6.4 — MCP registry submissions

Checked November 19, 2026. The owner authorized T6.4 after counting the real
$1 self-purchase toward T6.3.

- Live Streamable HTTP endpoint. `https://mcp.rigbyscloud.com/mcp` returned
  HTTP 401 without a key, with Bearer authentication.
- Public [GitHub README](https://github.com/MaxxSomers1220/rigbys-cloud-mcp/blob/main/README.md)
  returned HTTP 200.
- The live access page confirms a one-time pass from $1 USD and 90 days from
  redemption. The free tier is `opportunity_search` only, seven days delayed,
  with no scores or summaries and up to 20 searches per day.
- The four read-only tools are `opportunity_search`, `opportunity_get`,
  `opportunity_links`, and `gap_for_topic`.

## Registry status

| Directory | Submission status | Verified live listing |
| --- | --- | --- |
| Official MCP Registry | Published and verified as active using version 1.0.0. | [Public registry entry](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.MaxxSomers1220%2Frigbys-cloud/versions/1.0.0) |
| Glama | Eligible for hourly import from the official registry. The expected connector URL returned HTTP 404 on the immediate post-publication check. | Pending |
| Smithery | Publisher accounts, API keys, API, and CLI ended October 31, 2026. The legacy submission page returned HTTP 404. The remaining site is a curated directory, and its public documentation exposed no submission path. | None verified |
| PulseMCP | New servers and changes are paused. The directory directs publishers to the Official MCP Registry and says it will resume automatic intake when the pause ends. | None verified |

## Official MCP Registry

Publisher `mcp-publisher` v1.8.9 validated `server.json` against the production
registry. After the owner approved GitHub device authorization, the publisher
published `io.github.MaxxSomers1220/rigbys-cloud` version `1.0.0` on November
19, 2026 at 12:55:26 p.m. EST. Both the exact-version and latest URLs returned
the expected active entry. The response contained the remote URL, GitHub
README, required secret Bearer header, the four tool names, and the exact paid
and free access terms. The README returned HTTP 200 and the MCP endpoint
returned HTTP 401 with a Bearer challenge when opened without credentials.
[Committed manifest](https://github.com/MaxxSomers1220/rigbys-cloud-mcp/blob/0cfed4f665bb507b0c877a7eec9c04b1ee772f2b/server.json) · [Latest version](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.MaxxSomers1220%2Frigbys-cloud/versions/latest)

## Glama

Glama documents hourly import of hosted connectors from the official registry.
Its manual hosted submission uses a name, description, and endpoint, followed
by review and an ownership claim. If the imported page omits the full terms or
README, the owner must sign in with the matching GitHub account, claim the
connector, and edit the listing. [Glama submission and claim FAQ](https://glama.ai/mcp/faq#how-do-i-submit-an-mcp-connector)

## Smithery and PulseMCP

Smithery would need to restore a supported publisher submission process.
PulseMCP would need to resume intake and import the official registry entry.
[Smithery transition notice](https://www.smithery.ai/future) · [PulseMCP submission status](https://www.pulsemcp.com/submit)

T6.4 requires all four listings to be live and verified. It remains open.

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
| Official MCP Registry | The supported publisher validated `server.json`. GitHub owner device authorization is pending. | Pending |
| Glama | The hosted connector is eligible for hourly import after Official MCP Registry publication. The expected connector URL returned HTTP 404 before publication. | Pending |
| Smithery | Publisher accounts, API keys, API, and CLI ended October 31, 2026. The legacy submission page returned HTTP 404. The remaining site is a curated directory, and its public documentation exposed no submission path. | None verified |
| PulseMCP | New servers and changes are paused. The directory directs publishers to the Official MCP Registry and says it will resume automatic intake when the pause ends. | None verified |

## Official MCP Registry

Publisher `mcp-publisher` v1.8.9 passed `validate server.json` against the
production registry. The committed manifest is `0cfed4f` and publishes under
`io.github.MaxxSomers1220/rigbys-cloud` with version `1.0.0`. The live
manifest should expose the remote URL, GitHub README, a required secret
Bearer header, and the access terms and tool names in publisher metadata.
Exact-name lookup returned HTTP 404 and search returned zero matches before
submission. [Committed manifest](https://github.com/MaxxSomers1220/rigbys-cloud-mcp/blob/0cfed4f665bb507b0c877a7eec9c04b1ee772f2b/server.json) · [Official remote-server guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/remote-servers.mdx)

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

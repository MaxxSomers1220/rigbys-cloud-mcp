# T2.1 — local MCP Inspector check

Passed with actual `@modelcontextprotocol/inspector@2.15.0` CLI against
`http://127.0.0.1:8802/mcp` over Streamable HTTP. `initialize` returned
`rigbys-cloud`, version `1.0.0`, protocol `2025-11-25`, and the derived
source/honesty instructions. `tools/list` returned exactly four read-only tools:

- `opportunity_search`
- `opportunity_get`
- `opportunity_links`
- `gap_for_topic`

This checkpoint verifies scaffold connectivity and contracts. The four handlers
are stubs until T2.2–T2.5, and auth is T2.6; no later-phase work is claimed.
The supplied spec has no literal §2 instruction block, so server instructions
faithfully derive from its contracts, constitution, and Phase 1 honesty rules.
Full input schemas and raw Inspector result fields are in the adjacent JSON.

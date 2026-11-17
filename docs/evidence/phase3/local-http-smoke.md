# Phase 3 local HTTP smoke

Passed against actual loopback HTTP routes and the real local 789-record Phase 1
Postgres feed. Gumroad license verification used an injected `httpx.MockTransport`
with a synthetic ordinary-purchase receipt; zero requests reached Gumroad. This
is not a paid sale, real buyer verification, production configuration or deployment.

- Valid form redemption issued one key with both client commands and no-store.
- The key appeared once; refresh did not redisplay it. Invalid/replayed licenses
  returned plain errors without additional keys.
- Database storage contained hashes, never raw license/API keys. Expiry was exactly
  90 days from redemption despite an older synthetic purchase timestamp.
- Actual MCP calls succeeded before rotation. Rotation issued a replacement once,
  the old key immediately returned 401, the new key worked, original expiry and
  redemption time remained unchanged, and daily usage carried forward.
- `/health` before/after matched the persisted source states and original feed
  timestamp with server version 1.0.0. No current timestamp or new feed was invented.
- Missing product configuration returned 503 without even a mock provider send.

The actual Gumroad MCP-pass product is still an open configuration item when
`GUMROAD_PRODUCT_ID` is absent; synthetic injected product data does not close it.
All synthetic keys, redemptions and quota rows were removed; the HTTP server was
stopped. The existing 789 opportunities and feed status were unchanged.

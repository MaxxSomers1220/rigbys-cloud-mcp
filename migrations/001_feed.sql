CREATE TABLE opportunities (
    opportunity_id text PRIMARY KEY,
    dedupe_key text NOT NULL UNIQUE,
    title_normalized text NOT NULL,
    sponsor_normalized text NOT NULL,
    deadline_parsed timestamptz,
    eligibility_parsed jsonb NOT NULL CHECK (jsonb_typeof(eligibility_parsed) = 'array'),
    award_amount_parsed jsonb,
    source_ids jsonb NOT NULL CHECK (jsonb_typeof(source_ids) = 'array'),
    growth_score integer CHECK (growth_score BETWEEN 0 AND 100),
    momentum_score integer CHECK (momentum_score BETWEEN 0 AND 100),
    novelty_score integer CHECK (novelty_score BETWEEN 0 AND 100),
    gap_score integer CHECK (gap_score BETWEEN 0 AND 100),
    methodology_version text NOT NULL,
    summary_short text NOT NULL,
    extracted_requirements jsonb NOT NULL CHECK (jsonb_typeof(extracted_requirements) = 'array'),
    feed_generated_at timestamptz NOT NULL,
    fetched_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    source_refs jsonb NOT NULL CHECK (jsonb_typeof(source_refs) = 'object'),
    change_log jsonb NOT NULL CHECK (jsonb_typeof(change_log) = 'array'),
    record jsonb NOT NULL CHECK (jsonb_typeof(record) = 'object')
);
CREATE INDEX opportunities_deadline_idx ON opportunities(deadline_parsed);
CREATE INDEX opportunities_sponsor_idx ON opportunities(sponsor_normalized);
CREATE INDEX opportunities_gap_idx ON opportunities(gap_score);
CREATE INDEX opportunities_search_idx ON opportunities USING gin (
    to_tsvector('english', coalesce(title_normalized, '') || ' ' || coalesce(summary_short, ''))
);

CREATE TABLE opportunity_links (
    opportunity_id text NOT NULL REFERENCES opportunities(opportunity_id) ON DELETE CASCADE,
    link_type text NOT NULL CHECK (link_type IN ('award', 'paper')),
    target_id text NOT NULL,
    target_url text NOT NULL,
    join_confidence double precision NOT NULL CHECK (join_confidence BETWEEN 0 AND 1),
    relationship text NOT NULL,
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    PRIMARY KEY(opportunity_id, link_type, target_id)
);
CREATE INDEX opportunity_links_target_idx ON opportunity_links(link_type, target_id);

CREATE TABLE api_keys (
    key_hash text PRIMARY KEY CHECK (key_hash ~ '^[a-f0-9]{64}$'),
    key_prefix text NOT NULL CHECK (length(key_prefix) <= 24),
    tier text NOT NULL CHECK (tier IN ('free', 'paid')),
    email text NOT NULL,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    rotated_at timestamptz,
    revoked_at timestamptz
);
CREATE INDEX api_keys_prefix_idx ON api_keys(key_prefix);
CREATE INDEX api_keys_expiry_idx ON api_keys(expires_at);
CREATE TABLE redemptions (
    license_key_hash text PRIMARY KEY CHECK (license_key_hash ~ '^[a-f0-9]{64}$'),
    api_key_hash text NOT NULL REFERENCES api_keys(key_hash),
    redeemed_at timestamptz NOT NULL DEFAULT now(),
    gumroad_sale_ref text NOT NULL
);
CREATE INDEX redemptions_api_key_idx ON redemptions(api_key_hash);
CREATE TABLE rate_limit_counters (
    key_hash text NOT NULL REFERENCES api_keys(key_hash) ON DELETE CASCADE,
    day date NOT NULL,
    calls integer NOT NULL DEFAULT 0 CHECK (calls >= 0),
    PRIMARY KEY(key_hash, day)
);
CREATE INDEX rate_limit_counters_day_idx ON rate_limit_counters(day);

-- Build status/cache are feed infrastructure, not MCP or auth implementations.
CREATE TABLE feed_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attempted_at timestamptz NOT NULL DEFAULT now(),
    feed_generated_at timestamptz,
    status text NOT NULL CHECK (status IN ('success', 'failed')),
    source_counts jsonb NOT NULL,
    source_status jsonb NOT NULL,
    error text,
    CHECK ((status = 'success') = (feed_generated_at IS NOT NULL))
);
CREATE INDEX feed_runs_success_idx ON feed_runs(feed_generated_at DESC) WHERE status = 'success';
CREATE TABLE source_cache (
    cache_name text PRIMARY KEY,
    payload jsonb NOT NULL,
    fetched_at timestamptz NOT NULL
);

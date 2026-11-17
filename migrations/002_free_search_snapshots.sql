-- Append-only basic-field history. This is not a sale or a paid-key issuer.
CREATE TABLE free_feed_snapshots (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feed_run_id bigint NOT NULL UNIQUE REFERENCES feed_runs(run_id),
    feed_generated_at timestamptz NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    capture_transaction xid8 NOT NULL DEFAULT pg_current_xact_id(),
    record_count integer NOT NULL CHECK (record_count > 0)
);
CREATE INDEX free_feed_snapshots_eligible_idx
    ON free_feed_snapshots(feed_generated_at DESC, captured_at DESC, snapshot_id DESC);
CREATE TABLE free_search_records (
    snapshot_id bigint NOT NULL REFERENCES free_feed_snapshots(snapshot_id),
    opportunity_id text NOT NULL,
    title_normalized text NOT NULL,
    sponsor_normalized text NOT NULL,
    deadline_parsed timestamptz,
    award_amount_parsed jsonb,
    source_refs jsonb NOT NULL,
    fetched_at timestamptz NOT NULL,
    deadline_precision text,
    PRIMARY KEY(snapshot_id, opportunity_id)
);
CREATE INDEX free_search_records_title_idx ON free_search_records USING gin (
    to_tsvector('english', coalesce(title_normalized, ''))
);
CREATE INDEX free_search_records_deadline_idx ON free_search_records(snapshot_id, deadline_parsed);
CREATE INDEX free_search_records_sponsor_idx ON free_search_records(snapshot_id, sponsor_normalized);

CREATE FUNCTION rigbys_force_snapshot_capture_time() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.captured_at := statement_timestamp();
    NEW.capture_transaction := pg_current_xact_id();
    RETURN NEW;
END;
$$;
CREATE TRIGGER free_feed_snapshots_capture_time BEFORE INSERT ON free_feed_snapshots
    FOR EACH ROW EXECUTE FUNCTION rigbys_force_snapshot_capture_time();
-- Only the transaction creating a header may add rows to it. Committing seals
-- the history against later insertion of fresh data under an aged timestamp.
CREATE FUNCTION rigbys_guard_snapshot_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM free_feed_snapshots
                   WHERE snapshot_id = NEW.snapshot_id
                     AND capture_transaction = pg_current_xact_id()) THEN
        RAISE EXCEPTION 'Free feed snapshots are sealed after capture' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER free_search_records_sealed BEFORE INSERT ON free_search_records
    FOR EACH ROW EXECUTE FUNCTION rigbys_guard_snapshot_insert();

CREATE FUNCTION rigbys_reject_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Free feed snapshots are immutable' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER free_feed_snapshots_immutable BEFORE UPDATE OR DELETE ON free_feed_snapshots
    FOR EACH ROW EXECUTE FUNCTION rigbys_reject_snapshot_mutation();
CREATE TRIGGER free_search_records_immutable BEFORE UPDATE OR DELETE ON free_search_records
    FOR EACH ROW EXECUTE FUNCTION rigbys_reject_snapshot_mutation();
CREATE TRIGGER free_feed_snapshots_no_truncate BEFORE TRUNCATE ON free_feed_snapshots
    FOR EACH STATEMENT EXECUTE FUNCTION rigbys_reject_snapshot_mutation();
CREATE TRIGGER free_search_records_no_truncate BEFORE TRUNCATE ON free_search_records
    FOR EACH STATEMENT EXECUTE FUNCTION rigbys_reject_snapshot_mutation();

-- Restrict reference field names, nested keys, scalar types, source identity,
-- source URL and timestamp shape. Summary/score metadata cannot ride along.
CREATE FUNCTION rigbys_free_source_refs(refs jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
SELECT coalesce(jsonb_object_agg(fields.key, allowed.refs), '{}'::jsonb)
FROM jsonb_each(CASE WHEN jsonb_typeof(refs) = 'object' THEN refs ELSE '{}'::jsonb END) AS fields
CROSS JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'source', item->'source', 'source_id', item->'source_id',
        'url', item->'url', 'fetched_at', item->'fetched_at')) AS refs
    FROM jsonb_array_elements(CASE WHEN jsonb_typeof(fields.value) = 'array'
                                  THEN fields.value ELSE '[]'::jsonb END) AS item
    WHERE jsonb_typeof(item) = 'object'
      AND item->>'source' = 'grants_gov'
      AND jsonb_typeof(item->'source_id') = 'string'
      AND item->>'source_id' ~ '^[A-Za-z0-9_-]{1,200}$'
      AND jsonb_typeof(item->'url') = 'string'
      AND item->>'url' ~ '^https://(www\.)?grants\.gov/search-results-detail/[A-Za-z0-9_-]+/?$'
      AND jsonb_typeof(item->'fetched_at') = 'string'
      AND item->>'fetched_at' ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
) AS allowed
WHERE fields.key IN ('title_normalized', 'sponsor_normalized', 'deadline_parsed',
                     'award_amount_parsed', 'deadline_precision', 'fetched_at')
  AND allowed.refs IS NOT NULL;
$$;

CREATE FUNCTION rigbys_capture_free_snapshot(requested_run_id bigint) RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    run_time timestamptz;
    captured_id bigint;
    total integer;
BEGIN
    SELECT snapshot_id INTO captured_id FROM free_feed_snapshots WHERE feed_run_id = requested_run_id;
    IF captured_id IS NOT NULL THEN
        RETURN captured_id;
    END IF;
    SELECT feed_generated_at INTO run_time FROM feed_runs
        WHERE run_id = requested_run_id AND status = 'success';
    IF run_time IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT count(*) INTO total FROM opportunities WHERE feed_generated_at = run_time;
    IF total = 0 THEN
        RETURN NULL;
    END IF;
    INSERT INTO free_feed_snapshots(feed_run_id,feed_generated_at,record_count)
        VALUES (requested_run_id,run_time,total) RETURNING snapshot_id INTO captured_id;
    INSERT INTO free_search_records(snapshot_id,opportunity_id,title_normalized,sponsor_normalized,
                                    deadline_parsed,award_amount_parsed,source_refs,fetched_at,deadline_precision)
    SELECT captured_id, opportunity_id, title_normalized, sponsor_normalized, deadline_parsed,
           CASE WHEN jsonb_typeof(award_amount_parsed) = 'object' THEN jsonb_build_object(
               'currency', CASE WHEN award_amount_parsed->>'currency' = 'USD' THEN 'USD' ELSE NULL END,
               'floor', CASE WHEN jsonb_typeof(award_amount_parsed->'floor') = 'number'
                                  AND (award_amount_parsed->>'floor')::numeric >= 0
                             THEN award_amount_parsed->'floor' ELSE NULL END,
               'ceiling', CASE WHEN jsonb_typeof(award_amount_parsed->'ceiling') = 'number'
                                    AND (award_amount_parsed->>'ceiling')::numeric >= 0
                               THEN award_amount_parsed->'ceiling' ELSE NULL END)
               ELSE NULL END,
           rigbys_free_source_refs(source_refs), fetched_at,
           CASE WHEN record->>'deadline_precision' IN ('date','rolling','unspecified')
                THEN record->>'deadline_precision' ELSE NULL END
    FROM opportunities WHERE feed_generated_at = run_time;
    RETURN captured_id;
END;
$$;

-- Existing records are captured NOW. Their historical generation timestamps do
-- not establish historical custody and cannot make them eligible immediately.
SELECT rigbys_capture_free_snapshot(run_id) FROM feed_runs WHERE status = 'success'
    ORDER BY run_id DESC LIMIT 1;

CREATE TABLE snapshot_exports (
    slot text PRIMARY KEY CHECK (slot IN ('current', 'previous')),
    run_id bigint NOT NULL UNIQUE REFERENCES feed_runs(run_id),
    record_count integer NOT NULL CHECK (record_count > 0),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    chunk_count integer NOT NULL CHECK (chunk_count > 0)
);

CREATE TABLE snapshot_export_chunks (
    run_id bigint NOT NULL REFERENCES snapshot_exports(run_id) ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    data bytea NOT NULL CHECK (octet_length(data) BETWEEN 1 AND 1048576),
    PRIMARY KEY (run_id, chunk_index)
);

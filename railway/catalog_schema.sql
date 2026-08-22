CREATE TABLE IF NOT EXISTS arc3_catalog_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    schema_version integer NOT NULL DEFAULT 1,
    baseline jsonb NOT NULL DEFAULT '{}'::jsonb,
    biases jsonb NOT NULL DEFAULT '{}'::jsonb,
    catalog_json jsonb NOT NULL DEFAULT '{"schemaVersion":1,"runs":[]}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO arc3_catalog_state (singleton)
VALUES (true)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS arc3_runs (
    run_id text PRIMARY KEY CHECK (run_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$'),
    schema_version integer NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'published' CHECK (status IN ('staged', 'published', 'superseded')),
    avg_score double precision NOT NULL DEFAULT 0,
    game_count integer NOT NULL DEFAULT 0,
    level_count integer NOT NULL DEFAULT 0,
    action_count bigint NOT NULL DEFAULT 0,
    generated_tokens bigint NOT NULL DEFAULT 0,
    duration_seconds double precision,
    started_at timestamptz,
    ended_at timestamptz,
    catalog_entry jsonb NOT NULL,
    score_curve jsonb NOT NULL DEFAULT '{"points":[]}'::jsonb,
    artifact_manifest_sha256 text,
    source text NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arc3_runs_score_idx
ON arc3_runs (status, avg_score DESC, run_id DESC);

CREATE TABLE IF NOT EXISTS arc3_game_scores (
    run_id text NOT NULL REFERENCES arc3_runs(run_id) ON DELETE CASCADE,
    game_id text NOT NULL,
    score double precision NOT NULL DEFAULT 0,
    levels_completed integer NOT NULL DEFAULT 0,
    levels_total integer NOT NULL DEFAULT 0,
    actions integer NOT NULL DEFAULT 0,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, game_id)
);

CREATE TABLE IF NOT EXISTS arc3_score_events (
    run_id text NOT NULL REFERENCES arc3_runs(run_id) ON DELETE CASCADE,
    series text NOT NULL CHECK (series IN ('time', 'tokens')),
    sequence integer NOT NULL,
    recorded_at timestamptz,
    elapsed_seconds double precision NOT NULL DEFAULT 0,
    cumulative_actions bigint,
    cumulative_generated_tokens bigint,
    mean_score double precision NOT NULL DEFAULT 0,
    kind text NOT NULL,
    game_id text,
    action integer,
    level integer,
    game_score double precision,
    timestamp_basis text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, series, sequence)
);

CREATE INDEX IF NOT EXISTS arc3_score_events_lookup_idx
ON arc3_score_events (run_id, series, sequence);

CREATE TABLE IF NOT EXISTS arc3_run_artifacts (
    run_id text NOT NULL REFERENCES arc3_runs(run_id) ON DELETE CASCADE,
    relative_path text NOT NULL,
    artifact_kind text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_count bigint NOT NULL CHECK (byte_count >= 0),
    PRIMARY KEY (run_id, relative_path)
);

CREATE TABLE IF NOT EXISTS arc3_publications (
    publication_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES arc3_runs(run_id) ON DELETE CASCADE,
    source text NOT NULL,
    artifact_manifest_sha256 text NOT NULL CHECK (artifact_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    file_count integer NOT NULL CHECK (file_count > 0),
    byte_count bigint NOT NULL CHECK (byte_count > 0),
    published_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS arc3_publications_run_idx
ON arc3_publications (run_id, published_at DESC);

CREATE OR REPLACE FUNCTION arc3_refresh_catalog_snapshot()
RETURNS void
LANGUAGE sql
AS $$
    UPDATE arc3_catalog_state
    SET catalog_json = jsonb_build_object(
            'schemaVersion', schema_version,
            'baseline', baseline,
            'biases', biases,
            'runs', COALESCE(
                (
                    SELECT jsonb_agg(r.catalog_entry ORDER BY r.avg_score DESC, r.run_id DESC)
                    FROM arc3_runs AS r
                    WHERE r.status = 'published'
                ),
                '[]'::jsonb
            )
        ),
        updated_at = now()
    WHERE singleton = true;
$$;

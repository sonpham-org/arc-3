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

-- Thumbs up / thumbs down on one section of the model's own output (THINKING, ASSISTANT, a
-- TOOL CALL), with the reviewer's reason. These are training labels, so each row keeps the
-- exact text it judged: a run can be re-exported in place, and a mark must never be re-aimed
-- at different words. No foreign key to arc3_runs for the same reason -- a label outlives the
-- copy of the run it was made on. See railway/trace_feedback.py.
CREATE TABLE IF NOT EXISTS arc3_trace_feedback (
    feedback_id bigserial PRIMARY KEY,
    run_id text NOT NULL CHECK (run_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$'),
    game_index integer NOT NULL CHECK (game_index >= 0),
    game_id text,
    step_index integer NOT NULL CHECK (step_index >= 0),
    turn integer CHECK (turn >= 0),
    section_index integer NOT NULL CHECK (section_index >= 0),
    section_label text NOT NULL,
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    content text NOT NULL,
    vote text NOT NULL CHECK (vote IN ('up', 'down')),
    reason text,
    reviewer text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, game_index, step_index, section_index, content_sha256, reviewer)
);

CREATE INDEX IF NOT EXISTS arc3_trace_feedback_updated_idx
ON arc3_trace_feedback (updated_at, feedback_id);

-- Trace review (RL): points in a game that several plays reach (nodes), the plays' paths forward
-- from them, the sets of paths shown side by side (splits: LEFT / RIGHT / ...), the raters and
-- their verdicts. A path's turns (thinking, code, actions, boards) live on the volume under
-- /srv/data/_review/paths/<content_sha256>.json; these rows index them. Splits are made by the
-- server whenever new paths reach a node, so the pool keeps growing as runs are published.
-- See railway/rl_review.py.
CREATE TABLE IF NOT EXISTS rl_review_nodes (
    node_id text PRIMARY KEY CHECK (node_id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$'),
    kind text NOT NULL CHECK (kind IN ('level_start', 'fork')),
    game_id text NOT NULL,
    level integer NOT NULL CHECK (level >= 1),
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rl_review_paths (
    path_id text PRIMARY KEY CHECK (path_id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$'),
    node_id text NOT NULL REFERENCES rl_review_nodes (node_id),
    run_id text NOT NULL,
    play text NOT NULL,
    model text NOT NULL,
    level integer NOT NULL,
    cleared boolean NOT NULL,
    turns integer NOT NULL CHECK (turns >= 0),
    actions integer NOT NULL CHECK (actions >= 0),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rl_review_paths_node_idx ON rl_review_paths (node_id);

CREATE TABLE IF NOT EXISTS rl_review_splits (
    split_id text PRIMARY KEY CHECK (split_id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,254}$'),
    node_id text NOT NULL REFERENCES rl_review_nodes (node_id),
    path_ids text[] NOT NULL CHECK (cardinality(path_ids) BETWEEN 2 AND 4),
    priority real NOT NULL DEFAULT 0,
    source text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rl_review_splits_node_idx ON rl_review_splits (node_id);

-- Outside raters hold an invite key (only its SHA-256 is stored); the signed-in team rates as
-- 'team:<email>' without a row here.
CREATE TABLE IF NOT EXISTS rl_review_raters (
    rater_id text PRIMARY KEY CHECK (rater_id ~ '^r_[0-9a-f]{12}$'),
    name text NOT NULL,
    key_sha256 text NOT NULL UNIQUE CHECK (key_sha256 ~ '^[0-9a-f]{64}$'),
    created_by text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rl_review_ratings (
    rating_id bigserial PRIMARY KEY,
    split_id text NOT NULL REFERENCES rl_review_splits (split_id),
    rater_id text NOT NULL,
    choice text NOT NULL,
    confidence integer CHECK (confidence BETWEEN 1 AND 3),
    scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    marks jsonb NOT NULL DEFAULT '[]'::jsonb,
    comment text,
    seconds integer CHECK (seconds >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (split_id, rater_id)
);

CREATE INDEX IF NOT EXISTS rl_review_ratings_updated_idx ON rl_review_ratings (updated_at, rating_id);

-- RL2 decision tree (turn coach). A node is the game state where the coach made a decision
-- ('<game>:L<level>:<board_hash>'); plays that reach the same state merge into one node (no forks).
-- A branch is one decision taken there: mode, cap, probability, what the coach saw (features), what
-- followed (outcome), the turn's trace (on the volume under /srv/data/_rl2/traces/<sha256>.json) and
-- the node of that play's next decision (child_id, no FK: the child may be published later; null at
-- the play's end). Publication is per run: a run's branches are replaced whole. See rl_review.py.
CREATE TABLE IF NOT EXISTS rl2_tree_nodes (
    id text PRIMARY KEY CHECK (id ~ '^[a-z0-9]{4}:L[0-9]{1,4}:[0-9a-f]{12}$'),
    game text NOT NULL,
    level integer NOT NULL CHECK (level >= 0),
    board_hash text NOT NULL CHECK (board_hash ~ '^[0-9a-f]{12}$'),
    board jsonb,
    first_run text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rl2_tree_nodes_game_idx ON rl2_tree_nodes (game, level);

CREATE TABLE IF NOT EXISTS rl2_tree_branches (
    id text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$'),
    node_id text NOT NULL REFERENCES rl2_tree_nodes (id),
    child_id text,
    run text NOT NULL,
    play text NOT NULL,
    build text NOT NULL,
    policy text,
    decision integer NOT NULL CHECK (decision >= 0),
    mode text NOT NULL CHECK (mode ~ '^[a-z_]{1,20}$'),
    cap integer CHECK (cap >= 0),
    prob double precision,
    features jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_sha text CHECK (trace_sha ~ '^[0-9a-f]{64}$'),
    published_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rl2_tree_branches_node_idx ON rl2_tree_branches (node_id);
CREATE INDEX IF NOT EXISTS rl2_tree_branches_run_idx ON rl2_tree_branches (run);
CREATE INDEX IF NOT EXISTS rl2_tree_branches_child_idx ON rl2_tree_branches (child_id);

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
                    SELECT jsonb_agg(
                        r.catalog_entry
                        || jsonb_strip_nulls(
                            jsonb_build_object('duration_seconds', r.duration_seconds)
                        )
                        ORDER BY r.avg_score DESC, r.run_id DESC
                    )
                    FROM arc3_runs AS r
                    WHERE r.status = 'published'
                ),
                '[]'::jsonb
            )
        ),
        updated_at = now()
    WHERE singleton = true;
$$;

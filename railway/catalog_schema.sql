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

-- One good/bad mark (and its note) on one turn, saved the moment the rater makes it, before any verdict exists.
-- Submitting the pair's rating rewrites these rows from the rating's own marks, so the two never disagree.
CREATE TABLE IF NOT EXISTS rl_review_marks (
    split_id text NOT NULL REFERENCES rl_review_splits (split_id),
    rater_id text NOT NULL,
    path_id text NOT NULL,
    step integer NOT NULL CHECK (step >= 0),
    verdict text CHECK (verdict IN ('up', 'down')),
    note text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (split_id, rater_id, path_id, step)
);

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

-- The universal game tree (gt_*): any rollout's data, any harness, any policy, stored once as steps and read as
-- five trees. Separate from RL v1 (Firestore) and from the RL2 tables above, which stay for now.
--   gt_steps     one action of one rollout (the mode chosen; 'stock' for an uncoached turn): the screen before
--                it, level and moves, where it led, what the coach saw (features), what followed (outcome),
--                its trace (on the volume, /srv/data/_gtree/traces/<sha256>.json), and its node in each tree
--                (n1..n5) plus the node it led to (c1..c5, no FK; null at a rollout's end). Each tree is a
--                GROUP BY over the same rows: t1 path (context-aware), t2 screen + moves, t3 level + screen,
--                t4 screen only, t5 level + screen + moves bucketed by 6 (the restart grid).
--                moves_step: game moves (engine actions the competition counts, resets included) executed in
--                this step; tokens: tokens generated; ctx_before / ctx_after: sha256 of the context before and
--                after the step (gs://cellens-ai-artifacts/arc3-gtree/v1/ctx/<sha>.json.gz); state_ref: sha256
--                of a harness / REPL state record; resumable: ctx_before is exact (the step can be re-run).
--                outcome.moves_to_clear: game moves from the start of this step until this level was cleared
--                in this rollout (null: never cleared); the objective is fewest moves to clear a level.
--   gt_nodes     a node of one tree. The publisher computes the ids; the root of each (tree, game) is the
--                game start, '<game>:t<k>:root', with no screen. parent and depth are kept for t1 only.
--   gt_screens   one board per screen hash, shared by all trees (the first board sent is kept).
--   gt_rollouts  one play: from the game start (origin_state null, origin_kind 'start') or restarted from a
--                t1 node in the middle of the tree (Go-Explore style: origin_state the node, origin_kind
--                replay_exact / replay_actions / restore / snapshot, origin_edge the step it branched after, if any).
-- Publication is per rollout: a rollout's steps are replaced whole. See rl_review.py.
CREATE TABLE IF NOT EXISTS gt_screens (
    screen_hash text PRIMARY KEY CHECK (screen_hash ~ '^[0-9a-f]{12}$'),
    board jsonb,
    first_seen timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gt_nodes (
    id text PRIMARY KEY CONSTRAINT gt_nodes_id_t5 CHECK (id ~ '^[a-z0-9]{4}:t[1-5]:([0-9a-f]{16}|root)$'),
    tree smallint NOT NULL CONSTRAINT gt_nodes_tree_t5 CHECK (tree BETWEEN 1 AND 5),
    game text NOT NULL CHECK (game ~ '^[a-z0-9]{4}$'),
    level integer CHECK (level >= 0),
    moves integer CHECK (moves >= 0),
    screen_hash text CHECK (screen_hash ~ '^[0-9a-f]{12}$'),
    parent text,
    depth integer CHECK (depth >= 0),
    first_seen timestamptz NOT NULL DEFAULT now(),
    CHECK (id LIKE game || ':t' || tree || ':%'),
    CHECK (tree = 1 OR (parent IS NULL AND depth IS NULL))
);

CREATE INDEX IF NOT EXISTS gt_nodes_game_idx ON gt_nodes (game, tree);
CREATE INDEX IF NOT EXISTS gt_nodes_parent_idx ON gt_nodes (parent);

CREATE TABLE IF NOT EXISTS gt_rollouts (
    id text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,199}$'),
    game text NOT NULL CHECK (game ~ '^[a-z0-9]{4}$'),
    run text NOT NULL,
    build text NOT NULL,
    model text NOT NULL,
    harness text NOT NULL,
    policy text,
    origin_state text REFERENCES gt_nodes (id) CHECK (origin_state ~ ':t1:'),
    origin_edge text,
    origin_kind text NOT NULL DEFAULT 'start'
        CONSTRAINT gt_rollouts_origin_kind_snapshot
        CHECK (origin_kind IN ('start', 'replay_exact', 'replay_actions', 'restore', 'snapshot')),
    status text NOT NULL CHECK (status ~ '^[A-Za-z0-9_.-]{1,40}$'),
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    published_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((origin_state IS NULL) = (origin_kind = 'start'))
);

CREATE INDEX IF NOT EXISTS gt_rollouts_origin_idx ON gt_rollouts (origin_state);
CREATE INDEX IF NOT EXISTS gt_rollouts_game_idx ON gt_rollouts (game);
CREATE INDEX IF NOT EXISTS gt_rollouts_run_idx ON gt_rollouts (run);

CREATE TABLE IF NOT EXISTS gt_steps (
    id text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9][A-Za-z0-9:._~-]{0,254}$'),
    rollout_id text NOT NULL REFERENCES gt_rollouts (id) ON DELETE CASCADE,
    seq integer NOT NULL CHECK (seq >= 0),
    game text NOT NULL CHECK (game ~ '^[a-z0-9]{4}$'),
    level integer NOT NULL CHECK (level >= 0),
    moves integer NOT NULL CHECK (moves >= 0),
    screen_hash text NOT NULL CHECK (screen_hash ~ '^[0-9a-f]{12}$'),
    next_screen_hash text CHECK (next_screen_hash ~ '^[0-9a-f]{12}$'),
    next_level integer CHECK (next_level >= 0),
    next_moves integer CHECK (next_moves >= 0),
    action text NOT NULL CHECK (action ~ '^[A-Za-z0-9_.:+-]{1,40}$'),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    features jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_sha text CHECK (trace_sha ~ '^[0-9a-f]{64}$'),
    hidden_ref text CHECK (length(hidden_ref) <= 500),
    n1 text NOT NULL REFERENCES gt_nodes (id),
    n2 text NOT NULL REFERENCES gt_nodes (id),
    n3 text NOT NULL REFERENCES gt_nodes (id),
    n4 text NOT NULL REFERENCES gt_nodes (id),
    n5 text NOT NULL REFERENCES gt_nodes (id),
    c1 text,
    c2 text,
    c3 text,
    c4 text,
    c5 text,
    moves_step integer NOT NULL DEFAULT 0 CONSTRAINT gt_steps_moves_step_check CHECK (moves_step >= 0),
    tokens integer CONSTRAINT gt_steps_tokens_check CHECK (tokens >= 0),
    ctx_before text CONSTRAINT gt_steps_ctx_before_check CHECK (ctx_before ~ '^[0-9a-f]{64}$'),
    ctx_after text CONSTRAINT gt_steps_ctx_after_check CHECK (ctx_after ~ '^[0-9a-f]{64}$'),
    state_ref text CONSTRAINT gt_steps_state_ref_check CHECK (state_ref ~ '^[0-9a-f]{64}$'),
    resumable boolean NOT NULL DEFAULT false,
    UNIQUE (rollout_id, seq),
    -- c1..c5 all set or all null (the rollout's end); n5 IS NULL only on rows stored before t5 (see below)
    CONSTRAINT gt_steps_children_t5 CHECK (
        ((c1 IS NULL) = (c2 IS NULL) AND (c2 IS NULL) = (c3 IS NULL) AND (c3 IS NULL) = (c4 IS NULL))
        AND (n5 IS NULL OR (c4 IS NULL) = (c5 IS NULL))),
    CONSTRAINT gt_steps_resumable_ctx CHECK (NOT resumable OR ctx_before IS NOT NULL)
);

-- Migrations for a database made before t5 and the moves columns (3-Oct-2026). Safe to re-run on every start:
-- each step checks before it changes anything. Rows stored before t5 keep n5 / c5 null (the server refuses new
-- steps without them); n5 becomes NOT NULL once no such row is left.
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS n5 text REFERENCES gt_nodes (id);
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS c5 text;
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS moves_step integer NOT NULL DEFAULT 0
    CONSTRAINT gt_steps_moves_step_check CHECK (moves_step >= 0);
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS tokens integer CONSTRAINT gt_steps_tokens_check CHECK (tokens >= 0);
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS ctx_before text
    CONSTRAINT gt_steps_ctx_before_check CHECK (ctx_before ~ '^[0-9a-f]{64}$');
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS ctx_after text
    CONSTRAINT gt_steps_ctx_after_check CHECK (ctx_after ~ '^[0-9a-f]{64}$');
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS state_ref text
    CONSTRAINT gt_steps_state_ref_check CHECK (state_ref ~ '^[0-9a-f]{64}$');
ALTER TABLE gt_steps ADD COLUMN IF NOT EXISTS resumable boolean NOT NULL DEFAULT false;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gt_nodes_id_t5') THEN
        ALTER TABLE gt_nodes DROP CONSTRAINT IF EXISTS gt_nodes_id_check;
        ALTER TABLE gt_nodes ADD CONSTRAINT gt_nodes_id_t5 CHECK (id ~ '^[a-z0-9]{4}:t[1-5]:([0-9a-f]{16}|root)$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gt_nodes_tree_t5') THEN
        ALTER TABLE gt_nodes DROP CONSTRAINT IF EXISTS gt_nodes_tree_check;
        ALTER TABLE gt_nodes ADD CONSTRAINT gt_nodes_tree_t5 CHECK (tree BETWEEN 1 AND 5);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gt_steps_children_t5') THEN
        ALTER TABLE gt_steps DROP CONSTRAINT IF EXISTS gt_steps_check;
        ALTER TABLE gt_steps ADD CONSTRAINT gt_steps_children_t5 CHECK (
            ((c1 IS NULL) = (c2 IS NULL) AND (c2 IS NULL) = (c3 IS NULL) AND (c3 IS NULL) = (c4 IS NULL))
            AND (n5 IS NULL OR (c4 IS NULL) = (c5 IS NULL)));
    END IF;
    -- the RL rollout server restores a try from a harness state snapshot: origin_kind 'snapshot' (3-Oct-2026)
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gt_rollouts_origin_kind_snapshot') THEN
        ALTER TABLE gt_rollouts DROP CONSTRAINT IF EXISTS gt_rollouts_origin_kind_check;
        ALTER TABLE gt_rollouts ADD CONSTRAINT gt_rollouts_origin_kind_snapshot
            CHECK (origin_kind IN ('start', 'replay_exact', 'replay_actions', 'restore', 'snapshot'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'gt_steps_resumable_ctx') THEN
        ALTER TABLE gt_steps ADD CONSTRAINT gt_steps_resumable_ctx CHECK (NOT resumable OR ctx_before IS NOT NULL);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'gt_steps'::regclass AND attname = 'n5'
               AND NOT attnotnull) AND NOT EXISTS (SELECT 1 FROM gt_steps WHERE n5 IS NULL) THEN
        ALTER TABLE gt_steps ALTER COLUMN n5 SET NOT NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS gt_steps_n1_idx ON gt_steps (n1, action);
CREATE INDEX IF NOT EXISTS gt_steps_n2_idx ON gt_steps (n2, action);
CREATE INDEX IF NOT EXISTS gt_steps_n3_idx ON gt_steps (n3, action);
CREATE INDEX IF NOT EXISTS gt_steps_n4_idx ON gt_steps (n4, action);
CREATE INDEX IF NOT EXISTS gt_steps_n5_idx ON gt_steps (n5, action);
CREATE INDEX IF NOT EXISTS gt_steps_c1_idx ON gt_steps (c1);
CREATE INDEX IF NOT EXISTS gt_steps_c2_idx ON gt_steps (c2);
CREATE INDEX IF NOT EXISTS gt_steps_c3_idx ON gt_steps (c3);
CREATE INDEX IF NOT EXISTS gt_steps_c4_idx ON gt_steps (c4);
CREATE INDEX IF NOT EXISTS gt_steps_c5_idx ON gt_steps (c5);
CREATE INDEX IF NOT EXISTS gt_steps_rollout_idx ON gt_steps (rollout_id);
DROP INDEX IF EXISTS gt_steps_game_idx;
CREATE INDEX IF NOT EXISTS gt_steps_game_level_idx ON gt_steps (game, level);

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

-- Human attention is reserved for unresolved clusters. Diagnostic payloads are immutable;
-- decisions record who reviewed the exact evidence, never an automatic training reward.
CREATE TABLE IF NOT EXISTS trace_triage_items (
    id text PRIMARY KEY CHECK (id ~ '^[0-9a-f]{64}$'),
    cluster_key text NOT NULL,
    game text NOT NULL,
    route text NOT NULL CHECK (route IN ('human', 'assistant')),
    priority integer NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trace_triage_queue_idx ON trace_triage_items (route, priority DESC) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS trace_triage_cluster_idx ON trace_triage_items (cluster_key, status);

CREATE TABLE IF NOT EXISTS trace_triage_decisions (
    decision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id text NOT NULL REFERENCES trace_triage_items(id),
    cluster_key text NOT NULL,
    reviewer text NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('confirmed', 'reasonable', 'insufficient', 'dismissed')),
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 4000),
    seconds integer NOT NULL DEFAULT 0 CHECK (seconds BETWEEN 0 AND 86400),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trace_triage_decisions_cluster_idx ON trace_triage_decisions (cluster_key, created_at);

-- Mode explorer Play button: every Spark runner job view the site relays (railway/spark_runner.py) is kept here,
-- so a game's results table still loads when the runner on the Sparks cannot be reached.
CREATE TABLE IF NOT EXISTS arc3_spark_runner_jobs (
    job_id text PRIMARY KEY CHECK (job_id ~ '^[a-z0-9-]{8,40}$'),
    game text NOT NULL,
    status text NOT NULL,
    view jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arc3_spark_runner_jobs_game_idx
ON arc3_spark_runner_jobs (game, job_id DESC);

-- Game evolution trees and human feedback for the Games page.
-- Applied on every boot by catalog_server.py, after catalog_schema.sql; every statement is
-- idempotent. See games_store.py for who may read and write what.
--
-- A tree is one family of games. Its root is a seed game; every uploaded source is an
-- immutable, content-addressed version (version_id = "<game_id>@<first 12 hex of sha256>"),
-- linked to the version it was made from, and marked as one of:
--   seed      the root: a game that came from nowhere in this catalog
--   revision  the same game, improved. It continues its parent's line, even when the id
--             changes on the way (q041-v1 -> q041-v2 is one line)
--   branch    a new game that grew out of an old one; it starts a line of its own
-- A line's latest version is its current, best version; the root line's is the tree's.

CREATE TABLE IF NOT EXISTS arc3_game_trees (
    tree_id text PRIMARY KEY CHECK (tree_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$'),
    root_game_id text NOT NULL,
    family text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS arc3_games (
    game_id text PRIMARY KEY CHECK (game_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$'),
    tree_id text NOT NULL REFERENCES arc3_game_trees(tree_id),
    family text NOT NULL CHECK (family ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
    title text NOT NULL,
    description text,
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    default_fps integer NOT NULL DEFAULT 6 CHECK (default_fps BETWEEN 1 AND 60),
    derived_from text,
    hidden boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arc3_games_tree_idx ON arc3_games (tree_id);

CREATE TABLE IF NOT EXISTS arc3_game_versions (
    version_id text PRIMARY KEY CHECK (version_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,99}@[0-9a-f]{12}$'),
    game_id text NOT NULL REFERENCES arc3_games(game_id),
    tree_id text NOT NULL REFERENCES arc3_game_trees(tree_id),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    parent_version_id text REFERENCES arc3_game_versions(version_id),
    kind text NOT NULL CHECK (kind IN ('seed', 'revision', 'branch')),
    created_at timestamptz NOT NULL,
    author_kind text NOT NULL CHECK (author_kind IN ('gpt', 'claude', 'human', 'other', 'unknown')),
    author_model text,
    author_name text,
    reason text NOT NULL,
    details text,
    src_file text NOT NULL,
    class_name text NOT NULL,
    tile_scale integer,
    byte_count integer NOT NULL CHECK (byte_count > 0),
    has_thumbnail boolean NOT NULL DEFAULT false,
    origin text NOT NULL,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    published_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (game_id, sha256)
);

CREATE INDEX IF NOT EXISTS arc3_game_versions_tree_idx
ON arc3_game_versions (tree_id, created_at);

CREATE INDEX IF NOT EXISTS arc3_game_versions_game_idx
ON arc3_game_versions (game_id, created_at DESC);

-- One row per submitted review. Team rows come from signed-in reviewers (oauth2-proxy
-- identity); public rows are anonymous and are always ranked after team rows.
CREATE TABLE IF NOT EXISTS arc3_game_feedback (
    feedback_id bigserial PRIMARY KEY,
    game_id text NOT NULL,
    version_id text NOT NULL,
    reviewer_class text NOT NULL CHECK (reviewer_class IN ('team', 'public')),
    reviewer text,
    visitor_id text,
    outcome text CHECK (outcome IN ('won', 'lost', 'gave_up', 'in_progress')),
    levels_completed integer CHECK (levels_completed >= 0),
    levels_total integer CHECK (levels_total >= 0),
    actions integer CHECK (actions >= 0),
    resets integer CHECK (resets >= 0),
    undos integer CHECK (undos >= 0),
    seconds integer CHECK (seconds >= 0),
    fun smallint CHECK (fun BETWEEN 1 AND 5),
    clarity smallint CHECK (clarity BETWEEN 1 AND 5),
    difficulty smallint CHECK (difficulty BETWEEN 1 AND 5),
    novelty smallint CHECK (novelty BETWEEN 1 AND 5),
    flags text[] NOT NULL DEFAULT '{}',
    goal_guess text,
    liked text,
    disliked text,
    suggestion text,
    bugs text,
    verdict text CHECK (verdict IN ('keep', 'revise', 'branch', 'retire')),
    hidden boolean NOT NULL DEFAULT false,
    client jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_hint text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arc3_game_feedback_version_idx
ON arc3_game_feedback (version_id, reviewer_class);

CREATE INDEX IF NOT EXISTS arc3_game_feedback_game_idx
ON arc3_game_feedback (game_id, created_at DESC);

CREATE INDEX IF NOT EXISTS arc3_game_feedback_reviewer_idx
ON arc3_game_feedback (reviewer, version_id)
WHERE reviewer_class = 'team';

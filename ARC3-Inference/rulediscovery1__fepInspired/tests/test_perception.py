# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/perception.py: object-event labels in the
#   object_events alphabet, the pre = post board advance (the stale-board bug of
#   efe_trace_analysis.analyse, round four), persistent object ids, Scene.apply reproducing the real
#   next board, and label <-> parts round trips.
# SRP/DRY check: Pass -- fixtures from synth.py; no logic duplicated from the package.
from __future__ import annotations

from rulediscovery1__fepInspired.perception import Action, Effect, Perceiver, Scene, label_of, label_parts, parts_to_effects
from rulediscovery1__fepInspired.tests.synth import RIGHT, MoverEnv, mover_comp


def test_move_gives_object_event_label():
    env = MoverEnv()
    p = Perceiver()
    p.begin(env.board())
    grid, _, _ = env.step(RIGHT)
    tr = p.observe(RIGHT, grid)
    assert tr.label == "mv+1+0"
    assert tr.scored and not tr.terminal


def test_pre_board_advances_every_step():
    env = MoverEnv()
    p = Perceiver()
    p.begin(env.board())
    g1, _, _ = env.step(RIGHT)
    t1 = p.observe(RIGHT, g1)
    g2, _, _ = env.step(RIGHT)
    t2 = p.observe(RIGHT, g2)
    assert t2.pre.raw == t1.post.raw == g1
    assert p.current.raw == g2
    # against a stale first board the second step would read as a two-cell move
    assert t2.label == "mv+1+0"


def test_object_identity_survives_a_move():
    env = MoverEnv()
    p = Perceiver()
    p.begin(env.board())
    grid, _, _ = env.step(RIGHT)
    tr = p.observe(RIGHT, grid)
    a, b = mover_comp(tr.pre), mover_comp(tr.post)
    assert tr.pre.track_ids[a.id] == tr.post.track_ids[b.id]


def test_scene_apply_matches_the_real_next_board():
    env = MoverEnv()
    pre = Scene.from_grid(env.board(), None)
    grid, _, _ = env.step(RIGHT)
    real = Scene.from_grid(grid, None)
    imagined = pre.apply([Effect("move", mover_comp(pre).id, dx=1, dy=0)])
    assert imagined.signature() == real.signature()
    assert imagined.raw == real.raw


def test_label_parts_round_trip():
    assert label_parts("grow|mv+1+0x2") == ["grow", "mv+1+0", "mv+1+0"]
    assert label_parts("rc3>5x3+") == ["rc3>5"] * 3
    assert label_parts("nothing") == [] and label_parts("level_clear") == []
    assert label_of(parts_to_effects(["mv+1+0", "grow", "mv+1+0"])) == "grow|mv+1+0x2"
    assert label_of([]) == "nothing"


def test_click_action_row_dict_is_parsable_by_distill():
    from rulediscovery1__fepInspired._distill import efe
    row = Action("ACTION6", 7, 9).row_dict()
    m = efe.MOUSE_RE.search(row["action_display"])
    assert (int(m.group(1)), int(m.group(2))) == (7, 9)

# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic source 24-September-2026)
# PURPOSE: Hypothesis generation for the rule discovery prototype (OpenMind, #arc-3, 23-Sep-2026
#   21:03 ET): the cheap, reliable source of rules (template fitting on the events seen so far), and
#   the search that assembles rules into candidate RuleSets for beliefs.py.
#     - TemplateFitter.propose(records): instantiates every rules.py template the stored steps
#       support -- MoveRule (per button and moved object type: modal displacement; blocker / passable
#       colours from the look-ahead on steps where it did / did not move), ClickToggleRule (clicked
#       shape and colour -> colour after), NoOpRule (action keys that mostly did nothing),
#       CounterRule (label parts recurring at a fixed step period within a level, per scope; parts
#       that always co-occur tick together), PersistRule (repeat the previous outcome, or a fitted
#       deterministic prev -> next table; for the previous step and for the same context), and
#       ContactRule (what happened when a fitted mover ran into a colour: push / collect / convert /
#       stop). Each candidate must pass a part-level track record on the same steps (support and
#       precision), so the pool stays small.
#     - RuleSetBuilder.build: beam search over rule sets by the exact posterior score used in
#       beliefs.py (-description length + prequential log likelihood by replay), seeded with the
#       current survivors, so the posterior's own objective decides what gets composed.
#     - HypothesisProposer: facade: fitter + the (stub) language-model provider + builder.
#   The second hypothesis source (a language model writing rules and win conditions as code) enters
#   only through rules.RuleProvider; the provider here is rules.StubLLMRuleProvider (returns []).
#   23-Sep-2026 23:10 ET: fit_moves fuses types that always move together by the same displacement
#   (co_movers) into one MoveRule with a partner group and a group look-ahead, so a two-colour sprite
#   is one mover and its own other half no longer counts as a wall. fit_pads merges a sprite's movers
#   into one PadMoveRule (all arrows, one price).
#   24-Sep-2026 HDC integration A/B (OpenMind 10:17 ET): with use_hdc the fitter proposes rules.TapeRule once the
#   ghost tape has explained an object, and (fate piece) fits movers with the common-fate group rules.FATE instead
#   of co_movers' type-level groups (fate_riders drops the parts that ride on the controlled sprite).
#   24-Sep-2026 tensor-logic overhaul: HypothesisProposer.tl (a tl.bridge.TLSource, AgentConfig.use_tl) adds the learned,
#   thresholded tensor-logic programs (tl/rule.TLRule) to the candidates; templates=False drops the template fitter
#   (the tl_only arm). Defaults (tl None, templates True) = exactly the old candidates.
# SRP/DRY check: Pass -- look-ahead from agency_contexts, labels / parts from perception.py (object_events
#   alphabet), scoring from beliefs.score_ruleset. Fitting rules from events is new in this package.
"""Template fitting and rule-set search."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from ._distill import ag
from .beliefs import PredictionCache, Record, score_ruleset
from .rules import (FATE, SCOPES, ClickToggleRule, ContactRule, CounterRule, MoveRule, NoOpRule, PadMoveRule,
                    PersistRule, Rule, RuleProvider, RuleSet, StubLLMRuleProvider, TapeRule, _mover, action_key,
                    group_look_ahead, scopes_of, sprite_parts)


@dataclass
class FitConfig:
    min_support: int = 2           # observations a rule needs before it is proposed
    min_precision: float = 0.7     # part-level hit rate on the steps it fires on
    counter_purity: float = 0.8    # share of gaps equal to the modal period
    persist_purity: float = 0.8    # share of a prev label's successors equal to its modal successor
    max_candidates: int = 40


def _sub_multiset(a: Iterable[str], b: Iterable[str]) -> bool:
    ca, cb = Counter(a), Counter(b)
    return all(cb[k] >= n for k, n in ca.items())


class TemplateFitter:
    """Instantiate rule templates from stored steps (records from beliefs.BeliefState)."""

    def __init__(self, cfg: Optional[FitConfig] = None):
        self.cfg = cfg or FitConfig()

    # -- entry point
    def propose(self, records: list[Record]) -> list[Rule]:
        recs = [r for r in records if r.tr.scored]
        if not recs:
            return []
        counters = self.fit_counters(recs)
        counter_parts = {p for c in counters for p in c.parts}
        moves = self.fit_moves(recs)
        cands: list[Rule] = []
        cands += moves
        cands += self.fit_pads(moves)
        cands += self.fit_contacts(recs, moves, counter_parts)
        cands += self.fit_toggles(recs)
        cands += self.fit_noops(recs, counter_parts)
        cands += self.fit_persist(recs)
        if any(r.rc.tape is not None for r in recs):
            cands.append(TapeRule())                 # HDC: the ghost tape has explained an object this play
        kept = [r for r in cands if self.passes(r, recs, counter_parts)]
        kept += [c for c in counters if self.passes(c, recs, counter_parts)]
        kept.sort(key=lambda r: -self.track_record(r, recs, counter_parts)[1])
        return kept[: self.cfg.max_candidates]

    # -- track record (part level, so a rule is not blamed for events other rules explain)
    def track_record(self, rule: Rule, recs: list[Record], counter_parts: set) -> tuple[int, int]:
        fires = hits = 0
        for rec in recs:
            eff = rule.predict(rec.rc)
            if eff is None:
                continue
            if isinstance(rule, TapeRule) and rec.rc.tape[3] == "moves" and not any(
                    k == rec.rc.agent_type and (dy, dx) != (0, 0) for k, dy, dx in rec.tr.moves):
                continue                         # player-move clock and the player did not move: no claim
            fires += 1
            pred = [e.label_part() for e in eff]
            actual = rec.tr.parts()
            if rule.kind == "modifier":
                own = set(getattr(rule, "parts", ()))
                hits += int(_sub_multiset(pred, actual) if pred else not (own & set(actual)))
            elif pred:
                hits += int(_sub_multiset(pred, actual))
            else:
                hits += int(set(actual) <= counter_parts)
        return fires, hits

    def passes(self, rule: Rule, recs: list[Record], counter_parts: set) -> bool:
        fires, hits = self.track_record(rule, recs, counter_parts)
        return fires >= self.cfg.min_support and hits >= self.cfg.min_precision * fires

    # -- templates
    def co_movers(self, recs: list[Record]) -> dict:
        """type -> sorted tuple of the types that (almost) always move with it by the same displacement
        (the parts of one multi-colour sprite). Symmetric closure is left to the canonical-member rule
        in fit_moves, so each sprite yields one MoveRule per button, not one per part."""
        moved: Counter = Counter()
        together: Counter = Counter()
        for rec in recs:
            if not rec.tr.action.is_button:
                continue
            ms = [(k, dy, dx) for k, dy, dx in rec.tr.moves if (dy, dx) != (0, 0)]
            for k, dy, dx in ms:
                moved[k] += 1
                for k2, dy2, dx2 in ms:
                    if k2 != k and (dy2, dx2) == (dy, dx):
                        together[(k, k2)] += 1
        out = {}
        for k, n in moved.items():
            ps = tuple(sorted(k2 for (k1, k2), m in together.items()
                              if k1 == k and m >= self.cfg.min_support and m >= self.cfg.min_precision * n
                              and m >= self.cfg.min_precision * moved[k2]))
            if ps:
                out[k] = ps
        return out

    def fit_moves(self, recs: list[Record]) -> list[MoveRule]:
        disp: dict = defaultdict(Counter)
        for rec in recs:
            a = rec.tr.action
            if not a.is_button:
                continue
            for key, dy, dx in rec.tr.moves:
                disp[(a.name, key)][(dy, dx)] += 1
        fate = any(rec.rc.fate is not None for rec in recs)
        groups = {} if fate else self.co_movers(recs)
        riders = self.fate_riders(recs) if fate else set()
        out = []
        for (name, tkey), cnt in disp.items():
            (dy, dx), n = cnt.most_common(1)[0]
            if n < self.cfg.min_support or (dy, dx) == (0, 0):
                continue
            group = FATE if fate else groups.get(tkey, ())
            if fate and tkey in riders:
                continue                          # a part that rides on the controlled sprite: its rule covers it
            if not fate and group and min((tkey,) + group) != tkey:
                continue                          # one rule per sprite: only its canonical part fits it
            blockers, passable = set(), set()
            for rec in recs:
                if rec.tr.action.name != name:
                    continue
                mover = _mover(rec.rc, tkey)
                if mover is None:
                    continue
                parts = sprite_parts(rec.rc, mover, group)
                if parts is None:
                    continue
                la = group_look_ahead(rec.rc.scene, parts, (dy, dx))
                if la[0] == "edge" or len(la) < 2:
                    continue
                moved = any(k == tkey and (ddy, ddx) == (dy, dx) for k, ddy, ddx in rec.tr.moves)
                (passable if moved else blockers).add(la[1])
            amb = blockers & passable                 # sometimes through, sometimes not: leave silent
            out.append(MoveRule(name, tkey, dx, dy, frozenset(blockers - amb), frozenset(passable - amb), True,
                                group))
        return out

    @staticmethod
    def fate_riders(recs: list[Record]) -> set:
        """HDC fate mode: types that, on most button steps where the controlled sprite is known, are common-fate
        partners of it (the second colour of a two-colour sprite). They get no MoveRule of their own; the
        controlled type's FATE rule moves them. A box carried only now and then stays a type of its own."""
        part: Counter = Counter()
        seen: Counter = Counter()
        for rec in recs:
            if rec.rc.agent is None or not rec.tr.action.is_button:
                continue
            ids = set((rec.rc.fate or {}).get(rec.rc.agent.id, ()))
            for c in rec.rc.scene.objects():
                if c.type_key == rec.rc.agent_type:
                    continue
                seen[c.type_key] += 1
                part[c.type_key] += int(c.id in ids)
        return {k for k, n in part.items() if n >= 0.5 * seen[k] and n >= 2}

    def fit_pads(self, moves: list[MoveRule]) -> list[PadMoveRule]:
        """Merge the MoveRules of one sprite (two or more buttons) into one d-pad rule. Wall evidence is
        pooled: a colour that blocked any arrow and never let any arrow through is a wall."""
        by: dict = defaultdict(list)
        for m in moves:
            by[(m.type_key, m.group)].append(m)
        out = []
        for (tk, group), ms in by.items():
            if len(ms) < 2:
                continue
            blk = frozenset().union(*(m.blockers for m in ms))
            pas = frozenset().union(*(m.passable for m in ms))
            amb = blk & pas
            mv = tuple(sorted((m.action, m.dx, m.dy) for m in ms))
            out.append(PadMoveRule(tk, mv, blk - amb, pas - amb, True, group))
        return out

    def fit_toggles(self, recs: list[Record]) -> list[ClickToggleRule]:
        hit: Counter = Counter()
        tried: Counter = Counter()
        for rec in recs:
            a, c = rec.tr.action, rec.rc.clicked
            if not a.is_click or c is None or rec.tr.post is None:
                continue
            tried[(c.shape, c.colour)] += 1
            pc = rec.tr.post.comp_at(a.row, a.col)
            if pc is not None and pc.colour != c.colour and pc.shape == c.shape and (pc.y0, pc.x0) == (c.y0, c.x0):
                hit[(c.shape, c.colour, pc.colour)] += 1
        return [ClickToggleRule(s, a, b) for (s, a, b), n in hit.items()
                if n >= self.cfg.min_support and n >= 0.5 * tried[(s, a)]]

    def fit_noops(self, recs: list[Record], counter_parts: set) -> list[NoOpRule]:
        quiet: Counter = Counter()
        total: Counter = Counter()
        for rec in recs:
            k = action_key(rec.rc)
            total[k] += 1
            quiet[k] += int(set(rec.tr.parts()) <= counter_parts)
        return [NoOpRule(k) for k, n in quiet.items()
                if n >= self.cfg.min_support and n >= self.cfg.min_precision * total[k]]

    def fit_counters(self, recs: list[Record]) -> list[CounterRule]:
        out = []
        for scope in SCOPES:
            pos: dict = defaultdict(list)          # part -> [(level, index within level and scope)]
            idx: Counter = Counter()
            for rec in recs:
                if scope not in scopes_of(rec.tr.action):
                    continue
                lvl = rec.tr.level
                for p in set(rec.tr.parts()):
                    pos[p].append((lvl, idx[lvl]))
                idx[lvl] += 1
            groups: dict = defaultdict(list)      # identical occurrence lists tick together
            for p, occ in pos.items():
                groups[tuple(occ)].append(p)
            for occ, parts in groups.items():
                gaps = [b[1] - a[1] for a, b in zip(occ, occ[1:]) if a[0] == b[0]]
                if len(gaps) < self.cfg.min_support:
                    continue
                period, n = Counter(gaps).most_common(1)[0]
                if period >= 2 and n >= self.cfg.counter_purity * len(gaps):
                    out.append(CounterRule(tuple(sorted(parts)), period, scope))
        return out

    def fit_persist(self, recs: list[Record]) -> list[PersistRule]:
        out = []
        for scope in ("last", "last_same"):
            trans: dict = defaultdict(Counter)
            repeats = total = 0
            for rec in recs:
                prev = rec.rc.last_label if scope == "last" else rec.rc.last_same
                if prev is None or prev in ("reset", "level_clear", "game_over", "start"):
                    continue
                trans[prev][rec.label] += 1
                total += 1
                repeats += int(prev == rec.label)
            if total and repeats >= self.cfg.min_support and repeats >= 0.5 * total:
                out.append(PersistRule(scope, None, None))
            mapping = []
            for prev, nxt in sorted(trans.items()):
                lab, n = nxt.most_common(1)[0]
                if n >= self.cfg.min_support and n >= self.cfg.persist_purity * sum(nxt.values()):
                    mapping.append((prev, lab))
            if mapping and any(a != b for a, b in mapping):
                out.append(PersistRule(scope, tuple(mapping), None))
        return out

    def fit_contacts(self, recs: list[Record], moves: list[MoveRule], counter_parts: set) -> list[ContactRule]:
        tally: Counter = Counter()
        extras: dict = {}
        for mr in moves:
            for rec in recs:
                if rec.tr.action.name != mr.action:
                    continue
                mover = _mover(rec.rc, mr.type_key)
                if mover is None:
                    continue
                la = ag.look_ahead(rec.rc.scene.comps, mover, (mr.dy, mr.dx))
                if la[0] not in ("obj", "wall"):
                    continue
                y = la[1]
                parts = rec.tr.parts()
                n_mv = sum(p.startswith("mv") for p in parts)
                other = [p for p in parts if not p.startswith("mv") and p not in counter_parts]
                conv = [p for p in parts if p.startswith(f"rc{y}>")]
                if "van" in parts and n_mv >= 1:
                    op, to = "collect", None
                    other = [p for p in other if p != "van"]
                elif n_mv >= 2:
                    op, to = "push", None
                elif conv:
                    op, to = "convert", int(conv[0].split(">")[1])
                    other = [p for p in other if p != conv[0]]
                elif n_mv == 0 and other:
                    op, to = "stop", None
                else:
                    continue                          # plain move or plain block: MoveRule's business
                k = (mr.action, mr.type_key, mr.dx, mr.dy, y, op, to)
                tally[k] += 1
                prev = extras.get(k)
                extras[k] = Counter(other) if prev is None else (prev & Counter(other))
        out = []
        for k, n in tally.items():
            if n < self.cfg.min_support:
                continue
            extra = tuple(sorted(extras[k].elements())) if k[5] == "stop" else ()
            out.append(ContactRule(k[0], k[1], k[2], k[3], k[4], k[5], k[6], extra))
        return out


# ---------------------------------------------------------------- composing rule sets

class RuleSetBuilder:
    """Beam search over rule sets by the posterior's own score (-DL + replayed log likelihood)."""

    def __init__(self, beam: int = 4, max_rounds: int = 10):
        self.beam, self.max_rounds = beam, max_rounds

    def build(self, candidates: list[Rule], records: list[Record], cache: PredictionCache,
              price: Callable[[RuleSet], float], seeds: Iterable[RuleSet] = ()) -> list[RuleSet]:
        """price: prior cost of a rule set in nats (BeliefState.price: dl_weight x description length)."""
        scores: dict = {}

        def score(rs: RuleSet) -> float:
            k = rs.key()
            if k not in scores:
                ll, _, _ = score_ruleset(rs, records, cache)
                scores[k] = -price(rs) + ll
            return scores[k]

        pool = {rs.key(): rs for rs in list(seeds) + [RuleSet.empty()]}
        beam = sorted(pool.values(), key=score, reverse=True)[: self.beam]
        for _ in range(self.max_rounds):
            grown = dict((rs.key(), rs) for rs in beam)
            for rs in beam:
                have = {r.key() for r in rs.rules()}
                for r in candidates:
                    if r.key() not in have:
                        nxt = rs.with_rule(r)
                        grown.setdefault(nxt.key(), nxt)
            new_beam = sorted(grown.values(), key=score, reverse=True)[: self.beam]
            if [rs.key() for rs in new_beam] == [rs.key() for rs in beam]:
                break
            beam = new_beam
        return beam


class HypothesisProposer:
    """Fitter + model-written rules (stub provider) + beam composition, seeded by survivors."""

    def __init__(self, fitter: Optional[TemplateFitter] = None, builder: Optional[RuleSetBuilder] = None,
                 provider: Optional[RuleProvider] = None):
        self.fitter = fitter or TemplateFitter()
        self.builder = builder or RuleSetBuilder()
        self.provider = provider or StubLLMRuleProvider()
        self.tl = None                      # tl.bridge.TLSource (AgentConfig.use_tl)
        self.templates = True               # False: the template fitter is off (tensor-logic rules only)

    def propose(self, beliefs, summary: str = "") -> list[RuleSet]:
        """beliefs: beliefs.BeliefState. Returns candidate rule sets (not yet added)."""
        cands = self.fitter.propose(beliefs.records) if self.templates else []
        if self.tl is not None:
            cands += self.tl.propose()
        cands += list(self.provider.propose(summary))
        seeds = [h.ruleset for h in beliefs.hyps]
        return self.builder.build(cands, beliefs.records, beliefs.cache, beliefs.price, seeds)

# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Bayesian beliefs over rule sets for the rule discovery prototype (OpenMind, #arc-3,
#   23-Sep-2026 21:03 ET). In active-inference terms this is the learned transition model B, held as
#   a posterior over discrete structures (rule sets) rather than one parameter table.
#     - BackoffModel: the chained back-off count model of round seven (round7.Model, chain=True):
#       key levels (handcolour context) -> (handcolour context, previous label), backing off to the
#       play's pooled outcome distribution, open vocabulary. It predicts every step, shared by all
#       hypotheses, so an event no rule explains costs its back-off probability instead of zeroing the
#       hypothesis (round seven: the previous-outcome key only helps under the chain).
#     - Hypothesis: a RuleSet + description length (MDL prior exp(-DL)) + prequential log likelihood
#       + a KT-estimated miss rate eps. Predictive: when the rule set speaks,
#       p(o) = (1 - eps) [o = predicted] + eps p_backoff(o); when silent, p(o) = p_backoff(o).
#       Only non-terminal, non-reset steps score rule sets (clears / game overs belong to goals.py).
#     - BeliefState: posterior over hypotheses (softmax of -DL + loglik), per-step update, surprise
#       (-ln p under the posterior mixture), Bayesian surprise (KL between posteriors over rule sets
#       before and after the step), the Dirichlet novelty model's own KL, late entry of new hypotheses
#       by exact replay over the stored history (the back-off's per-step predictive is stored, so a
#       rule set proposed at step t is scored on steps 0..t exactly as if it had been there; the MDL
#       prior pays for having been fitted on those steps), Bayesian model reduction (drop a rule when
#       the reduced set has a higher posterior; exact here because the history is replayable) and
#       pruning to top K.
#     - NoveltyModel: Dirichlet counts per handcolour context with the yardstick's back-off prior
#       (heldout_yardstick.TypePriorBeliefs); novelty = efe_trace_analysis.eig (information gain about
#       the parameters, the book's "novelty"), plus the closed-form Dirichlet BMR test of whether a
#       context needs its own distribution at all.
#     - SurpriseMonitor: running mean / spread of surprisal; a spike triggers re-proposal and replanning.
#   Integration: agent.py calls observe(rc, transition) once per step BEFORE the ContextBuilder is
#   advanced (prequential); hypotheses.py scores candidate sets with score_ruleset; policy.py reads
#   predictions(rc) for candidate actions. Not run yet: only py_compile was used.
# SRP/DRY check: Pass -- chain back-off = round7.Model, Dirichlet with back-off prior =
#   heldout_yardstick.TypePriorBeliefs, EIG / Dirichlet KL = efe_trace_analysis. New: the mixture of
#   rule-set experts over the shared back-off, replay scoring, BMR over rules, surprise monitor.
"""Posterior over rule sets: MDL prior, prequential likelihood with chain back-off, BMR, surprise."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from scipy.special import gammaln

from ._distill import chain_model, efe, hy, oe
from .perception import Scene, Transition, label_parts
from .rules import DLContext, Prediction, Rule, RuleContext, RuleSet, dl_context_for

NOVEL = oe.NOVEL
UNREADABLE = "<unreadable>"          # an observed label equal to NOVEL (missing board) is renamed
# How a rule set's prediction is scored against the observed outcome label (23-Sep-2026, after the
# first evaluation): "label" = the predicted label must equal the whole observed label (original);
# "parts" = a rule predicts only its own event parts; the back-off count model supplies the rest
# (side effects such as floor residue or a second mover). Set per process (offline_eval sets it from
# AgentConfig.likelihood inside each worker).
LIKELIHOOD = "parts"
COMPOSE_C = 0.1                      # pseudo-mass on the bare predicted label when the back-off has
                                     # little or no mass on labels containing the predicted parts


# ---------------------------------------------------------------- distributions

def prob(dist: dict, o: str) -> float:
    """p(o) under a label distribution whose NOVEL key holds the mass of every unlisted label."""
    return dist.get(o, dist[NOVEL])


def mix_predictive(pred_label: str, eps: float, pb: dict) -> dict:
    """(1 - eps) on the predicted label + eps x back-off. A predicted label outside the back-off's
    vocabulary takes half of the unseen slot's eps-share, so the result still sums to one."""
    out = {o: eps * p for o, p in pb.items()}
    if pred_label in out:
        out[pred_label] += 1.0 - eps
    else:
        half = out[NOVEL] / 2.0
        out[NOVEL] = half
        out[pred_label] = (1.0 - eps) + half
    return out


def entropy(dist: dict) -> float:
    return -sum(p * math.log(p) for p in dist.values() if p > 0)


def mixture(dists: list[dict], weights: list[float]) -> dict:
    """Weighted average; labels absent from a distribution count as zero there (its NOVEL key keeps
    the unseen mass separately), which keeps each summand normalised."""
    out: dict = {}
    for w, d in zip(weights, dists):
        for o, p in d.items():
            out[o] = out.get(o, 0.0) + w * p
    return out


def kl_categorical(p: list[float], q: list[float]) -> float:
    return sum(a * math.log(a / b) for a, b in zip(p, q) if a > 0 and b > 0)


from functools import lru_cache


@lru_cache(maxsize=None)
def _parts_counter(label: str) -> tuple:
    """Cached multiset of a label's event parts as sorted (part, count) pairs."""
    c = {}
    for x in label_parts(label):
        c[x] = c.get(x, 0) + 1
    return tuple(sorted(c.items()))


@lru_cache(maxsize=None)
def _contains(label: str, pred_label: str) -> bool:
    """True if the parts of pred_label are a sub-multiset of the parts of label (cached)."""
    have = dict(_parts_counter(label))
    return all(have.get(x, 0) >= n for x, n in _parts_counter(pred_label))


def _sub_multiset(a: list, b: list) -> bool:
    ca = {}
    for x in a:
        ca[x] = ca.get(x, 0) + 1
    for x in b:
        if x in ca:
            ca[x] -= 1
    return all(v <= 0 for v in ca.values())


def compose_predictive(pred_label: str, eps: float, pb: dict) -> dict:
    """Part-level likelihood. The rule asserts its predicted event parts occur; the back-off count
    model, conditioned on labels that contain those parts, supplies the side effects:
        p(o) = eps * pb(o) + (1 - eps) * [pb(o) * 1(parts(pred) <= parts(o)) + c * 1(o unseen)] / (Z + c)
    with Z the back-off mass on consistent labels (the c-share goes to the NOVEL slot). A prediction without parts ("nothing") falls back
    to exact-label scoring. Sums to one over the same support as mix_predictive."""
    if not _parts_counter(pred_label):
        return mix_predictive(pred_label, eps, pb)
    cons = {o: p for o, p in pb.items() if o != NOVEL and _contains(o, pred_label)}
    denom = sum(cons.values()) + COMPOSE_C
    out = {o: eps * p for o, p in pb.items()}
    for o, p in cons.items():
        out[o] += (1.0 - eps) * p / denom
    # The c-share is "a label containing the predicted parts that the back-off has not seen yet". It goes
    # to the unseen slot. (Fix, 23-Sep-2026 23:20 ET: it used to go to the bare predicted label and took
    # half of the unseen slot with it, so a CORRECT rule scored worse than the counts whenever the real
    # outcome was new, e.g. a Locksmith move with its first-seen side effects.)
    out[NOVEL] += (1.0 - eps) * COMPOSE_C / denom
    return out


def rule_missed(pred_label: str, label: str) -> bool:
    """Miss for the rule's own track record: whole-label mismatch ("label"), or the predicted parts
    not all present in the observed outcome ("parts"; exact match for part-less predictions)."""
    if LIKELIHOOD == "label":
        return pred_label != label
    if not _parts_counter(pred_label):
        return pred_label != label
    return not _contains(label, pred_label)


def kt_eps(misses: int, fires: int) -> float:
    """Krichevsky-Trofimov estimate of the miss rate (prequential, never 0 or 1)."""
    return (misses + 0.5) / (fires + 1.0)


# ---------------------------------------------------------------- shared count models

class BackoffModel:
    """round7.Model(chain=True) keyed by (handcolour ctx) -> (handcolour ctx, previous label)."""

    def __init__(self, vocab0: Optional[list[str]] = None):
        self.model = chain_model(list(vocab0 or efe.BASE_OUTCOMES))

    @staticmethod
    def levels(rc: RuleContext) -> tuple:
        return (("hc", rc.hc_ctx), ("hcl", rc.hc_ctx, rc.last_label or "start"))

    def dist(self, rc: RuleContext) -> dict:
        key = self.levels(rc)
        out = {o: self.model.p(key, o) for o in self.model.vocab}
        out[NOVEL] = self.model.p(key, NOVEL)          # NOVEL is never in the vocabulary
        return out

    def update(self, rc: RuleContext, label: str) -> None:
        self.model.update(self.levels(rc), label)

    @property
    def vocab_size(self) -> int:
        return len(self.model.vocab)


def dirichlet_bmr(post: list[float], prior: list[float], reduced_prior: list[float]) -> float:
    """Closed-form Bayesian model reduction for a Dirichlet-categorical (Friston's BMR):
    log evidence of the reduced model minus the full one, given the full posterior.
    ln B(a) = sum ln G(a_k) - ln G(sum a_k); a' = post + reduced_prior - prior.
    Positive -> the reduced prior explains the counts at least as well (prune the extra structure)."""
    def ln_b(a):
        return sum(float(gammaln(x)) for x in a) - float(gammaln(sum(a)))
    red_post = [p + r - q for p, r, q in zip(post, reduced_prior, prior)]
    if min(red_post) <= 0:
        return -math.inf
    return ln_b(red_post) - ln_b(reduced_prior) - (ln_b(post) - ln_b(prior))


class NoveltyModel:
    """Dirichlet per handcolour context with the yardstick's back-off prior (parameter learning).
    novelty(ctx) = expected information gain about that context's outcome distribution."""

    def __init__(self, beta: float = efe.BACKOFF_BETA):
        self.b = hy.TypePriorBeliefs([], beta, None)
        self.visits: dict = {}

    def novelty(self, hc_ctx: tuple) -> float:
        return efe.eig(self.b.alpha(hc_ctx))

    def update(self, hc_ctx: tuple, label: str) -> float:
        self.visits[hc_ctx] = self.visits.get(hc_ctx, 0) + 1
        return self.b.update(hc_ctx, label)

    def split_evidence(self, hc_ctx: tuple, concentration: float = 50.0) -> float:
        """BMR: does this context need its own outcome distribution? Compares the fitted context
        with a reduced prior concentrated on the play's pooled distribution. >0 = merge it."""
        prior = self.b.base()
        post = self.b.alpha(hc_ctx)
        z = sum(prior)
        reduced = [concentration * p / z for p in prior]
        return dirichlet_bmr(post, prior, reduced)


# ---------------------------------------------------------------- hypotheses

@dataclass
class Hypothesis:
    ruleset: RuleSet
    dl: float
    loglik: float = 0.0
    fires: int = 0
    misses: int = 0
    origin: str = "fit"

    @property
    def eps(self) -> float:
        return kt_eps(self.misses, self.fires)

    @property
    def log_score(self) -> float:
        """Unnormalised log posterior: MDL prior + prequential log likelihood."""
        return -self.dl + self.loglik

    def dist(self, pred: Optional[Prediction], pb: dict) -> dict:
        if pred is None:
            return pb
        if LIKELIHOOD == "label":
            return mix_predictive(pred.label, self.eps, pb)
        return compose_predictive(pred.label, self.eps, pb)

    def absorb(self, pred: Optional[Prediction], pb: dict, label: str) -> float:
        """Score one step prequentially, then update the miss-rate counts. Returns ln p."""
        lp = math.log(max(prob(self.dist(pred, pb), label), 1e-300))
        self.loglik += lp
        if pred is not None:
            self.fires += 1
            self.misses += int(rule_missed(pred.label, label))
        return lp


@dataclass
class Record:
    """One stored step for replay: the context before the outcome, the transition, the back-off
    predictive at that time, and a serial number for the prediction cache."""
    serial: int
    rc: RuleContext
    tr: Transition
    label: str
    pb: dict


class PredictionCache:
    """(rule key, record serial) -> rule output. Rules are deterministic in their context, so a
    rule is evaluated once per stored step however many rule sets contain it."""

    def __init__(self):
        self.d: dict = {}

    def contrib(self, serial: int, rc: RuleContext) -> Callable[[Rule], Optional[list]]:
        def f(rule: Rule):
            k = (rule.key(), serial)
            if k not in self.d:
                self.d[k] = rule.predict(rc)
            return self.d[k]
        return f

    def forget_before(self, serial: int) -> None:
        self.d = {k: v for k, v in self.d.items() if k[1] >= serial}


def score_ruleset(rs: RuleSet, records: list[Record], cache: PredictionCache) -> tuple[float, int, int]:
    """Exact prequential replay of one rule set over stored steps: (log likelihood, fires, misses)."""
    h = Hypothesis(rs, 0.0)
    for rec in records:
        if not rec.tr.scored:
            continue
        pred = rs.predict(rec.rc, cache.contrib(rec.serial, rec.rc))
        h.absorb(pred, rec.pb, rec.label)
    return h.loglik, h.fires, h.misses


# ---------------------------------------------------------------- surprise

@dataclass
class StepSurprise:
    label: str
    predicted: Optional[str]             # MAP hypothesis's predicted label (None = silent)
    surprisal: float                     # -ln p(label) under the posterior mixture
    backoff_surprisal: float             # -ln p(label) under the back-off alone (the round-seven reference)
    bayes_surprise: float                # KL(posterior after || before) over rule sets
    dirichlet_kl: float                  # novelty model's Bayesian surprise for this context
    posterior_entropy: float
    spike: bool


class SurpriseMonitor:
    """Exponentially weighted mean / variance of surprisal; spike = well above the running level."""

    def __init__(self, rate: float = 0.1, k: float = 2.5, min_nats: float = 2.0, warmup: int = 5):
        self.rate, self.k, self.min_nats, self.warmup = rate, k, min_nats, warmup
        self.mean, self.var, self.n = 0.0, 1.0, 0

    def push(self, s: float) -> bool:
        spike = self.n >= self.warmup and s > max(self.min_nats, self.mean + self.k * math.sqrt(self.var))
        d = s - self.mean
        self.mean += self.rate * d
        self.var = (1 - self.rate) * (self.var + self.rate * d * d)
        self.n += 1
        return spike


# ---------------------------------------------------------------- the belief state

class BeliefState:
    """Posterior over rule sets for one play (carried across levels: the slow timescale)."""

    def __init__(self, max_hypotheses: int = 8, max_records: int = 600, min_weight: float = 1e-4,
                 vocab0: Optional[list[str]] = None, dl_weight: float = 1.0):
        """vocab0: starting outcome support of the back-off (default: the base outcomes only, open
        vocabulary; offline_eval passes the training fold's labels, as round seven did).
        dl_weight: temperature on the MDL prior (1 = plain two-part MDL). The chained back-off is a
        strong prequential competitor and a rule of ~20 bits needs many steps to pay for itself
        within one play, so this is a knob to select on training folds (offline_eval grid)."""
        self.max_hypotheses, self.max_records, self.min_weight = max_hypotheses, max_records, min_weight
        self.dl_weight = dl_weight
        self.backoff = BackoffModel(vocab0)
        self.novelty = NoveltyModel()
        self.cache = PredictionCache()
        self.records: list[Record] = []
        self.monitor = SurpriseMonitor()
        self.serial = 0
        self.dlc = DLContext()
        self.hyps: list[Hypothesis] = [Hypothesis(RuleSet.empty(), self.price(RuleSet.empty()), origin="empty")]

    # -- posterior
    def price(self, rs: RuleSet) -> float:
        """Prior cost of a rule set in nats: dl_weight x description length."""
        return self.dl_weight * rs.description_length(self.dlc)

    def refresh_dl(self, scene: Optional[Scene]) -> None:
        self.dlc = dl_context_for(scene, self.backoff.vocab_size)
        for h in self.hyps:
            h.dl = self.price(h.ruleset)

    def weights(self) -> list[float]:
        s = [h.log_score for h in self.hyps]
        m = max(s)
        e = [math.exp(v - m) for v in s]
        z = sum(e)
        return [v / z for v in e]

    def posterior_entropy(self) -> float:
        return -sum(w * math.log(w) for w in self.weights() if w > 0)

    def map_hypothesis(self) -> Hypothesis:
        return max(self.hyps, key=lambda h: h.log_score)

    # -- prediction
    def predictions(self, rc: RuleContext) -> list[tuple[Hypothesis, float, Optional[Prediction], dict]]:
        """Per hypothesis: (hypothesis, weight, prediction or None, predictive distribution)."""
        pb = self.backoff.dist(rc)
        out = []
        for h, w in zip(self.hyps, self.weights()):
            pred = h.ruleset.predict(rc)
            out.append((h, w, pred, h.dist(pred, pb)))
        return out

    def predictive(self, rc: RuleContext) -> dict:
        ps = self.predictions(rc)
        return mixture([d for _, _, _, d in ps], [w for _, w, _, _ in ps])

    # -- update
    def observe(self, rc: RuleContext, tr: Transition) -> StepSurprise:
        """Score the step prequentially, update every hypothesis, the back-off and the novelty
        counts, and store the step for replay. Call BEFORE advancing the ContextBuilder."""
        self.refresh_dl(rc.scene)
        label = UNREADABLE if tr.label == NOVEL else tr.label
        pb = self.backoff.dist(rc)
        w_old = self.weights()
        serial = self.serial
        self.serial += 1
        map_pred = None
        if tr.scored:
            contrib = self.cache.contrib(serial, rc)
            preds = [h.ruleset.predict(rc, contrib) for h in self.hyps]
            p_mix = sum(w * prob(h.dist(pr, pb), label) for h, w, pr in zip(self.hyps, w_old, preds))
            i_map = max(range(len(self.hyps)), key=lambda i: self.hyps[i].log_score)
            map_pred = preds[i_map].label if preds[i_map] is not None else None
            for h, pr in zip(self.hyps, preds):
                h.absorb(pr, pb, label)
        else:
            p_mix = prob(pb, label)
        w_new = self.weights()
        dir_kl = 0.0
        if not tr.reset:
            dir_kl = self.novelty.update(rc.hc_ctx, label)
            self.backoff.update(rc, label)
        elif rc.action.name == "RESET":
            # a chosen RESET: count it in the novelty table so its epistemic value decays (the back-off
            # is left alone, so offline replay scores are unchanged)
            dir_kl = self.novelty.update(rc.hc_ctx, label)
        self.records.append(Record(serial, rc, tr, label, pb))
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
            self.cache.forget_before(self.records[0].serial)
        s = -math.log(max(p_mix, 1e-300))
        return StepSurprise(label, map_pred, s, -math.log(max(prob(pb, label), 1e-300)),
                            kl_categorical(w_new, w_old), dir_kl, self.posterior_entropy(),
                            self.monitor.push(s))

    # -- structure: add, reduce, prune
    def add_rulesets(self, rulesets: list[RuleSet], origin: str = "fit") -> int:
        """Score new rule sets by exact replay and add them. Returns how many were new."""
        have = {h.ruleset.key() for h in self.hyps}
        n = 0
        for rs in rulesets:
            if rs.key() in have:
                continue
            have.add(rs.key())
            ll, fires, misses = score_ruleset(rs, self.records, self.cache)
            self.hyps.append(Hypothesis(rs, self.price(rs), ll, fires, misses, origin))
            n += 1
        return n

    def _scored(self, rs: RuleSet, origin: str) -> Hypothesis:
        ll, fires, misses = score_ruleset(rs, self.records, self.cache)
        return Hypothesis(rs, self.price(rs), ll, fires, misses, origin)

    def reduce(self, max_passes: int = 3) -> None:
        """Bayesian model reduction over rules: replace a hypothesis by its best one-rule-smaller
        version while that raises the posterior; then dedupe and prune to the top K (the counts-only
        hypothesis is always kept as the reference)."""
        out = []
        for h in self.hyps:
            cur = h
            for _ in range(max_passes):
                best = None
                for r in cur.ruleset.rules():
                    red = self._scored(cur.ruleset.without(r), cur.origin + "-bmr")
                    if red.log_score >= cur.log_score and (best is None or red.log_score > best.log_score):
                        best = red
                if best is None:
                    break
                cur = best
            out.append(cur)
        seen, uniq = set(), []
        for h in sorted(out, key=lambda h: -h.log_score):
            if h.ruleset.key() not in seen:
                seen.add(h.ruleset.key())
                uniq.append(h)
        self.hyps = uniq
        self.prune()

    def prune(self) -> None:
        empty_key = RuleSet.empty().key()
        self.hyps.sort(key=lambda h: -h.log_score)
        w = self.weights()
        keep = [h for h, wi in zip(self.hyps, w) if wi >= self.min_weight][: self.max_hypotheses]
        if not any(h.ruleset.key() == empty_key for h in keep):
            keep.append(next((h for h in self.hyps if h.ruleset.key() == empty_key),
                             self._scored(RuleSet.empty(), "empty")))
        self.hyps = keep

    # -- summaries
    def top(self, k: int = 3) -> list[tuple[Hypothesis, float]]:
        pairs = sorted(zip(self.hyps, self.weights()), key=lambda t: -t[1])
        return pairs[:k]

    def scored_records(self) -> list[Record]:
        return [r for r in self.records if r.tr.scored]


@dataclass
class PlayScore:
    """Accumulated prequential nats for one play (offline_eval)."""
    nats_mix: float = 0.0
    nats_backoff: float = 0.0
    steps: int = 0
    surprisals: list = field(default_factory=list)

    def add(self, s: StepSurprise) -> None:
        self.nats_mix += s.surprisal
        self.nats_backoff += s.backoff_surprisal
        self.steps += 1
        self.surprisals.append(s.surprisal)

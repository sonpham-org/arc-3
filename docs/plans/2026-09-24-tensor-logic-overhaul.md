# Tensor-logic overhaul of the rule-discovery agent (plan, 24-Sep-2026)

Asked by OpenMind (#arc-3), items 1-6 of Bubba's proposal approved. Helper: Claude Opus 5.5 (Bubba).
Code: ~/GitHub/arc-3/ARC3-Inference/rulediscovery1__fepInspired/tl/ (new) + small hooks.
Backup: ../backupsOldVersions/rulediscovery1__fepInspired_6e55c3332208. No commits. No LLM at runtime.

## Design
- tl/engine.py: sparse Boolean relations (named indices), natural join on shared indices, projection
  (sum / any), elementwise nonlinearity with temperature (T=0 step, T>0 sigmoid(x/T)), forward chaining to
  fixpoint; multilinear tensor equations `L[n,e] = sum data[n,e,i..] * P1[i] * P2[j] ...` with one sparse data
  factor and dense parameter factors; gradient of each parameter = the same equation with that factor
  removed (a tensor equation itself); softmax cross-entropy; Adam + L1 proximal step (description length).
- tl/relations.py: per step, over the perceived objects of the pre board: Colour(o,c), Type(o,k), Ctl(o),
  Group(o,o') (common fate), Ahead(o,move e,c) (colours in the strip o's group would enter by e's
  displacement; edge = colour 16), Contact(o) / On(o) (the controlled sprite runs into / stands on o),
  Clicked(o), Hist(o,tau,e') (o's own effect tau steps ago), Tape(s,e) (controlled sprite's move in the
  previous run at run-clock minus s), Action(a). Per-object effect targets from the tracker (labels, never
  engine internals): none / mv(dy,dx) / van / rc>c / grow / shrink / reshape; a "world" row for app.
- tl/learner.py: bank of join shapes feeding one softmax over effects per object:
  A own x action, B ahead (move index shared with the head), P self-relation x colour x action (pushed,
  collected, clicked), K linked object (relation of o' x colour(o') x colour(o)) = switch->door,
  H own lag with learned soft lag (softmax over tau) = persistence / counters, G previous-run tape with a
  learned soft lag = the ghost. Starts with A+B; others switched on when their zero-weight gradient on
  recent / surprising steps is large (surprise-driven structure = backward chaining).
  Export: threshold + round weights (T=0) into TLRule (a rules.Rule, one per action, plus one modifier for
  action-free lag clauses); per-rule temperature T = T0 / (1 + support / n0) makes rare rules analogical
  (type literal matched by similarity: same colour or same shape counts partly), well-supported rules exact.
  DL = literal + weight code lengths, so beliefs.py's MDL posterior judges them next to the templates.
- tl/plan.py: reachability as forward chaining (fixpoint of Reach[p+d_a] <- Reach[p], Free[p+d_a]) with
  Free from a correlation of the sprite mask with the wall map; replaces explore.search in TL arms.
- Switches (AgentConfig): use_tl, tl_templates (False = templates off), tl_plan. Default = old behaviour,
  verified action for action.
- game_sweep arms: touch_tl (templates + TL), tl_only (TL only, TL mover for the explorer).

## Stages
S1 engine + relations + tests. S2 offline on a0 recorded plays (replayed through GameEnv, labels only for
scoring): rules rediscovered, nats on all / first-contact steps vs templates. S3 live sweep, 9 games x
3 arms x 10 seeds x 500 actions, tag tl_slippery7. Report results/tl/report.md(+json), NOTE, analysis doc,
provenance event.

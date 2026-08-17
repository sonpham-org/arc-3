# taaf-plain-checkpoint8

- Base: exact author-shared plain TAAF (`ARC3-Inference` aa69123 dirty
  snapshot, `tufa-arc-agi-framework` fe9f7c4).
- Single change: at most eight real environment actions are executed from one
  `action(...)` request.
- On checkpoint, TAAF returns the settled board, the eight-action limit, the
  unexecuted suffix, and an instruction to re-ground before reusing it.
- No ffa7gn, no-impact guard, state graph, animation memory, failed-prefix
  guard, hypothesis lease, plan reset, or prompt replacement is included.

This is the inverse of the earlier combined experiment: cap-8 is grafted onto
TAAF's code and interaction loop.

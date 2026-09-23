# Fresh-context independent game agents

Required by Son Pham on 14 September 2026, to reduce repetition between games.

Every game improvement gets a new agent started with `fork_turns="none"`.
Do not reuse an author across different games or pass the parent conversation.
Supply only that game's frozen baseline, candidate file locations, shared
rubric and technical constraints, and its own sampled mechanic candidates.
The shared rules are instructions, not examples of other games' designs.

Authors do not read other games, pair reports, other agents' messages,
solutions, reviews, shared summaries, or each other's work. They write to
disjoint candidate files. No agent-to-agent messages are allowed. The parent
coordinates file ownership and runtime issues without forwarding design ideas.
This is prompt and workflow isolation in a shared workspace, not an operating
system access-control boundary. Record the supplied prompt, agent task name,
context setting, allowed inputs, and files changed for audit.

Once both independent improvements are frozen, start a separate fresh-context
comparison agent. That agent may inspect both candidates and apply the twelve
distance dimensions. Its combined comparison stays with the coordinator.
Any necessary repair request goes to a new author with only its own game's
specific deficiency and constraints. Do not pass the other author's solution.

After final changes, start fresh QC reviewers, also with `fork_turns="none"`.
They do not see author discussions, reviewer scores, exact winning sequences,
or each other's opinions. For the novice play test, reveal only the normal
game and ordinary player controls. Only after the cold test is recorded may
the reviewer read the two English descriptions and inspect rules for accuracy.
Two reviewers score independently before results are compared. Use the
highest of the four description scores and retain any disagreement.

A reviewer who has seen a solution or authored a repair cannot be the fresh
novice tester for that revision. After a source change, use new reviewers and
new timed sessions. Preserve failed attempts and do not silently reset scores
or elapsed time. Infrastructure failures may be retried in a new session, with
both records retained and the reason stated.

The coordinator alone checks the whole pool for repetition after independent
design. New seeds follow the same isolated-author rule; the coordinator audits
their closest prior games, meaningful novelty, and structural similarity.

Simulation is recorded as simulation. Only actual human observations permit
`human_confirmed`. Independence is never a substitute for game qualification.

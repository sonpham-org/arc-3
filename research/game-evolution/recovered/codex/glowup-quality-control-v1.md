# Quality Control: simple English and first-level playability

Approved by Son Pham for the QC batch and restarted loop, 14 September 2026.
Fresh independent agents must follow `glowup-agent-isolation-v1.md`.
The user's subsequent recovery feedback is required by `glowup-recovery-policy-v1.md`:
prefer forgiving exploration; terminal loss is optional, and retained loss must be
clear and recoverable. Apply it to the unfinished batch and future candidates.

**Position in the loop**

Select two seeds → glow up both → pull them apart across the 12 dimensions → **Quality Control on each game** → final qualification → activate both versions and record the cycle.

QC is a separate gate. High fidelity or pair-distance scores cannot compensate for confusing rules or an unreadable first level. Both games must pass the screening criteria below. A QC repair that changes either game must be followed by another distance check and another QC check on the resulting versions.

**1. Explain the game honestly, then score it**

Write two short descriptions from the actual implemented game:

- **Mechanics:** what the player controls, what actions change, the goal, failure and recovery, and any important rules introduced later. Use ordinary words and describe causes and effects. Cover real complexity rather than hiding it.
- **How to play Level 1:** what to look for, how to act, how to recognize progress and a win, and how to retry. Aim for at most five short sentences, roughly 100 words. This is an explanation of the rules, not the exact winning move sequence.

Use concrete verbs such as move, click, turn, connect, stop, and reveal. Describe visible objects consistently. Remove lore, marketing language, invented mechanic names, undefined technical terms, and long chains of conditions. A new idea may need a new word, but define it in an ordinary sentence. Brevity alone is not a pass: a short but false or incomplete explanation fails.

Score each description on the user's scale: **0 = simple English; 1 = slop**. These are reasoned judgments, not measured probabilities or an automatic reading-age metric.

| Score anchor | Meaning |
|---|---|
| 0.00 | Direct, accurate everyday English. A novice can say what to do and why. |
| 0.25 | Mostly clear, but a term, rule, or causal link needs explanation. |
| 0.50 | Repeated reading is needed; several rules or exceptions are difficult to connect. |
| 0.75 | Jargon and abstraction make the actions or goal hard to identify. |
| 1.00 | The description does not give a usable, coherent account of how the game works. |

Keep the first draft and its scores. Have two fresh reviewers, representing people with basic technical English and no game-specific knowledge, judge independently. Each must identify confusing sentences and paraphrase what the player does, what happens, and what wins. For each reviewer, keep both description scores. The game's English-slop score is the **highest of those four scores**, so a clear tutorial cannot conceal an incomprehensible overall mechanic summary.

**Language gate: final score ≤ 0.20**, with no missing or misleading rule. Reviewers must check that the words match the running game after their initial independent reading.

**2. Rewrite, then change the game if needed**

Try to explain the same real mechanics in simpler English and score the revised descriptions again. Allow at most two wording-only revisions before diagnosing the game design. If an accurate simple explanation still fails, change the game itself: remove unnecessary exceptions, make actions consistent, simplify the goal, improve visible feedback, or defer rules to later levels.

Do not merely rename complex mechanics or omit inconvenient details. If the screen is already confusing, repair it immediately rather than waiting for two rewrites. Keep the interesting idea and later depth, but give Level 1 a small, clear task with safe exploration and obvious consequences.

**3. Test whether someone can start from the screen**

Use a fresh novice tester who has not seen the source code, design notes, summary, solution, or previous playthrough. They see the normal game screen and the controls ordinarily available to a player. The simple-English explanations are QC records; they cannot serve as a hidden walkthrough for this test.

First-level targets:

- Make a meaningful action within 60 seconds without author coaching.
- Complete Level 1 within five minutes, allowing exploration and restarts.
- Explain in simple English what that action changed and why the level ended in a win. A lucky sequence alone does not establish understanding.
- Recognize feedback and find the retry action without source-code knowledge, precise motor tricks, or a long manual.
- Deliberately explore plausible wrong actions and explain their consequences. Test
  harmless blocked/empty actions, any visible lives or budgets, and retry without
  losing completed levels, following `glowup-recovery-policy-v1.md`.

Record actions, time, restarts, requests for help, and specific points of confusion. Failure triggers changes to controls, rules, layout, cues, or Level 1 itself, followed by a fresh test. Do not solve a readability problem by giving away the solution.

The existing Level 2+ random-resistance requirement remains. Level 1 is allowed to be an easy introduction. Later levels can deepen the idea through clearly introduced rules and compositions.

**4. Be explicit about human evidence**

Automatic screening can use independent simulated novice reviewers, but they must interact with the visible game and ordinary controls for the play test. Reading code or following a verifier's winning trace does not count. Record the tester type for every result.

- `fail`: language or first-level criteria failed. Repair before activation.
- `provisional_pass`: all screening criteria passed using simulated testers; actual human playability is still unconfirmed.
- `human_confirmed`: the screening criteria passed and a real first-time player with basic technical English completed the cold-start test.

For the automatic loop, a provisional pass permits ordinary machine qualification and candidate activation, with that status displayed honestly in the cycle report. It never becomes a claim of human validation. A real human failure reopens QC even if a simulation or an earlier version passed. Confidence that the games work for humans must ultimately come from actual play observations.

**5. Recheck and record the final result**

After any QC game change, repeat the 12-dimension comparison, necessary mechanic checks, language review, and first-level test. Then run the existing final qualification checks on the exact versions being activated. If simplicity and distance cannot both pass, leave the cycle unfinished or revert it; do not weaken QC to preserve a distance score.

Every cycle report must include, separately for each game:

- Exact tested game version and source hash.
- Initial and final mechanics and how-to-play descriptions.
- Independent before/after scores, explanations, and final maximum score.
- Game changes made because the explanation or first level was confusing.
- Cold-start evidence: tester type, time to first meaningful action, time to win, restarts, help needed, and the tester's explanation of the rule.
- QC status, remaining uncertainty, and the final pair-distance and qualification results.
- Recovery-policy audit, including retained/removed loss conditions, exact tested
  player mode, exploratory action evidence, visible feedback and checkpoint behavior.

QC is added prospectively. Previous games and cycles do not acquire a QC pass retroactively. When the loop restarts, each selected game's new candidate goes through this step before activation.

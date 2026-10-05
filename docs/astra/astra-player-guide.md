# Astra's player guide: all 25 games, level by level

**5 October 2026 · Codex's reconstruction of the published GPT-6 Astra notes**  
**183 levels reviewed. Astra's account first; comparison with Boss's human guide is still pending.**

Boss, this is what the winning player's published notes can actually teach us at each level. It is **not 183 complete winning recipes**: many notes leave the solution unexplained. Those gaps are highlighted below, including on levels the player won.

Every game here uses its **max-effort provider-adapter** replay. All 25 session records report 100 and every level completed. There are **759 published summaries across 6,485 actions**. The notes are intermittent summaries, not a complete record of the player's reasoning. A note saying “continue the plan” does not show us the plan; it also does not establish that no thinking happened.

## Interesting gaps to inspect first

| Game and level | What makes it useful to inspect | Published steps |
|---|---|---|
| [G50T, level 6](#g50t) | **Plan missing:** 13 notes largely defer to an earlier plan, without teaching the solution. | 202–246 |
| [LF52, levels 4, 8, 9](#lf52) | **Notes without a solution:** seven, three, and sixteen notes respectively, mostly next actions and references to an earlier plan. | 112–146; 515–537; 560–662 |
| [CN04, level 5](#cn04) | **Failed idea, unclear correction:** joining the pieces into one branching structure did not win. The replacement connection rule is still uncertain. | 108, 154 |
| [BP35, level 6](#bp35) | **Rules reconsidered mid-level:** gravity switches and the goal location are questioned without a clear final explanation. | 176, 183, 200, 206 |
| [SK48, level 8](#sk48) | **Possible target mismatch:** the desired pair and the later reported pair differ. The notes do not explain whether the plan changed or the shorthand is wrong. | 293, 306 |
| [SB26, levels 2–8](#sb26) | **The opening guess never becomes a lesson:** level 3 has no summary; the others mostly name actions without explaining the choice. | See each level below |

These are failures of the **published explanation**, not findings that the game was lost or that the player cheated. A useful partial plan can still help a human experiment; it is not automatically a trustworthy training explanation.

## Reading the guide

Each row says what the notes actually provide, then identifies the missing explanation. Proposed tactics remain proposals. The labels mean:

- **No notes:** no written summary was published during the level.
- **Plan missing:** notes exist, but mainly announce actions or refer to a plan they do not explain.
- **Rule missing:** a needed control or game rule is not taught.
- **Untested idea:** the explanation is presented as a guess without a clear confirming result.
- **Correction unresolved:** an earlier idea is questioned, contradicted, or revised without a settled replacement.
- **Partial plan:** there is a useful tactic or route fragment, but not a complete explanation of the level.

The classifications are a reading judgment, not a mechanical proof. “Solution explained” would require enough stated controls, rules, and a connected plan for a new player to reproduce the solution without inventing a missing rule. None of these entries meets that strict standard; the rows retain the useful pieces rather than treating them all as equally empty.

**Level boundaries were checked against the recording.** A winning action belongs to the level it finishes; its note is not assigned to the next level simply because the resulting board has changed. Step numbers identify actions in the recording, not animation frames. Each game's replay link is above its table. The [source index](astra-player-guide-sources.json) contains all summary steps, the exact game builds, action ranges, and level-clear steps.

Color words in these notes can disagree with the board. The [6 September audit in ARC Explainer](https://github.com/82deutschmark/arc-explainer/blob/main/docs/astra/reasoning-trace-audit.md) already documented that problem. Descriptions here use shape, position, or function where possible. No missing game rules have been filled in from Boss's guide. This is not a blind test: some human notes and engine behavior had been seen earlier in the conversation; the claims here must stand on the published passages.

### Coverage

| Explanation gap | Levels |
|---|---:|
| No notes | 7 |
| Plan missing | 30 |
| Rule missing | 15 |
| Untested idea | 55 |
| Correction unresolved | 11 |
| Partial plan | 65 |

The levels with no published summary at all are **CD82 level 3, FT09 level 2, RE86 level 1, SB26 level 3, SU15 level 7, TR87 level 2, TR87 level 4**.

### Jump to a game

[AR25](#ar25) · [BP35](#bp35) · [CD82](#cd82) · [CN04](#cn04) · [DC22](#dc22) · [FT09](#ft09) · [G50T](#g50t) · [KA59](#ka59) · [LF52](#lf52) · [LP85](#lp85) · [LS20](#ls20) · [M0R0](#m0r0) · [R11L](#r11l) · [RE86](#re86) · [S5I5](#s5i5) · [SB26](#sb26) · [SC25](#sc25) · [SK48](#sk48) · [SP80](#sp80) · [SU15](#su15) · [TN36](#tn36) · [TR87](#tr87) · [TU93](#tu93) · [VC33](#vc33) · [WA30](#wa30)

## AR25

[Winning max-effort replay](https://arcprize.org/replay/ed09362c-eb47-41b8-bf46-2d275090be02) · 8 levels · 18 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Move the source sideways; its partner moves oppositely. | **Untested idea:** The target rule is still guessed. | 1, 2 |
| 2 | Click the hollow source to select it, then adjust its position. | **Rule missing:** Movement controls are not explained. | 16, 18 |
| 3 | Test moving the mirror upward to align both sources. | **Untested idea:** Reflection and success rules are unconfirmed. | 27 |
| 4 | Only a next click is announced. | **Plan missing:** No level plan is explained. | 81 |
| 5 | Adjust one source vertically, perhaps also moving the mirror. | **Untested idea:** Independent reflections remain a guess. | 89, 99 |
| 6 | Place shapes opposite one another, then shift the second source left and down. | **Partial plan:** The complete alignment rule is missing. | 117, 151, 161 |
| 7 | Shift one source right and up; select another to avoid overlap. | **Partial plan:** The full target arrangement is unexplained. | 170, 192 |
| 8 | Move a shape down toward the center. | **Plan missing:** Its purpose and the final arrangement are missing. | 207 |

## BP35

[Winning max-effort replay](https://arcprize.org/replay/b02b9920-372b-43c9-8eef-58b76704664f) · 9 levels · 74 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Try removing blocks after several unrelated opening guesses. | **Untested idea:** Movement and block rules are missing. | 1, 2, 8 |
| 2 | Remove blocks along the passage, then open the block above. | **Rule missing:** Clicks are listed without teaching their effects. | 40, 42, 50 |
| 3 | Reach the goal through a shaft with apparently restricted blocks. | **Untested idea:** The new block rules remain guesses. | 56, 82, 84 |
| 4 | Change blocks remotely and use a fall to approach the goal. | **Untested idea:** Click range and gravity remain unclear. | 96, 103, 108, 112 |
| 5 | A few leftward positions and a click are listed. | **Plan missing:** The existing plan is never taught. | 121, 123, 124, 137 |
| 6 | Flip gravity under a safe ceiling, then find a return route. | **Correction unresolved:** Later notes question switches and the goal; no settled correction. | 163, 176, 183, 200, 206, 225 |
| 7 | Open a neighboring block and fall onto a safe surface. | **Partial plan:** The full safe route is missing. | 249, 279 |
| 8 | Create a stopping surface before changing height. | **Rule missing:** The special block's effect is not taught. | 303, 333 |
| 9 | Create safe stops and use gravity changes between passages. | **Partial plan:** Block effects and the complete route remain unclear. | 384, 386, 387, 394, 404, 424 |

## CD82

[Winning max-effort replay](https://arcprize.org/replay/f4cac4df-b688-49e1-8cef-02935d9ef885) · 6 levels · 12 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Bring paint and paper together, then perhaps turn the painted shape. | **Untested idea:** The painting controls are guesses. | 1, 2, 8 |
| 2 | Only the next action is discussed. | **Plan missing:** No level plan is explained. | 19 |
| 3 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 4 | Only the next action is discussed. | **Plan missing:** No level plan is explained. | 49 |
| 5 | Fill positions in southwest, south, then southeast order. | **Partial plan:** What moves and how it paints are unclear. | 56, 65 |
| 6 | Paint one section before stamping another, to avoid overwriting earlier work. | **Partial plan:** Stamping controls and the complete target are missing. | 69, 78 |

## CN04

[Winning max-effort replay](https://arcprize.org/replay/f6296e32-d4b0-4068-9bb0-3be64b8afef5) · 6 levels · 20 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Select a piece and bring its endpoint toward another connector. | **Untested idea:** Touching versus overlapping is unresolved. | 2, 4, 6 |
| 2 | Move one piece upward; rotate another clockwise three times. | **Partial plan:** The final connected arrangement is not explained. | 21, 31 |
| 3 | Rotate a loose piece and compare its outline with the target. | **Untested idea:** The attachment and silhouette rules are guesses. | 46, 56 |
| 4 | Find open ends; move a piece down before left to avoid overlap. | **Partial plan:** Valid connections are not defined. | 67, 72 |
| 5 | Joining everything into a branching shape failed; try changing a piece's orientation and overlap. | **Correction unresolved:** The corrected winning rule is never established. | 108, 115, 154 |
| 6 | Click a handle to change a wire gap, then reposition a piece. | **Untested idea:** Handle behavior and the complete arrangement remain unclear. | 187, 204 |

## DC22

[Winning max-effort replay](https://arcprize.org/replay/eb980b49-c92d-4fdd-b5a0-ff2aa8254cb9) · 6 levels · 31 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | The opening guesses that pushers or blowers direct objects toward bins. | **Untested idea:** No machinery rule is established. | 1 |
| 2 | Activate a lower bridge route, then walk upward and sideways. | **Partial plan:** The control-to-bridge link is uncertain. | 25, 26, 45, 56 |
| 3 | Use portals between separated areas, then continue walking. | **Untested idea:** How portals activate is guessed. | 68, 93, 102 |
| 4 | Map platforms; test whether a boot-like control crosses a gap. | **Rule missing:** The crossing controls are missing. | 113, 118, 119, 122 |
| 5 | Activate a bridge; later place a solid platform across a gap. | **Partial plan:** The platform controls and complete route are unclear. | 177, 179, 256 |
| 6 | Combine portals, a rotating crossing, and a robot-like mechanism. | **Untested idea:** The notes never settle their effects or timing. | 297, 323, 382, 384 |

## FT09

[Winning max-effort replay](https://arcprize.org/replay/31df82b6-0491-45fc-abbd-c8ed5310d8c9) · 6 levels · 9 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Change corner-grid cells to match or encode the middle pattern. | **Untested idea:** The relationship is guessed. | 1 |
| 2 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 3 | The next clicks and a changed value are noted. | **Plan missing:** No method for choosing them is taught. | 12, 22 |
| 4 | Only the next click is announced. | **Plan missing:** No level plan is explained. | 30 |
| 5 | Change a cell toward the target value, then align related cells. | **Untested idea:** The click-to-value rule is not established. | 50 |
| 6 | Adjust several cells, then restore a top cell affected by the changes. | **Partial plan:** The complete target and affected-cell rule are missing. | 63, 67, 68 |

## G50T

[Winning max-effort replay](https://arcprize.org/replay/b93ce848-16a9-4930-994b-871dd64ed93d) · 7 levels · 77 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Reach the exit past an opening gate. | **Rule missing:** The essential ghost-creation rule is never taught. | 1, 5, 6, 12, 18 |
| 2 | Time separate trips so a ghost opens the gate when needed. | **Partial plan:** Recording and replay controls are missing. | 22, 25, 49 |
| 3 | Count the route and ghost positions to time the gate crossing. | **Untested idea:** Whether ghosts stay at endpoints is still questioned. | 62, 92, 108, 115 |
| 4 | Coordinate around a switch that may transport whoever stands inside a marked area. | **Untested idea:** The transport trigger is a guess. | 134, 138, 144 |
| 5 | Track the player and two ghosts so switches line up with gate crossings. | **Partial plan:** The full setup is missing. | 150, 161, 175, 177, 185, 191 |
| 6 | All 13 notes largely say to continue an earlier plan. | **Plan missing:** No usable solution is explained. | 202, 210, 214, 216, 218, 220, 222, 224, 228, 234, 240, 244, 246 |
| 7 | Check a few positions, then follow an earlier plan. | **Plan missing:** The final ghost-and-gate strategy is missing. | 251, 258, 268, 274, 290 |

## KA59

[Winning max-effort replay](https://arcprize.org/replay/a20bebda-f97c-4a72-940f-de03dae1833b) · 7 levels · 26 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Try pushing one body through a special floor strip with another. | **Untested idea:** Selection, pushing, and sliding are guesses. | 9, 10, 16 |
| 2 | Only continuing play and a next action are discussed. | **Plan missing:** No level plan is explained. | 56 |
| 3 | Approach offset goals from below; perhaps match bodies to holes. | **Partial plan:** Matching and the full route are unconfirmed. | 70, 87 |
| 4 | Move down before crossing, because a crate blocks the later downward route. | **Partial plan:** Only this local detour is explained. | 114 |
| 5 | Try a directional action as a kick, then reposition another body. | **Untested idea:** The kick effect is unconfirmed. | 151, 158 |
| 6 | Approach from above and kick left to align a body near a wall. | **Partial plan:** Kick distance and stopping behavior are unknown. | 165, 177, 185 |
| 7 | Send the wide body to the middle goal and the tall body below; kick early to avoid backtracking. | **Partial plan:** Selection and kick rules remain incomplete. | 210, 259 |

## LF52

[Winning max-effort replay](https://arcprize.org/replay/248b7fbd-5f82-40bd-af6d-ff811283526a) · 10 levels · 91 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Select a peg, then its landing spot; jump until one remains. | **Partial plan:** The full jump order is missing. | 1, 2, 3, 4 |
| 2 | Portal guesses give way to mentions of a moving ferry. | **Rule missing:** How to load and drive it is missing. | 11, 16, 25, 32, 48 |
| 3 | Combine jumps with ferry movement and docking. | **Untested idea:** Which ferries move together remains uncertain. | 65, 66, 68, 95 |
| 4 | All seven notes follow an earlier action sequence. | **Plan missing:** No level solution is explained. | 112, 120, 127, 137, 139, 141, 146 |
| 5 | Park one ferry aside; use another to help a jump. | **Correction unresolved:** Questioned routes never become a settled rule. | 160, 193, 195, 196, 197 |
| 6 | Board a ferry and carry pieces into further captures. | **Partial plan:** The special ferry's rules are missing. | 279, 292, 315 |
| 7 | Carry a peg into successive jumps; coordinate ferries sharing the arrows. | **Partial plan:** The full route is missing. | 340, 390, 421, 475 |
| 8 | All three notes follow an earlier sequence. | **Plan missing:** No level solution is explained. | 515, 524, 537 |
| 9 | Sixteen notes mostly track actions and refer to an earlier plan. | **Plan missing:** No level solution is explained. | 560, 582, 595, 609, 646, 658, 662 |
| 10 | Reselect for a jump; shift two ferries while keeping another at the boundary. | **Partial plan:** Only local adjustments are explained. | 682, 705 |

## LP85

[Winning max-effort replay](https://arcprize.org/replay/ced68d8b-8d12-486a-adaf-cb49c1e646e7) · 8 levels · 16 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Try shifting beads around a loop; plan several reverse turns. | **Untested idea:** The initial goal guesses are unresolved. | 1, 2, 4 |
| 2 | Test one clockwise turn at the upper-right control. | **Untested idea:** Its effect and the target are unconfirmed. | 9 |
| 3 | A reverse shift behaves as predicted; plan three more shifts toward the target. | **Partial plan:** The remaining solution is not described. | 17, 18 |
| 4 | Move a bead along intersecting horizontal and vertical tracks. | **Untested idea:** Movement order at crossings is guessed. | 33, 34 |
| 5 | Shift an upper track toward its target, then adjust another track. | **Partial plan:** The full button sequence is unclear. | 47, 51 |
| 6 | Map bead groups around star-like crossings; consider a reverse turn. | **Rule missing:** Which beads move together is unresolved. | 57, 67 |
| 7 | Test whether arrows move coupled groups in restricted directions. | **Untested idea:** The one-way and coupling rules are guesses. | 76, 77 |
| 8 | Trace diagonal bead loops and their shared positions. | **Partial plan:** The path map and solution remain unfinished. | 90 |

## LS20

[Winning max-effort replay](https://arcprize.org/replay/c836fd19-5a16-4ca0-8d3f-afd48c73073e) · 7 levels · 36 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Match the shape's orientation; take the upper route around a wall. | **Partial plan:** The changing station's effect is guessed. | 1, 3 |
| 2 | Visit a refill station before making further shape changes and returning. | **Untested idea:** The full route and station rules are missing. | 17, 34, 37, 40 |
| 3 | With little energy left, move down toward the identified goal. | **Partial plan:** The matching rule is not explained. | 104 |
| 4 | Leave a station, move right, then push upward. | **Plan missing:** The objects and purpose are unspecified. | 122 |
| 5 | Reconsider whether a station rotates the shape or replaces it. | **Correction unresolved:** The revised station rule is not established. | 153, 174, 184 |
| 6 | After a moving-shape collision, detour downward around a wall. | **Partial plan:** The collision's purpose and full route are unclear. | 247, 290 |
| 7 | Budget energy for a short route toward the lower-right area. | **Correction unresolved:** The cost estimates disagree. | 303, 304, 328, 329 |

## M0R0

[Winning max-effort replay](https://arcprize.org/replay/37443746-b7f8-4d5c-9140-b623f00cabe7) · 6 levels · 23 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Test whether the two movers travel in mirrored directions and should meet. | **Rule missing:** Both rules are initial guesses. | 1, 2, 5 |
| 2 | Approach from another row to avoid a suspected hazard. | **Untested idea:** It may hurt or merely block; unresolved. | 18 |
| 3 | Hold one mover against a wall while moving the other, then bring them together. | **Partial plan:** Blocks and checkpoints remain unexplained. | 41, 48, 55, 80 |
| 4 | Move a blocker into a side passage to help align the movers. | **Untested idea:** The blocker control and crossing are unconfirmed. | 105, 106 |
| 5 | Move inward to meet while navigating closed gates. | **Rule missing:** How gates open and whether they harm you are unclear. | 134, 149, 154, 155, 165 |
| 6 | Use floor plates to open gates; consider leaving boxes on them. | **Untested idea:** These are proposed tactics, not demonstrated rules. | 170, 175 |

## R11L

[Winning max-effort replay](https://arcprize.org/replay/932837ac-8800-414f-9d7c-46537ebea3a3) · 6 levels · 24 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Guide a pole through a passage; test clicking near the exit. | **Rule missing:** What clicking moves is unknown. | 1, 2, 3 |
| 2 | Choose a diagonal endpoint whose connecting path stays clear. | **Partial plan:** The line's interaction with objects is missing. | 7, 10 |
| 3 | Move the ball along a clear horizontal lane, then select another point. | **Partial plan:** Selection, collisions, and the goal remain unclear. | 40, 41 |
| 4 | Use an intermediate point before aiming farther across. | **Untested idea:** The obstruction and movement rule are unconfirmed. | 60, 61 |
| 5 | Move toward a free endpoint while staying within the board. | **Partial plan:** The endpoint's role is not explained. | 75, 78 |
| 6 | Select a source, question its position, then click another point. | **Plan missing:** No connection to a solution is given. | 94, 95, 96 |

## RE86

[Winning max-effort replay](https://arcprize.org/replay/d7c629e9-5f79-4225-8344-53131c1c5dbc) · 8 levels · 49 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 2 | Move a diamond left and up, keeping its tip clear of another shape. | **Partial plan:** Matching and overlap rules are missing. | 35 |
| 3 | Reconsider whether shape centers, sizes, or overlaps determine a match. | **Correction unresolved:** No settled rule follows. | 57 |
| 4 | Shift selected shapes down and left toward target positions. | **Partial plan:** The notes do not connect the fragments. | 105, 118 |
| 5 | Keep a diamond inside the board and adjust shapes toward targets. | **Untested idea:** Whether matching requires color is untested. | 148, 168, 188, 199 |
| 6 | Fit a tall rectangle; test whether obstacle contact changes a shape's dimensions. | **Untested idea:** The transformation remains a hypothesis. | 211, 215, 238, 251 |
| 7 | Arrange a rectangle and cross around an obstacle. | **Partial plan:** Shape-changing controls and the final arrangement are missing. | 299, 304, 347, 361, 364, 367 |
| 8 | Flatten and shift a rectangle, then correct an edge after a collision. | **Correction unresolved:** Dimensions and correction remain unresolved. | 391, 399, 443, 449, 518, 537 |

## S5I5

[Winning max-effort replay](https://arcprize.org/replay/7609fe46-64be-4d12-b100-81733da7c768) · 8 levels · 23 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Try extending bars toward end marks by clicking an anchor. | **Untested idea:** The click effect is guessed. | 1 |
| 2 | Route one bar above a wall and another down the far side. | **Partial plan:** Extension controls and endpoint requirements are missing. | 14 |
| 3 | Adjust endpoints in small increments beside walls. | **Partial plan:** The intended finished shape is not explained. | 50, 54, 57, 67 |
| 4 | Consider combining nearby pieces and adding more. | **Untested idea:** The merging idea is untested. | 78, 84 |
| 5 | Choose a path beside the fixed wall instead of risking a collision. | **Partial plan:** The route's start and finish are missing. | 120, 125 |
| 6 | Extend an endpoint and turn the base to fit wall gaps. | **Untested idea:** Turning controls and fit remain unconfirmed. | 135, 141, 144 |
| 7 | Pass below the main wall, then turn upward on its far side. | **Partial plan:** Collision and turning rules remain unclear. | 160, 163, 185, 186, 196 |
| 8 | Shorten the beam before adjusting the next one to fit the walls. | **Partial plan:** The complete endpoint arrangement is missing. | 218, 230, 241 |

## SB26

[Winning max-effort replay](https://arcprize.org/replay/7eebd5e4-fac6-47c7-b829-4ca32cc491e2) · 8 levels · 13 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Choose from the bottom palette to make dots match hollow targets. | **Untested idea:** The opening rule is only guessed. | 1 |
| 2 | Only next actions are discussed. | **Plan missing:** No level solution is explained. | 12, 24 |
| 3 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 4 | Only the next click is discussed. | **Plan missing:** No level solution is explained. | 50 |
| 5 | Only next clicks are discussed. | **Plan missing:** No level solution is explained. | 57, 65 |
| 6 | Only next clicks are discussed. | **Plan missing:** No level solution is explained. | 76, 84, 88 |
| 7 | Only the next click is discussed. | **Plan missing:** No level solution is explained. | 91 |
| 8 | Only next clicks are discussed. | **Plan missing:** No level solution is explained. | 118, 122 |

## SC25

[Winning max-effort replay](https://arcprize.org/replay/2e83cea2-946f-4f51-9ce5-d7ca5c8576f3) · 6 levels · 22 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Shrink the player; the notes report that the size change worked. | **Partial plan:** The target and growth controls are missing. | 3, 10, 13 |
| 2 | Pass a gate while small, then grow afterward. | **Untested idea:** The gate's effect is guessed. | 18 |
| 3 | A vague pattern choice and next actions are mentioned. | **Plan missing:** No level solution is explained. | 25, 28 |
| 4 | Shrink for a narrow corridor, line up with a distant switch, and consider firing. | **Partial plan:** Shot size and range are uncertain. | 38, 40, 45, 49 |
| 5 | Move left before up to line up a shot with less repositioning. | **Untested idea:** The target's hit requirements are missing. | 69 |
| 6 | Choose growth controls, then follow a short route through waypoints. | **Partial plan:** Why those settings solve the level is unexplained. | 112, 126 |

## SK48

[Winning max-effort replay](https://arcprize.org/replay/ec8d80f4-250f-47c4-948f-6e5d51379cb5) · 8 levels · 32 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Push pieces left, then move up and right to collect another. | **Untested idea:** Rod and attachment rules are uncertain. | 5, 13 |
| 2 | Avoid trapping pieces at a wall; retract the rod before moving up. | **Partial plan:** How retraction affects pieces is missing. | 30, 37, 42 |
| 3 | Free the rod from a pin, then move the collected pieces upward. | **Partial plan:** The final arrangement is unclear. | 75, 76 |
| 4 | Leave selected pieces pinned while withdrawing the rod and repositioning others. | **Partial plan:** Release and selection rules are incomplete. | 90, 94, 99, 105 |
| 5 | Carry pieces above an obstacle, then reposition them to reach another. | **Partial plan:** The pickup order and collisions remain uncertain. | 114, 117 |
| 6 | Route the horizontal rod below an obstacle so the upright rod can collect from above. | **Partial plan:** The full sequence is unconfirmed. | 175 |
| 7 | Make a cross with matching outer pairs and a shared middle piece. | **Partial plan:** The complete construction is missing. | 243, 273 |
| 8 | Rearrange pieces between rods, then retract one rod. | **Correction unresolved:** The desired and reported pairs differ; no explanation resolves this. | 293, 306 |

## SP80

[Winning max-effort replay](https://arcprize.org/replay/553aa4ea-9177-4bf2-b9bc-fb59d237cf89) · 6 levels · 12 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Align a bar with openings to guide falling streams into cups. | **Untested idea:** Object behavior and bar controls are uncertain. | 1, 4 |
| 2 | Move right twice as previously planned. | **Plan missing:** The purpose is not explained. | 6, 8 |
| 3 | Only the next action is discussed. | **Plan missing:** No level plan is explained. | 15 |
| 4 | Test whether a vertical control changes the bar's length. | **Untested idea:** No outcome or route is explained. | 25 |
| 5 | Use a reported upward turn at a blockage when arranging the deflector and branches. | **Partial plan:** Controls and the full route are missing. | 96, 109 |
| 6 | Plan a crossing beside a bar without overlap. | **Untested idea:** The clearance rule is only guessed. | 113 |

## SU15

[Winning max-effort replay](https://arcprize.org/replay/2e3994e1-8760-4e47-89f3-7ec096fce420) · 9 levels · 28 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Guess that a mirror and beam reach the target. | **Untested idea:** The proposed controls are unconfirmed. | 1, 2, 3 |
| 2 | Bring nearby pieces together around a ring. | **Untested idea:** The merging distance and ring effect are guessed. | 10, 11, 13 |
| 3 | Combine pieces into requested amounts, then deliver them. | **Partial plan:** The combination recipe and delivery rule are missing. | 21, 28, 29, 32 |
| 4 | Only the next click is discussed. | **Plan missing:** No level plan is explained. | 43 |
| 5 | Lure a hazard aside while gathering pieces elsewhere. | **Partial plan:** Hazard response and safe distances are unconfirmed. | 46, 50, 53, 57, 59 |
| 6 | Guide a square toward its goal while accounting for triangles. | **Untested idea:** The proposed movement and mass rules remain speculative. | 69, 73, 76, 78, 83, 85 |
| 7 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 8 | Consider pairing separated pieces and aiming toward the lower-right target. | **Untested idea:** Range and pairing are unresolved. | 92, 97 |
| 9 | Join pieces on the left while pulling another group downward. | **Partial plan:** Target amounts and the complete sequence are missing. | 99, 106 |

## TN36

[Winning max-effort replay](https://arcprize.org/replay/6f5dd73e-fdf4-4b30-a87a-22e4557d8189) · 7 levels · 11 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Set switches to route the top piece downward to its destination. | **Rule missing:** The switch code is missing. | 1, 3 |
| 2 | Set more command slots on a larger board. | **Rule missing:** No usable settings or route are provided. | 11 |
| 3 | Inspect a demonstration to distinguish forward, reverse, and turn commands. | **Untested idea:** Those meanings remain guesses. | 21 |
| 4 | The note mentions shrinking left, without explaining it. | **Plan missing:** No usable level plan. | 37 |
| 5 | Watch a demonstration's sequence of turns to infer the command. | **Untested idea:** How that observation solves the board is missing. | 47, 48 |
| 6 | Open a demonstration to inspect the board. | **Plan missing:** The demonstration's lesson is never described. | 65 |
| 7 | Change individual command slots and toggles. | **Rule missing:** The notes never teach how to choose the settings. | 91, 117, 124 |

## TR87

[Winning max-effort replay](https://arcprize.org/replay/5c144b64-fd15-4913-bdc4-28feac5046ee) · 6 levels · 11 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Compare patterns after quarter-turns and cycle through candidate choices. | **Untested idea:** The matching rule is not established. | 1, 7, 9, 15 |
| 2 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 3 | Consider a repeating pattern sequence and move between candidate indices. | **Untested idea:** Why the sequence applies is missing. | 52, 56 |
| 4 | No written summary was published for this level. | **No notes:** No explanation to inspect. | None |
| 5 | Test whether a pair of patterns changes together. | **Untested idea:** The grouped-change effect is unconfirmed. | 102 |
| 6 | Match one rotated pattern, then check the remaining pairs. | **Partial plan:** The later choices and complete rule are missing. | 115, 122, 127, 134 |

## TU93

[Winning max-effort replay](https://arcprize.org/replay/7c54faff-3875-43f3-8a06-ca25720b32c8) · 9 levels · 45 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Map connected passages and follow a written sequence of turns. | **Partial plan:** The route is not explained from start to finish. | 1, 2, 7, 14 |
| 2 | Try approaching a guard from its side or behind. | **Untested idea:** Attack and guard behavior are unconfirmed. | 20, 25, 28 |
| 3 | Detour around the guards and flank one from above and beside it. | **Partial plan:** The encounter rule is uncertain. | 29, 34 |
| 4 | Move upward, deal with a target on the left, then turn toward the goal. | **Partial plan:** The target interaction is unexplained. | 55, 63, 66 |
| 5 | Wait before taking a route past a possible trigger. | **Untested idea:** What triggers the danger is unknown. | 73, 77, 93 |
| 6 | Move down to the next safe spot, then continue an earlier route. | **Partial plan:** Later directions lack enough context. | 107, 116 |
| 7 | Enter carefully to control when a stationary enemy starts chasing. | **Untested idea:** Sight and chase rules remain guesses. | 127, 130 |
| 8 | Track patrol positions and issue next moves. | **Plan missing:** No usable route is taught. | 140, 142, 155, 156 |
| 9 | Consider a side approach to intercept a patrol and save a loop. | **Partial plan:** The shortcut is explicitly unproven. | 165, 182, 183, 185 |

## VC33

[Winning max-effort replay](https://arcprize.org/replay/150eaeb5-32e2-4c96-88ea-40b38638b375) · 7 levels · 24 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Try aligning a marker with a slider or boundary. | **Rule missing:** The control explanations conflict. | 1, 3, 4, 5, 8, 11, 13, 15 |
| 2 | Adjust neighboring bands while keeping enough in the middle. | **Correction unresolved:** The proposed minimum conflicts with the calculation. | 18, 19, 22 |
| 3 | Transfer along neighboring chambers in a planned order. | **Partial plan:** Transfer direction and target checks are unconfirmed. | 25, 36 |
| 4 | Test whether a valve moves contents through tunnels. | **Rule missing:** Even what the moving parts represent is uncertain. | 48, 49, 53 |
| 5 | After a fill limit blocks the plan, transfer from C to D instead. | **Correction unresolved:** The correction never becomes a full solution. | 94, 111, 115 |
| 6 | Pump from A to C through the identified connection. | **Partial plan:** Target levels and later transfers are missing. | 133 |
| 7 | Only the next action is discussed. | **Plan missing:** No level plan is explained. | 184 |

## WA30

[Winning max-effort replay](https://arcprize.org/replay/49ac7afb-b83a-46f4-bb1e-3ecc902ca291) · 9 levels · 32 summaries

| Level | What the published notes provide | Highlighted explanation gap | Evidence steps |
|---:|---|---|---|
| 1 | Turn while carrying a box to move it toward a target. | **Untested idea:** Carrying and target rules are missing. | 1, 2, 8, 12 |
| 2 | Use a helper to collect and deliver boxes around blocked routes. | **Partial plan:** Helper instructions are not explained. | 27, 32, 49, 51, 71 |
| 3 | Hand off a box; move away to avoid grabbing it again. | **Untested idea:** Barrier and handoff rules remain uncertain. | 80, 86, 89, 99, 128 |
| 4 | Route two boxes around barriers toward separate delivery spots. | **Partial plan:** Helper behavior and the complete routes are unconfirmed. | 150, 157, 183 |
| 5 | Avoid another character and a box while approaching delivery and pickup positions. | **Partial plan:** The fragments never form a complete route. | 195, 200, 260, 286 |
| 6 | Go farther down before crossing after the first route is blocked. | **Correction unresolved:** The revised route remains unresolved. | 296, 298, 320 |
| 7 | A free box and next actions are mentioned. | **Plan missing:** No useful level plan is explained. | 369, 378 |
| 8 | Take the only open direction; separately plan to intercept a thief. | **Partial plan:** The thief's behavior and full route are missing. | 386, 441, 451 |
| 9 | Plan another delivery while watching a nearby thief. | **Partial plan:** The moves never form a complete final-level plan. | 497, 502 |

## The separate LF52 replay with 13 summaries

The [13-summary replay](https://arcprize.org/replay/310cd2d3-2af5-4da5-8c83-0d9c41911a5a) uses **medium** effort. It is not the max replay above, which has 91 summaries.

Those 13 notes offer clues about peg jumps and later carts, but not a ten-level manual. **There is no published summary between steps 29 and 253:** that covers the rest of level 2 and all of levels 3–5. A human watching the moves could reconstruct more, but that would be learning from the behavior, beyond what those written notes explain.

## What changed since the September investigation

The [6 September audit](https://github.com/82deutschmark/arc-explainer/blob/main/docs/astra/reasoning-trace-audit.md) read three games and identified misleading colors and references to earlier summaries. The [5 September token-spend note](trace-audit-token-spend.md) separately warned that cheaper moves did not prove why scores improved. This guide extends the reading to all 25 max runs and locates the missing explanations level by level.

The useful next comparison is specific: does Boss's guide teach the rule missing in each highlighted row? That comparison has **not** been done here. This document grades what a human can learn from the published account, not the player's unobserved understanding.

# Flash-Next champion visual-transition matrix

This bundle starts from the immutable recovered Kaggle champion wrapper and
keeps its scored runtime contract: 32k analyzer context, fixed-30 retained
assistant turns, 22 workers, 6,480 seconds per game, strict cumulative action
cap 14, PLU0, no replay, no reflection, and the persistent top-six curator.

One runtime variable, `ARC3_VISUAL_TRANSITION_MODE`, defines the four arms:

1. `control`: exact champion model-facing prompts/evidence; all new evidence
   paths are dormant.
2. `metadata`: append only compact action/frame-count/sample-position labels;
   retain legacy ASCII storyboards and region inspection.
3. `additive`: append the labels and sampled raw images; retain legacy ASCII
   storyboards and region inspection.
4. `replace`: append the labels and sampled raw images; suppress legacy ASCII
   storyboards, reminder prose, and model-facing region inspection.

For an animation with `n` returned frames, the visual arms display
`k=min(n, 8, max(2, ceil(log2(n))))` returned frames. Frame zero and frame
`n-1` are pinned and the remaining slots are distributed uniformly. The prior
user turn already contains the pre-action grid; the timeline is followed by the
current-grid image, which is the exact settled state.

The transition observation is queued by the action-bearing tool result and
prepended to the next analyzer user message. Therefore the conversation order
is unambiguous: pre-action observation, assistant action/tool call, tool result,
labeled chronological frames, settled current grid, then the next reasoning.

Detector telemetry and the guarded meaningful-animation batch pause remain
enabled in all arms. Transition PNGs are budgeted as 72 context tokens each
rather than mistakenly counting their base64 bytes as language tokens.

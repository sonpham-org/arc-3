# v12ff4: winner-inspired toggles on the baseline bundle

Two model-agnostic techniques ported from the ARC-AGI-3 2nd/3rd-place milestone
solutions, applied to the baseline v12 bundle's ARC3-Inference (NOT repo HEAD, to
stay one-variable vs the 2.127 graft baseline). Both DEFAULT OFF.

- **Multi-frame images** (`MULTIMODAL_FRAMES=N`, cap 4): attach the last N boards as
  a chronological STEP-labeled image sequence instead of one current frame.
  Touches vision_context.py, tool_agent.py, prompts.py.
- **Click dead-signature** (`CLICK_DEADSIG=1`, `CLICK_DEADSIG_K=2`): suppress MOUSE
  clicks on object-classes (colour+shape signature) that never change the frame,
  per level. New click_heuristics.py + solver.py hook.

Bundle: gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ff4.tgz
Launch: gcp/v12ff4_startup.sh, technique via arc3-extra-env metadata.

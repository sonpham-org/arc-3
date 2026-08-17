# Qwen3.8 xhigh TAAF Kaggle-2.03 no-cap control

This is the one-variable control for Kaggle submission `55551321` (public
score `2.03`), notebook
`sonphamorg/arc3-qwen3-8-xhigh-taaf-native-checkpoint-cap8`, script version
`342637750`.

Source of truth downloaded on 2026-08-17:

- notebook SHA-256:
  `ef27bc3838ef769eff5d71bb4ee77f5c0187191ecd52682f7af33b4d1ca9a90`
- attached dataset: `sonphamorg/taaf-source-native-cap8-qwen38-xhigh`
- model: `Qwen/Qwen3.8-27B-FP8`
- model revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- reasoning effort: `xhigh`
- analyzer concurrency: `28`
- temperature/top-p/top-k: `0.6 / 0.95 / 20`
- server/analyzer context: `65536 / 32768`
- visual transport: `current_grid`, 4x upscale

The scored dataset differs from the pristine author TAAF source in exactly two
Python files and 19 added lines: ten lines in `framework/solver.py` implement
the eight-action checkpoint, and nine lines in `agent/tool_agent.py` expose its
metadata. This control uses the pristine author bundle
`bundle-taaf-plain-author-20260812-132401.tgz` (SHA-256
`7d030b62d95eed54899e3a8d0abf49281230d9f1ae7dcb72831a1cff86b18ce3`),
thereby removing only checkpoint-8 while retaining the scored notebook's model,
sampling, reasoning, context, concurrency, and 4x image transport.

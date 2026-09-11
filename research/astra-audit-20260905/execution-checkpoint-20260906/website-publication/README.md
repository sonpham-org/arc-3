# Production trace publication

All 12 trace exports below were accepted by the hash-verified production
publication API at `https://arc3.sonpham.net`. A final authenticated read on
2026-09-07T00:42:23Z matched every production artifact-manifest SHA-256 against
its local publication receipt or identical local export manifest. There were no
missing or mismatched runs. Publication changed the site data catalog atomically;
it did not require a Git change or Railway deployment.

The agreed 12-run scope is the ten selected context-matrix attempts plus the two
historical configurations that replaced overlapping paid matrix runs. The
separate 131,072-context, seven-lane historical run is outside both requested
aggregate-envelope grids and is therefore an optional 13th publication.

“Aggregate envelope” is configured context per lane multiplied by lanes. It is
not a universal physical KV-cache size. Scores use the fixed 25-game denominator.

| Aggregate envelope | Context/lane | Lanes | Policy | Final score | Trace | Artifact-manifest SHA-256 |
|---:|---:|---:|---|---:|---|---|
| 720,896 | 32,768 | 22 | fixed-30 baseline | 11.1726 | [open](https://arc3.sonpham.net/trace.html#run=g4run-q38-kwbase-astra-verify-r1-20260905-181701) | `ea8c9b90b95909aa1f3fe156fa3d3c097621f8e9ed186f52fd02f566e93c94d0` |
| 720,896 | 65,536 | 11 | fixed-30 | 18.2099 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-flash-cover-r1-20260906) | `a9f7e9547b75fc66a5b60ba8d34391bbde7361d29b361709e879c78948bd2e90` |
| 720,895 | 102,985 | 7 | full-context-R3 | 24.6980 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b720-w7-20260906) | `4db7f55b0eda4ba47eac9663a0a9c1f3f163c389ba7d3e8fdada9a32428a3c62` |
| 720,895 | 144,179 | 5 | full-context-R3 | 22.9610 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b720-w5-20260906) | `822727b32715c90eb171088692b51b6c1a08177c3a1a1308081e1e029aabf28d` |
| 720,896 | 180,224 | 4 | full-context-R3 | 20.5309 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b720-w4-recovery-r1-20260906) | `360cc19835ef03de7a736ff9cc8de8f441f190a5db294edff77d8c73ccc0c9e3` |
| 720,894 | 240,298 | 3 | full-context-R3 | 16.6700 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b720-w3-20260906) | `4a6ffd4c2ffd7d14fc357dffb8bcbfa9adc085bef4b29b84050e7775f0915b96` |
| 476,432 | 21,656 | 22 | full-context-R3; input-ceiling confound | 3.4846 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w22-recovery-r1-20260906) | `88e5dd5b77854f916a59897b18ebced3fbb50f7314ef1d9ef885f76960596a1b` |
| 476,443 | 43,313 | 11 | full-context-R3 | **27.6610** | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w11-recovery-r2-20260906) | `0201dd3736adb79873b22c11190eda2aaf535b79f90b2d0ed82c3cd220b4a960` |
| 476,441 | 68,063 | 7 | full-context-R3 | 21.4993 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w7-recovery-r1-20260906) | `7d8cd4df14b413e24879fd3f52e4f4fe4903fafe3fd16ec9f66a2b0262140086` |
| 476,445 | 95,289 | 5 | full-context-R3 | 17.9072 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w5-20260906) | `cc6d9151c5d71cd5e79f185afc20e0dd7ee40e4ae24ea726371cd0de906a601f` |
| 476,444 | 119,111 | 4 | full-context-R3 | 14.0285 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w4-recovery-r1-20260906) | `c0cfbf169b70a243269be207f772e0d469a01cea1ab7cb75608ac4615e4c7bf7` |
| 476,445 | 158,815 | 3 | full-context-R3 | 15.0032 | [open](https://arc3.sonpham.net/trace.html#run=g4run-astra-grid2-b476-w3-20260906) | `16b15d04d7b0a8b9889fdad0ae889a4a81d262b7c506c3d444ce1c216661ee05` |

The low-context 22-lane score is confounded by a 12,952-token effective input
ceiling after output and safety reserves. It should not be interpreted as an
isolated lane-count result.

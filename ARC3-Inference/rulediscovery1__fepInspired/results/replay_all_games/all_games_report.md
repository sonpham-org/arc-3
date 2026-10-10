# OpenMind rule-discovery agent, offline replay, one play per game (CPU only)

## ar25 ar25 (mixed): 311 steps, 7 clears, 40.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/base16rep_job12v7/output/artifacts/ar25-0c556536_p0_events.jsonl
- weight 1.0: the last outcome of the same action repeats
- weight 0.0: (no rules: counts only)
- surprise spikes: 21; first: [(12, 'ACTION3', 'appx2|mv-3+0x3+|shrinkx2'), (13, 'ACTION3', 'app|mv-3+0x3+|shrinkx2'), (29, 'ACTION3', 'app|mv-3+0x3+|shrinkx2|van'), (47, 'ACTION3', 'nothing')]
- goal guesses: [('convert every colour-11 cell', 1.0), ('leave exactly 1 colour-5 objects', 0.0)]

## bp35 bp35 (unknown): 276 steps, 3 clears, 26.6 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prompt_arms/runs/E-kaggle-20261002/artifacts/bp35-0a0ad940_p0_events.jsonl
- weight 1.0: d-pad moves colour-11 piece: ACTION3 (-6,+0), ACTION4 (+6,+0), ACTION7 (-6,+0); blocked by colours -
- weight 0.0: (no rules: counts only)
- surprise spikes: 9; first: [(5, 'ACTION4', 'nothing'), (98, 'ACTION4', 'appx3+|mv+0+3x3+|mv+0-3x3+|mv+1+3x3+|mv+1-3|mv+2-3|mv+3+0|mv+3+3|mv+3-3|mv-1+3x2|mv-1-3x3+|mv-2+3|mv-2-3|mv-3-2|mv-3-3x3+|vanx3+'), (120, 'ACTION4', 'appx3+|mv+0+2x3+|mv+0+3x3+|mv+0-3x3+|mv+1+3x3+|mv+1-3|mv+3+0|mv+3-3x2|mv-1-2x2|mv-1-3x3+|mv-2+3|mv-2-3|mv-3-2|mv-3-3x3+|vanx3+'), (138, 'ACTION4', 'level_clear')]
- goal guesses: [('line colour 3 up with colour 9', 0.29), ('line colour 9 up with colour 3', 0.29)]

## cd82 cd82 (mixed): 138 steps, 4 clears, 1.6 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prune16/results/v9/output/artifacts/cd82-fb555c5d_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 3; first: [(65, 'ACTION5', 'app|shrink|vanx2'), (98, 'ACTION5', 'rc8>14'), (124, 'ACTION5', 'grow|shrink|vanx2')]
- goal guesses: [('convert every colour-0 cell', 0.95), ('convert every colour-15 cell', 0.02)]

## cn04 cn04 (mixed): 134 steps, 4 clears, 2.8 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/level_reset/results/v10/output/artifacts/cn04-2fe56bfb_p0_events.jsonl
- weight 0.27: ACTION3 drives colour-0 piece into colour 8: collect; ACTION2 moves colour-11 piece by (+0,+3); blocked by colours - and the edge; ACTION4 moves colour-0 piece by (+3,+0); blocked by colours - and the edge; ACTION3 moves colour-8 piece by (-3,+0); blocked by colours - and the edge; ACTION5 moves colour-0 piece by (+0,+3); blocked by colours - and the edge; click bg does nothing
- weight 0.24: ACTION3 drives colour-0 piece into colour 8: collect; ACTION2 drives colour-11 piece into colour 4: push; ACTION4 moves colour-0 piece by (+3,+0); blocked by colours - and the edge; ACTION3 moves colour-8 piece by (-3,+0); blocked by colours - and the edge; ACTION5 moves colour-0 piece by (+0,+3); blocked by colours - and the edge; click bg does nothing
- surprise spikes: 0; first: []
- goal guesses: [('convert every colour-4 cell', 0.59), ('remove every colour-4 object', 0.32)]

## dc22 dc22 (mixed): 221 steps, 3 clears, 5.7 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/w13c103k_v13/output/artifacts/dc22-fdcac232_p0_events.jsonl
- weight 0.81: d-pad moves colour-14 piece: ACTION1 (+0,-2), ACTION2 (+0,+2), ACTION3 (-2,+0), ACTION4 (+2,+0); blocked by colours 4
- weight 0.18: d-pad moves colour-14 piece: ACTION1 (+0,-2), ACTION2 (+0,+2), ACTION3 (-2,+0), ACTION4 (+2,+0); blocked by colours 4
- surprise spikes: 8; first: [(64, 'ACTION4', 'growx2|mv+2+0|shrinkx2'), (76, 'ACTION6', 'appx2|vanx2'), (99, 'ACTION1', 'level_clear'), (147, 'ACTION6', 'appx3+|mv+3+3|mv-2-2x2|mv-3-3x3+|shrinkx2')]
- goal guesses: [('convert every colour-0 cell', 0.28), ('remove every colour-9 object', 0.13)]

## ft09 ft09 (click): 80 steps, 5 clears, 1.5 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prune16/results/v8/output/artifacts/ft09-0d8bbf25_p0_events.jsonl
- weight 0.88: the last outcome of the same action repeats; the previous step repeats
- weight 0.05: click on shape #7920 turns colour 11 into 14; the last outcome of the same action repeats
- surprise spikes: 4; first: [(6, 'ACTION6', 'level_clear'), (27, 'ACTION6', 'level_clear'), (43, 'ACTION6', 'level_clear'), (66, 'ACTION6', 'level_clear')]
- goal guesses: [('convert every colour-9 cell', 0.39), ('remove every colour-9 object', 0.33)]

## g50t g50t (unknown): 505 steps, 5 clears, 23.4 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prompt_arms/runs/ste/artifacts/g50t-5849a774_p0_events.jsonl
- weight 0.31: ACTION5 drives colour-9 piece into colour 1: collect; d-pad moves colour-5+colour-9 piece: ACTION1 (+0,-6), ACTION2 (+0,+6), ACTION3 (-6,+0), ACTION4 (+6,+0), ACTION5 (-24,+0); blocked by colours 0,8; 'grow' every 2 steps (any)
- weight 0.31: ACTION5 drives colour-9 piece into colour 1: collect; d-pad moves colour-5+colour-9 piece: ACTION1 (+0,-6), ACTION2 (+0,+6), ACTION3 (-6,+0), ACTION4 (+6,+0), ACTION5 (-24,+0); blocked by colours 0,8; 'grow' every 2 steps (buttons)
- surprise spikes: 19; first: [(9, 'ACTION2', 'grow|shrink'), (32, 'ACTION4', 'mv+3+0x2|shrinkx2'), (152, 'ACTION3', 'grow|mv-3+0x2|shrinkx3+'), (185, 'ACTION3', 'grow|mv+3+0x2|mv-3+0x2|shrink')]
- goal guesses: [('remove every colour-1 object', 0.82), ('convert every colour-8 cell', 0.12)]

## ka59 ka59 (mixed): 168 steps, 3 clears, 4.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/streamer25/results/armE25_rep2/output/artifacts/ka59-38d34dbb_p0_events.jsonl
- weight 0.38: ACTION3 drives colour-14 piece into colour 4: push; d-pad moves colour-0+colour-14 piece: ACTION1 (+0,-3), ACTION2 (+0,+3), ACTION3 (-3,+0), ACTION4 (+3,+0); blocked by colours 2,15
- weight 0.32: d-pad moves colour-0+colour-14 piece: ACTION1 (+0,-3), ACTION2 (+0,+3), ACTION3 (-3,+0), ACTION4 (+3,+0); blocked by colours 2,15
- surprise spikes: 3; first: [(124, 'ACTION4', 'appx3+|grow|shrink|vanx2'), (153, 'ACTION1', 'growx2|mv+0-3|shrinkx2|van'), (158, 'ACTION1', 'appx2|grow|shrinkx2|vanx2')]
- goal guesses: [('leave exactly 1 colour-0 objects', 0.39), ('leave exactly 1 colour-1 objects', 0.21)]

## lf52 lf52 (mixed): 288 steps, 3 clears, 14.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prompt_arms/runs/A-kaggle-20261002/artifacts/lf52-271a04aa_p0_events.jsonl
- weight 1.0: the last outcome of the same action repeats
- weight 0.0: (no rules: counts only)
- surprise spikes: 16; first: [(8, 'ACTION6', 'appx3+|mv+0+3x3+|shrink'), (32, 'ACTION2', 'grow|mv+0+3x3+|reshape|van'), (44, 'ACTION6', 'appx3+|mv+3+0x3+|shrinkx2'), (51, 'ACTION1', 'app|grow|mv+0-3x2|reshape|van')]
- goal guesses: [('leave exactly 1 colour-14 objects', 0.44), ('remove every colour-9 object', 0.2)]

## lp85 lp85 (click): 135 steps, 7 clears, 3.0 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prune16/results/v9/output/artifacts/lp85-305b61c3_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 1; first: [(5, 'ACTION6', 'mv+0+3x3+|mv+0-3x3+|mv+3+0x3+|mv+3-3|mv-3+0x3+')]
- goal guesses: [('make the colour-1 shapes match the colour-11 shapes', 0.11), ('make the colour-2 shapes match the colour-11 shapes', 0.11)]

## ls20 ls20 (button): 563 steps, 4 clears, 31.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prompt_arms/runs/D-kaggle-20261002/artifacts/ls20-9607627b_p0_events.jsonl
- weight 1.0: d-pad moves colour-9+colour-12 piece: ACTION1 (+0,-5), ACTION2 (+0,+5), ACTION3 (-5,+0), ACTION4 (+5,+0); blocked by colours 4,5
- weight 0.0: (no rules: counts only)
- surprise spikes: 18; first: [(7, 'ACTION1', 'app|grow|mv+0-3x2|shrink'), (115, 'ACTION3', 'grow|mv-3+0x2|vanx3+'), (120, 'ACTION2', 'level_clear'), (151, 'ACTION4', 'grow|shrink')]
- goal guesses: [('get colour 8 to touch colour 11', 0.22), ('get colour 11 to touch colour 8', 0.22)]

## m0r0 m0r0 (mixed): 174 steps, 4 clears, 2.5 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/w19c79k_v11/output/artifacts/m0r0-492f87ba_p0_events.jsonl
- weight 0.3: ACTION1 moves colour-10 piece by (+0,-5); blocked by colours - and the edge; ACTION2 moves colour-10 piece by (+0,+4); blocked by colours - and the edge; ACTION1 moves colour-10 piece by (+0,-4); blocked by colours - and the edge
- weight 0.3: ACTION2 moves colour-10 piece by (+0,+4); blocked by colours - and the edge; ACTION1 moves colour-10 piece by (+0,-5); blocked by colours - and the edge; ACTION1 moves colour-10 piece by (+0,-4); blocked by colours - and the edge
- surprise spikes: 0; first: []
- goal guesses: [('leave exactly 1 colour-5 objects', 0.23), ('convert every colour-8 cell', 0.1)]

## r11l r11l (click): 117 steps, 5 clears, 3.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/w13c120k_v12/output/artifacts/r11l-495a7899_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 0; first: []
- goal guesses: [('remove every colour-15 object', 0.42), ('make the colour-0 shapes match the colour-6 shapes', 0.16)]

## re86 re86 (button): 417 steps, 6 clears, 91.2 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/base16rep_job12v7/output/artifacts/re86-8af5384d_p0_events.jsonl
- weight 0.77: ACTION3 drives colour-0 piece into colour 8: push; ACTION2 drives colour-0 piece into colour 8: collect; ACTION3 drives colour-9 piece into colour 4: push; ACTION3 moves colour-12 piece by (-3,+0); blocked by colours - and the edge; d-pad moves colour-0 piece: ACTION1 (+0,-3), ACTION2 (+0,+3), ACTION3 (-3,+0), ACTION4 (+3,+0), ACTION5 (-9,+42); blocked by colours 10,14
- weight 0.23: ACTION3 drives colour-0 piece into colour 8: push; ACTION2 drives colour-0 piece into colour 8: collect; ACTION3 moves colour-12 piece by (-3,+0); blocked by colours - and the edge; d-pad moves colour-0 piece: ACTION1 (+0,-3), ACTION2 (+0,+3), ACTION3 (-3,+0), ACTION4 (+3,+0), ACTION5 (-9,+42); blocked by colours 10,14
- surprise spikes: 16; first: [(19, 'ACTION1', 'app|grow|mv+0-3x3+|shrinkx2|van'), (113, 'ACTION1', 'app|mv+0-3x3+|shrink'), (120, 'ACTION3', 'app|grow|mv-3+0x3+|shrink|vanx3+'), (158, 'ACTION1', 'appx3+|growx3+|shrink|vanx3+')]
- goal guesses: [('convert every colour-15 cell', 0.44), ('remove every colour-11 object', 0.4)]

## s5i5 s5i5 (click): 198 steps, 4 clears, 3.5 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/level_reset/results/v10/output/artifacts/s5i5-18d95033_p0_events.jsonl
- weight 1.0: the last outcome of the same action repeats
- weight 0.0: (no rules: counts only)
- surprise spikes: 13; first: [(10, 'ACTION6', 'appx2|growx3+|shrink|vanx3+'), (16, 'ACTION6', 'level_clear'), (40, 'ACTION6', 'nothing'), (69, 'ACTION6', 'growx2|mv+0+3|shrink')]
- goal guesses: [('convert every colour-12 cell', 0.31), ('leave exactly 2 colour-14 objects', 0.16)]

## sb26 sb26 (click): 146 steps, 7 clears, 1.8 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/base16rep_job12v7/output/artifacts/sb26-7fbdac44_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 8; first: [(7, 'ACTION6', 'grow|mv+3-3|mv-3+3|shrinkx2|van'), (26, 'ACTION6', 'grow|mv+2-3|mv-2+3|shrinkx2|van'), (52, 'ACTION6', 'grow|mv+1-3|mv-1+3|shrinkx2|van'), (65, 'ACTION6', 'grow|mv+3+3|mv-3-3x2|shrinkx2|van')]
- goal guesses: [('leave exactly 1 colour-11 objects', 0.28), ('leave exactly 1 colour-15 objects', 0.28)]

## sc25 sc25 (mixed): 250 steps, 4 clears, 7.3 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/slippery7_r2/results/armE/output/artifacts/sc25-635fd71a_p1_events.jsonl
- weight 0.37: ACTION4 drives colour-9 piece into colour 2: push; click on shape #2f0e turns colour 2 into 14; click on shape #2f0e turns colour 0 into 14; d-pad moves colour-9+colour-10 piece: ACTION3 (-2,+0), ACTION4 (+2,+0); blocked by colours 6; d-pad moves colour-10 piece: ACTION1 (+0,-2), ACTION2 (+0,+4); blocked by colours 5,9,13
- weight 0.37: ACTION4 drives colour-9 piece into colour 2: push; click on shape #2f0e turns colour 0 into 14; click on shape #2f0e turns colour 2 into 14; d-pad moves colour-9+colour-10 piece: ACTION3 (-2,+0), ACTION4 (+2,+0); blocked by colours 6; d-pad moves colour-10 piece: ACTION1 (+0,-2), ACTION2 (+0,+4); blocked by colours 5,9,13
- surprise spikes: 10; first: [(7, 'ACTION3', 'nothing'), (127, 'ACTION2', 'reshapex2'), (130, 'ACTION4', 'appx2|grow|vanx2'), (155, 'ACTION6', 'grow|rc14>2x2|vanx3+')]
- goal guesses: [('leave exactly 1 colour-3 objects', 0.27), ('leave exactly 1 colour-10 objects', 0.17)]

## sk48 sk48 (unknown): 260 steps, 2 clears, 19.2 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prompt_arms/runs/E-kaggle-20261002/artifacts/sk48-d8078629_p0_events.jsonl
- weight 1.0: ACTION3 drives colour-8 piece into colour 1: collect; d-pad moves colour-3 piece: ACTION1 (+0,+2), ACTION2 (+0,-2); blocked by colours 2
- weight 0.0: (no rules: counts only)
- surprise spikes: 10; first: [(6, 'ACTION4', 'appx3+|grow|shrinkx2'), (66, 'ACTION4', 'appx3+|grow|shrink'), (161, 'ACTION3', 'grow|mv+3+0x3+|mv-1-1|mv-3+0|mv-3+1|shrink|vanx3+'), (165, 'ACTION4', 'appx3+|mv+1+1|mv+3+0|mv+3-1|mv-3+0x3+')]
- goal guesses: [('leave exactly 1 colour-8 objects', 0.08), ('leave exactly 1 colour-9 objects', 0.08)]

## sp80 sp80 (mixed): 164 steps, 4 clears, 3.0 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/base16rep_job12v7/output/artifacts/sp80-589a99af_p0_events.jsonl
- weight 1.0: the last outcome of the same action repeats
- weight 0.0: (no rules: counts only)
- surprise spikes: 8; first: [(8, 'ACTION5', 'level_clear'), (20, 'ACTION5', 'game_over'), (49, 'ACTION3', 'mv-3+0'), (85, 'ACTION6', 'mv+3+3|mv-3-3')]
- goal guesses: [('convert every colour-14 cell', 0.29), ('leave exactly 1 colour-11 objects', 0.16)]

## su15 su15 (click): 113 steps, 3 clears, 0.5 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/prune16/results/v8/output/artifacts/su15-1944f8ab_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 4; first: [(10, 'ACTION6', 'mv+2-2|mv-2+2'), (17, 'ACTION6', 'level_clear'), (30, 'ACTION6', 'mv-1-3'), (80, 'ACTION6', 'level_clear')]
- goal guesses: [('remove every colour-10 object', 0.66), ('convert every colour-10 cell', 0.21)]

## tn36 tn36 (click): 200 steps, 4 clears, 3.9 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/vg_opener/results/armS/output/artifacts/tn36-ef4dde99_p0_events.jsonl
- weight 1.0: the last outcome of the same action repeats
- weight 0.0: (no rules: counts only)
- surprise spikes: 11; first: [(32, 'ACTION6', 'level_clear'), (52, 'ACTION6', 'app|mv+3+0|rc1>5x3+|van'), (54, 'ACTION6', 'app|mv-3+0|rc5>1x3+|van'), (64, 'ACTION6', 'mv+0+3x3+|mv+0-3x3+|mv+3+0')]
- goal guesses: [('line colour 1 up with colour 11', 0.32), ('line colour 11 up with colour 1', 0.32)]

## tr87 tr87 (button): 188 steps, 5 clears, 3.5 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/level_reset/results/v10/output/artifacts/tr87-cd924810_p0_events.jsonl
- weight 1.0: (no rules: counts only)
- surprise spikes: 4; first: [(40, 'ACTION1', 'app|grow|reshape|shrink'), (120, 'ACTION1', 'growx2|mv+2+0|shrink|van'), (140, 'ACTION2', 'app|grow|mv+0+2|shrinkx2'), (163, 'ACTION1', 'growx2|mv+0-1|shrinkx3+')]
- goal guesses: [('leave exactly 1 colour-0 objects', 0.62), ('convert every colour-1 cell', 0.06)]

## tu93 tu93 (button): 350 steps, 8 clears, 38.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/w13c120k_v12/output/artifacts/tu93-0768757b_p0_events.jsonl
- weight 0.5: ACTION1 drives colour-4 piece into colour 0: push; ACTION3 drives colour-9 piece into colour 0: push; ACTION4 drives colour-12 piece into colour 0: push; ACTION3 drives colour-12 piece into colour 0: collect; ACTION2 drives colour-4 piece into colour 0: collect; ACTION4 drives colour-9 piece into colour 0: push; ACTION3 drives colour-9 piece into colour 8: collect; d-pad moves colour-12 piece: ACTION1 (+0,+6), ACTION2 (+0,+6), ACTION3 (+0,+6), ACTION4 (+0,+6); blocked by colours -
- weight 0.5: ACTION1 drives colour-4 piece into colour 0: push; ACTION3 drives colour-9 piece into colour 0: push; ACTION3 drives colour-12 piece into colour 0: collect; ACTION4 drives colour-12 piece into colour 0: push; ACTION2 drives colour-4 piece into colour 0: collect; ACTION4 drives colour-9 piece into colour 0: push; ACTION3 drives colour-9 piece into colour 8: collect; d-pad moves colour-12 piece: ACTION1 (+0,+6), ACTION2 (+0,+6), ACTION3 (+0,+6), ACTION4 (+0,+6); blocked by colours -
- surprise spikes: 16; first: [(27, 'ACTION2', 'level_clear'), (31, 'ACTION4', 'game_over'), (61, 'ACTION1', 'app|mv+0+3|mv+1-3|van'), (64, 'ACTION2', 'appx2|mv+1+3|vanx3+')]
- goal guesses: [('get colour 0 to touch colour 9', 0.16), ('get colour 9 to touch colour 0', 0.16)]

## vc33 vc33 (click): 286 steps, 6 clears, 2.3 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/lane_sweep/results/w13c103k_v13/output/artifacts/vc33-5430563c_p0_events.jsonl
- weight 0.73: the last outcome of the same action follows appx2|grow|mv+0+3x2|rc1>12|shrink->grow|mv+0-3x2|rc12>1|shrink|vanx2, growx2|mv+0+2x2|mv+0-2x2|shrinkx2->growx2|mv+0+2x2|mv+0-2x2|shrinkx2, growx2|mv+0+2x2|shrinkx2->growx2|mv+0+2x2|shrinkx2, growx2|shrinkx2->growx2|shrinkx2, grow|mv+0+3x2|shrink->appx2|grow|mv+0+3x2|rc1>12|shrink, grow|mv+3+0x2|mv-3+0x2|rc12>1|shrink|vanx2->grow|mv+3+0x2|mv-3+0x2|shrink
- weight 0.27: the previous step follows growx2|mv+0+2x2|mv+0-2x2|shrinkx2->growx2|mv+0+2x2|mv+0-2x2|shrinkx2, growx2|mv+0+2x2|shrinkx2->growx2|mv+0+2x2|shrinkx2, growx2|shrinkx2->growx2|shrinkx2, grow|mv+0+3x2|shrink->appx2|grow|mv+0+3x2|rc1>12|shrink, grow|mv+3+0x2|mv-3+0x2|rc12>1|shrink|vanx2->grow|mv+3+0x2|mv-3+0x2|shrink
- surprise spikes: 13; first: [(5, 'ACTION6', 'grow|mv-3+0x2'), (12, 'ACTION6', 'mv+3+0x2|van'), (14, 'ACTION6', 'app|mv-3+0x2'), (18, 'ACTION6', 'mv-3+0x2|van')]
- goal guesses: [('leave exactly 1 colour-11 objects', 0.81), ('leave exactly 1 colour-14 objects', 0.14)]

## wa30 wa30 (button): 600 steps, 4 clears, 145.1 s
replay: /Users/macmini/bubba-workspace/arc3-kaggle/vg_opener/results/armS/output/artifacts/wa30-ee6fef47_p0_events.jsonl
- weight 0.5: ACTION3 drives colour-5 piece into colour 12: push; ACTION5 drives colour-5 piece into colour 12: collect; ACTION3 drives colour-14 piece into colour 4: convert to colour 3; ACTION5 drives colour-5 piece into colour 2: push; ACTION1 drives colour-5 piece into colour 12: push; ACTION4 moves colour-12 piece by (-4,+0); blocked by colours - and the edge; d-pad moves colour-14 piece: ACTION1 (+0,-4), ACTION2 (+0,+4), ACTION3 (-4,+0); blocked by colours 4; d-pad moves colour-14 piece: ACTION1 (+0,-4), ACTION2 (+0,+4), ACTION3 (-4,+0), ACTION4 (+4,+0); blocked by colours 3,4
- weight 0.5: ACTION5 drives colour-5 piece into colour 12: collect; ACTION3 drives colour-5 piece into colour 12: push; ACTION3 drives colour-14 piece into colour 4: convert to colour 3; ACTION5 drives colour-5 piece into colour 2: push; ACTION1 drives colour-5 piece into colour 12: push; ACTION4 moves colour-12 piece by (-4,+0); blocked by colours - and the edge; d-pad moves colour-14 piece: ACTION1 (+0,-4), ACTION2 (+0,+4), ACTION3 (-4,+0); blocked by colours 4; d-pad moves colour-14 piece: ACTION1 (+0,-4), ACTION2 (+0,+4), ACTION3 (-4,+0), ACTION4 (+4,+0); blocked by colours 3,4
- surprise spikes: 18; first: [(102, 'ACTION4', 'grow|rc4>5|shrink'), (126, 'ACTION3', 'app|growx3+|mv+0-3|shrinkx3+'), (154, 'ACTION3', 'grow|rc4>5|shrink'), (269, 'ACTION5', 'app|mv-3+0|reshape|shrink')]
- goal guesses: [('convert every colour-7 cell', 0.49), ('convert every colour-9 cell', 0.49)]

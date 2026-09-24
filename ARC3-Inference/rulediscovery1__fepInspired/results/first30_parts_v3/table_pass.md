# Rule discovery prototype, offline replay (pass split, 30 plays, likelihood=parts)

| arm | nats/step | gain vs chain back-off (95% CI) |
|---|---|---|
| all | 1.977 | +0.053 [+0.007, +0.115] |
| all_game_cluster | 1.977 | +0.053 [+0.005, +0.112] |
| button | 2.445 | +0.064 [-0.002, +0.239] |
| click | 1.267 | +0.038 [-0.025, +0.163] |
| mixed | 2.483 | +0.063 [+0.006, +0.140] |

policy agreement with the played action: {"top1_share": 0.06709533128319821, "mean_percentile": 0.20726465223573817, "top_salience_share": 0.6737489516354487, "ranked_steps": 3577}
configs chosen on training folds: [{"fold": 0, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0, "likelihood": "parts"}, "train_nats_per_step": 1.7073690491951643}, {"fold": 1, "config": {"propose_every": 5, "max_hypotheses": 8, "dl_weight": 0.25, "likelihood": "parts"}, "train_nats_per_step": 2.311885255195253}]
wall seconds: 160.8

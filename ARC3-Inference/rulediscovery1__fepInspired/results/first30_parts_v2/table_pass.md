# Rule discovery prototype, offline replay (pass split, 30 plays, likelihood=parts)

| arm | nats/step | gain vs chain back-off (95% CI) |
|---|---|---|
| all | 1.995 | +0.035 [+0.002, +0.083] |
| all_game_cluster | 1.995 | +0.035 [-0.002, +0.088] |
| button | 2.500 | +0.009 [+0.000, +0.033] |
| click | 1.263 | +0.042 [-0.012, +0.150] |
| mixed | 2.505 | +0.042 [-0.004, +0.109] |

policy agreement with the played action: {"top1_share": 0.06681576740285156, "mean_percentile": 0.20594772878084988, "top_salience_share": 0.8378529493989376, "ranked_steps": 3577}
configs chosen on training folds: [{"fold": 0, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0, "likelihood": "parts"}, "train_nats_per_step": 1.7073690491951643}, {"fold": 1, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0, "likelihood": "parts"}, "train_nats_per_step": 2.3159769366767304}]
wall seconds: 97.7

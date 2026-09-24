# Rule discovery prototype, offline replay (pass split, 30 plays)

| arm | nats/step | gain vs chain back-off (95% CI) |
|---|---|---|
| all | 2.017 | +0.012 [-0.003, +0.030] |
| all_game_cluster | 2.017 | +0.012 [-0.007, +0.033] |
| button | 2.509 | +0.000 [+0.000, +0.000] |
| click | 1.269 | +0.036 [+0.004, +0.068] |
| mixed | 2.553 | -0.007 [-0.015, +0.000] |

policy agreement with the played action: {"top1_share": 0.06457925636007827, "mean_percentile": 0.20557371778471625, "top_salience_share": 0.7945205479452054, "ranked_steps": 3577}
configs chosen on training folds: [{"fold": 0, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0}, "train_nats_per_step": 1.6876745801704645}, {"fold": 1, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0}, "train_nats_per_step": 2.305623112627403}]
wall seconds: 57.0

# Rule discovery prototype, offline replay (pass split, 30 plays, likelihood=parts)

| arm | nats/step | gain vs chain back-off (95% CI) |
|---|---|---|
| all | 2.016 | +0.014 [+0.001, +0.030] |
| all_game_cluster | 2.016 | +0.014 [-0.002, +0.033] |
| button | 2.509 | +0.000 [+0.000, +0.000] |
| click | 1.269 | +0.036 [+0.011, +0.066] |
| mixed | 2.549 | -0.002 [-0.005, +0.000] |

policy agreement with the played action: {"top1_share": 0.06346100083869165, "mean_percentile": 0.20524822272324472, "top_salience_share": 0.7483925076880067, "ranked_steps": 3577}
configs chosen on training folds: [{"fold": 0, "config": {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0, "likelihood": "parts"}, "train_nats_per_step": 1.6859866754351613}, {"fold": 1, "config": {"propose_every": 5, "max_hypotheses": 8, "dl_weight": 1.0, "likelihood": "parts"}, "train_nats_per_step": 2.2999256731829827}]
wall seconds: 127.6

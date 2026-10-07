## Warehouse (wa30)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions |
|---|---|---|---|---|---|---|---|---|
| random | 20 | 0 | 0 | None | 0 | 0 | 0 | 500.0 |
| touch_tl | 20 | 0 | 0 | None | 0 | 2 | 0 | 500.0 |
| tl_only | 20 | 0 | 0 | None | 0 | 9 | 0 | 500.0 |
| dp_self | 20 | 0 | 0 | None | 0 | 19 | 0 | 231.5 |
| dp_face | 20 | 0 | 0 | None | 0 | 2 | 0 | 500.0 |
| dp_epi | 20 | 0 | 0 | None | 0 | 5 | 0 | 500.0 |
| dp_arch | 20 | 0 | 0 | None | 0 | 1 | 0 | 500.0 |
| dp_goal | 20 | 0 | 0 | None | 0 | 2 | 0 | 500.0 |
| dp_s12 | 20 | 0 | 0 | None | 0 | 19 | 0 | 231.5 |
| dp_s123 | 20 | 0 | 0 | None | 0 | 20 | 0 | 212.0 |
| dp_all | 20 | 0 | 0 | None | 0 | 6 | 0 | 500.0 |

| arm | self kept (all steps) | self kept (turn steps) | own move seen right | grab positions | interact there | plays with a grab | grabs | MAP predicts change at grab pos. (after 1st grab) | plays: Facing clause in MAP | box configs (median) | plays with a new config | box on target |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random | 0/0 (0%) | 0/0 (0%) | 0/0 (0%) | 214 | 41 (19%) | 17 | 41 | 0/0 (0%) | - | 3.5 | 13 | 0 |
| touch_tl | 1295/9759 (13%) | 79/5017 (2%) | 1920/7303 (26%) | 551 | 18 (3%) | 11 | 18 | 38/253 (15%) | - | 5.0 | 11 | 0 |
| tl_only | 782/8898 (9%) | 110/5242 (2%) | 1366/6420 (21%) | 224 | 4 (2%) | 4 | 4 | 42/107 (39%) | - | 1.0 | 4 | 0 |
| dp_self | 4757/5195 (92%) | 2520/2766 (91%) | 3787/4087 (93%) | 625 | 1 (0%) | 1 | 1 | 0/44 (0%) | - | 1.0 | 1 | 0 |
| dp_face | 1293/9759 (13%) | 79/5001 (2%) | 1917/7289 (26%) | 579 | 18 (3%) | 11 | 18 | 38/253 (15%) | 0 | 5.0 | 11 | 0 |
| dp_epi | 1171/9371 (12%) | 106/5017 (2%) | 1540/6698 (23%) | 430 | 19 (4%) | 10 | 19 | 52/322 (16%) | - | 4.5 | 10 | 0 |
| dp_arch | 1298/9996 (13%) | 111/5136 (2%) | 1861/7531 (25%) | 563 | 26 (5%) | 12 | 26 | 46/284 (16%) | - | 8.5 | 12 | 0 |
| dp_goal | 1295/9759 (13%) | 79/5017 (2%) | 1920/7303 (26%) | 551 | 18 (3%) | 11 | 18 | 38/253 (15%) | - | 5.0 | 11 | 0 |
| dp_s12 | 4757/5195 (92%) | 2520/2766 (91%) | 3787/4087 (93%) | 625 | 1 (0%) | 1 | 1 | 0/44 (0%) | 0 | 1.0 | 1 | 0 |
| dp_s123 | 4120/5233 (79%) | 1917/2351 (82%) | 3455/4097 (84%) | 526 | 19 (4%) | 19 | 19 | 69/422 (16%) | 0 | 12.0 | 19 | 0 |
| dp_all | 7081/8539 (83%) | 3263/3809 (86%) | 5668/6569 (86%) | 757 | 62 (8%) | 16 | 62 | 123/500 (25%) | 0 | 12.0 | 16 | 0 |

| arm | archive cells (median) | returns | arrived | missed | new cells after a return |
|---|---|---|---|---|---|
| dp_arch | 49.0 | 25 | 16 | 8 | 673 |
| dp_all | 17.5 | 108 | 56 | 45 | 102 |

## Locksmith (ls20)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions |
|---|---|---|---|---|---|---|---|---|
| touch_tl | 20 | 20 | 20 | 48.5 | 0 | 20 | 0 | 185.0 |
| tl_only | 20 | 20 | 20 | 51.5 | 0 | 20 | 0 | 205.5 |
| dp_self | 20 | 20 | 20 | 48.0 | 0 | 20 | 0 | 184.5 |
| dp_face | 20 | 20 | 20 | 48.5 | 0 | 20 | 0 | 185.0 |
| dp_epi | 20 | 20 | 20 | 40.5 | 0 | 20 | 0 | 177.5 |
| dp_arch | 20 | 20 | 20 | 48.5 | 0 | 1 | 0 | 500.0 |
| dp_goal | 20 | 20 | 20 | 48.5 | 0 | 20 | 0 | 185.0 |
| dp_s12 | 20 | 20 | 20 | 48.0 | 0 | 20 | 0 | 184.5 |
| dp_s123 | 20 | 20 | 20 | 47.0 | 0 | 20 | 0 | 183.0 |
| dp_all | 20 | 20 | 20 | 47.0 | 0 | 0 | 0 | 500.0 |

| arm | archive cells (median) | returns | arrived | missed | new cells after a return |
|---|---|---|---|---|---|
| dp_arch | 28.0 | 180 | 169 | 3 | 0 |
| dp_all | 26.0 | 190 | 179 | 0 | 0 |

## Ghost Twin (g50t)

| arm | plays | levels | plays clearing | first clear (median action) | plays clearing level 2 | game overs | time-outs | median actions |
|---|---|---|---|---|---|---|---|---|
| touch_tl | 20 | 0 | 0 | None | 0 | 13 | 0 | 330.0 |
| tl_only | 20 | 1 | 1 | 183 | 0 | 18 | 0 | 312.5 |
| dp_self | 20 | 3 | 3 | 80 | 0 | 17 | 0 | 260.0 |
| dp_face | 20 | 0 | 0 | None | 0 | 12 | 0 | 330.0 |
| dp_epi | 20 | 1 | 1 | 69 | 0 | 13 | 0 | 410.5 |
| dp_arch | 20 | 2 | 2 | 298.5 | 0 | 5 | 0 | 500.0 |
| dp_goal | 20 | 0 | 0 | None | 0 | 13 | 0 | 330.0 |
| dp_s12 | 20 | 3 | 3 | 80 | 0 | 17 | 0 | 260.0 |
| dp_s123 | 20 | 1 | 1 | 54 | 0 | 17 | 0 | 176.5 |
| dp_all | 20 | 4 | 4 | 263.5 | 0 | 4 | 0 | 500.0 |

| arm | archive cells (median) | returns | arrived | missed | new cells after a return |
|---|---|---|---|---|---|
| dp_arch | 26.0 | 64 | 52 | 7 | 148 |
| dp_all | 24.5 | 98 | 58 | 30 | 79 |


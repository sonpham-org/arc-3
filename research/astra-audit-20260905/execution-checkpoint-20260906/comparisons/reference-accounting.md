# Verified reference-run accounting

| Measurement | Exact baseline replication | Flash64 reference |
|---|---:|---:|
| VM start-to-stop | 2h 22m 03.020s | 4h 35m 03.103s |
| Gameplay elapsed | 2h 12m 40.088s | 4h 24m 05.441s |
| Returned gameplay tokens | 2,628,543 | 3,873,442 |
| Workers / game limit | 22 / 108 min | 11 / 88 min |
| Score at 132 gameplay minutes | 11.17264239 | 11.22637065 |
| Levels at 132 gameplay minutes | 48 | 48 |

The baseline total and Flash64 total are cumulative successful-response completion tokens, including reasoning once. They are not exact server-generation bills: timed-out, aborted, or otherwise unreturned generation can be missing. Earlier action-attached totals undercounted successful responses that produced no later action by 56,979 baseline tokens and 76,669 Flash64 tokens.

At the common completed-response budget of 2,628,543 tokens, Flash64 reached 11.60313427 and 50 levels. At 2.7M it remains 11.60313427 because the next whole response crosses the boundary. Response receipt is a discrete proxy; concurrent generation can precede the recorded receipt.

The retrospective 108k-per-game Flash64 view reaches 13.08819746 with 2,658,550 accepted whole-response tokens. It is a replayed allocation rule, not the outcome of an actual hard-capped run.

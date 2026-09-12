<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: Records how to actually get a Kaggle kernel onto the RTX PRO 6000 from the CLI,
after three earlier smoke tests silently landed on a Tesla P100 while reporting success.
Written so nobody spends a 20h experiment budget on hardware they didn't ask for.
SRP/DRY check: Pass -- no existing note on Kaggle accelerator selection.
-->

# Kaggle RTX PRO 6000 from the CLI — two gates, both silent

**Confirmed 12-Sep-2026, 16:2x ET, account `markbarney`, kernel `markbarney/arc3-accel-smoke` v11.**
Log line: `NVIDIA RTX PRO 6000 Blac...`.

## The working recipe

`kernel-metadata.json`:
```json
{
  "enable_gpu": true,
  "competition_sources": ["arc-prize-2026-arc-agi-3"]
}
```
Push:
```bash
kaggle kernels push -p <folder> --accelerator NvidiaRtxPro6000
```

Both parts are load-bearing.

## Gate 1 — capitalization, and the server lies about it

Kaggle's own web bundle spells the enum **camelCase**: `nvidiaRtxPro6000`, `nvidiaTeslaP100`,
`nvidiaH100`, `nvidiaL4`. That is the client-side spelling. The **API wants PascalCase** —
the form documented in `kagglesdk` (`NvidiaTeslaP100`, `NvidiaTeslaT4`).

An unrecognized value is **not** an error. It is silently coerced to the generic string `Gpu`,
which schedules a P100. Probed directly with `KernelExecutionType.QUICK_SAVE` (saves without a
full run) and reading `machine_shape` back off `get_kernel`:

| pushed value | `error` | machine_shape read back |
|---|---|---|
| `nvidiaTeslaT4` | `''` | `Gpu` |
| `NvidiaTeslaT4` | `''` | `NvidiaTeslaT4` |
| `nvidiaRtxPro6000` | `''` | `Gpu` |
| `NvidiaRtxPro6000` | `''` | `NvidiaRtxPro6000` |
| `RTX_PRO_6000` | `''` | `Gpu` |

Empty error string on every row. The push reports success either way.

**Verification primitive worth keeping:** you can read the server's stored shape without
burning a run.

```python
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi(); api.authenticate()
with api.build_kaggle_client() as k:
    r = ApiGetKernelRequest(); r.user_name = "markbarney"; r.kernel_slug = "<slug>"
    print(k.kernels.kernels_api_client.get_kernel(r).metadata.machine_shape)
```

## Gate 2 — the competition allowlist

Fixing the case is **not sufficient**. Version 10 was pushed with `NvidiaRtxPro6000`, read
back as `NvidiaRtxPro6000`, and still executed on a `Tesla P100-PCIE-16GB`.

Version 11 was identical except `competition_sources: ["arc-prize-2026-arc-agi-3"]` was
attached. It landed on the RTX PRO 6000. The gating flag in Kaggle's bundle is
`KernelsRtxPro6000Comps` — a per-competition allowlist — which matches the observed behavior:
the card is granted through the competition, not the account.

So a saved `machine_shape` is a *request*, not a guarantee. The scheduler downgrades without
saying so.

## Why the earlier three smoke tests failed

- v1 `--accelerator nvidiaRtxPro6000` — camelCase, coerced to `Gpu` → P100
- v2 `machine_shape` in metadata, `enable_gpu` off — CPU
- v3 camelCase + competition attached — camelCase still coerced → P100

v3 had the right competition and the wrong string; v10 had the right string and no
competition. Only v11 had both. Every one of them reported a successful push.

## Standing rule for the experiment arms

**Do not trust the request. Read the card.** Every real ARC-3 run keeps `nvidia-smi` in its
own log as the first cell, and the hardware is recorded from that line, never assumed from
`machine_shape`. Had this not been probed first, the plan would have produced ~20 hours of
clean-looking P100 numbers labeled RTX PRO 6000.

## Quota, as of this probe

`GetAcceleratorQuotaStatistics` reports the GPU pool at 108,000s = 30h/week, refreshing
Thu 18-Sep 20:00 ET. The editor dialog for this card reads "Availability is limited to 30
hours per week. You have 29 hours remaining." Cost of the whole investigation: under two
minutes of runtime across five short kernel versions.

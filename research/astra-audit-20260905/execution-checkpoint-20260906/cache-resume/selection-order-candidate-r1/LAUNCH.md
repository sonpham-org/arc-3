# Frozen ordering-control launcher

Launcher: `../start_selection_order_server.py`.
Source SHA-256:
`31d122581d154780590813b799863d495b87e27d7231c28716d69e0efa88601f`.
Portable tests: `../test_start_selection_order_server.py`; all 14 pass.

The source binds candidate manifest
`9581fb0105abaf3c1850cb6ec0c668199098dbb2004e45cbe8e2e2fc3300de34`,
parent manifest
`966b7a9d01f5994d0580468104f3147fa9fd3acdc4af8a20e5a7e42890afd56f`,
the exact owned-probe candidate path, candidate ops
`1bb70e3410908e334de9df490f876473ad6b83ca5c3af9c25632b685d69d924d`,
and the existing model/embedding-aware helper identities. It also verifies the
image's original model, scheduler and QSA ops source hashes, each mounted payload,
the dependency map, and the frozen FP8 numerical report.

Example for the parent operator after separately reconciling the isolated probe:

```sh
python3 /opt/arc3/astra-probe/qsa-resume-correctness-r1/start_selection_order_server.py \
  --arm qsa-cpu-fp8-bytecheck --attempt e1 \
  --scheduler-alignment-fix --synchronous-eager --layer-trace \
  --resume-diagnostics /opt/arc3/astra-probe/qsa-resume-correctness-r1/selection-order-candidate-r1 \
  --resume-manifest-sha256 9581fb0105abaf3c1850cb6ec0c668199098dbb2004e45cbe8e2e2fc3300de34
```

The new output directory begins `serving/selection-order-r1-`. The launcher
refuses an existing service, an uncertain container-name check, a missing owned
`READY` marker, or a reused attempt directory. It never stops another service.
Preparing and testing this launcher performed no Docker, GPU or cloud actions.

Resources and numerical settings match the frozen v2 control: context 131,072;
22 sequences; GPU allocation .965; 6,144 batched tokens; eager execution; async
scheduling disabled; 16 GiB CPU cache; auto MoE backend; trace maximum 128
forwards. The compiled-cache location is also unchanged. The root task controls
the finite probe runtime, source upload, launch and later reconciliation.

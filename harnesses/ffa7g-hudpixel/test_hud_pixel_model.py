"""Standalone dry-run test for _HudPixelModel + _verify_hud_model_percell -- the two new
classes this variant adds on top of ../ffa7g/. Mirrors the project's own replay-dry-run
verification convention (see harnesses/ffa7g/MANIFEST.md's ls20 table).

Self-contained: applies this variant's own patch to a throwaway copy of the frozen
baseline-v12, then extracts just the two new pure-Python classes as source text (NOT a real
import -- inference/framework/solver.py depends on the `taaf` package, which this repo's
harness scripts don't need installed locally just to validate this logic). Run directly:

    python3 harnesses/ffa7g-hudpixel/test_hud_pixel_model.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "harnesses" / "baseline-v12" / "src" / "ARC3-Inference"
PATCH = REPO_ROOT / "harnesses" / "ffa7g-hudpixel" / "patch" / "ffa7g-hudpixel-full-stack.patch"


def _patched_solver_source() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "ARC3-Inference"
        shutil.copytree(BASELINE, target)
        subprocess.run(["patch", "-p1", "-i", str(PATCH)], cwd=target, check=True,
                        stdout=subprocess.DEVNULL)
        return (target / "inference" / "framework" / "solver.py").read_text()


def _extract(src: str, start_marker: str, end_marker: str) -> str:
    start = src.index(start_marker)
    end = src.index(end_marker, start)
    return src[start:end]


_solver_src = _patched_solver_source()
_extracted_src = _extract(_solver_src, "def _verify_hud_model_percell", "class _StateGraph")
_ns: dict = {}
exec(compile(_extracted_src, "<extracted _HudPixelModel>", "exec"), _ns)
_HudPixelModel = _ns["_HudPixelModel"]
_verify_hud_model_percell = _ns["_verify_hud_model_percell"]


CODE_CORRECT = (
    "def advance_hud(frame, action):\n"
    "    rows = frame.split('\\n')\n"
    "    counter_chars = '0123456789'\n"
    "    idx = counter_chars.index(rows[0][0])\n"
    "    new_first = counter_chars[(idx + 1) % 10]\n"
    "    rows[0] = new_first + rows[0][1:]\n"
    "    return '\\n'.join(rows)\n"
)


def make_board(counter_digit, extra="gg"):
    return [f"{counter_digit}{extra}", "BBB", "WWW"]


def run() -> None:
    model = _HudPixelModel(window=20, threshold=0.9, warmup=3)
    err = model.register(CODE_CORRECT)
    assert err is None, f"register failed: {err}"
    assert model.active

    print("=== Phase 1: model predicts correctly every action ===")
    prev = make_board(0)
    for i in range(1, 6):
        actual = make_board(i % 10)
        pred = model.predict("\n".join(prev), "ACTION1")
        assert pred is not None
        bar_cells, mispred = _verify_hud_model_percell(prev, actual, pred.split("\n"))
        model.observe(bar_cells, mispred)
        print(f"  action {i}: bar_cells={sorted(bar_cells)} mispredicted={sorted(mispred)} "
              f"trusted={sorted(model.trusted_cells())}")
        prev = actual
    assert (0, 0) in model.trusted_cells(), "counter cell should be trusted after warmup"
    print(f"  PASS: counter cell (0,0) trusted. trusted={sorted(model.trusted_cells())}")

    print("\n=== Phase 2: a second cell changes too, but the model never claims it ===")
    for i in range(6, 10):
        actual = make_board(i % 10)
        actual[1] = "X" + actual[1][1:]  # unrelated real-gameplay change at (1,0)
        pred = model.predict("\n".join(prev), "ACTION1")
        bar_cells, mispred = _verify_hud_model_percell(prev, actual, pred.split("\n"))
        model.observe(bar_cells, mispred)
        prev = actual
    assert (1, 0) not in model.trusted_cells(), "unclaimed cell must never be masked"
    print(f"  PASS: unclaimed real-gameplay cell (1,0) never entered the mask. "
          f"trusted={sorted(model.trusted_cells())}")

    print("\n=== Phase 3: the model starts mispredicting (e.g. counter frozen/reset) ===")
    prev = make_board(5)
    for i in range(20):
        actual = make_board(5)  # frozen -- "always increment" is now wrong every time
        pred = model.predict("\n".join(prev), "ACTION1")
        bar_cells, mispred = _verify_hud_model_percell(prev, actual, pred.split("\n"))
        model.observe(bar_cells, mispred)
        prev = actual
    assert (0, 0) not in model.trusted_cells(), "cell should drop out once consistently wrong"
    print(f"  PASS: (0,0) dropped out of trust within the rolling window -- non-monotonic, "
          f"no whole-model reset needed. trusted={sorted(model.trusted_cells())}")

    print("\n=== Phase 4: re-registering different code resets per-cell trust ===")
    model2 = _HudPixelModel(window=20, threshold=0.9, warmup=3)
    model2.register(CODE_CORRECT)
    prev = make_board(0)
    for i in range(1, 6):
        actual = make_board(i % 10)
        pred = model2.predict("\n".join(prev), "ACTION1")
        bar_cells, mispred = _verify_hud_model_percell(prev, actual, pred.split("\n"))
        model2.observe(bar_cells, mispred)
        prev = actual
    assert (0, 0) in model2.trusted_cells()
    model2.register(CODE_CORRECT + "\n# forces a different source string\n")
    assert model2.trusted_cells() == set(), "expected trust reset on re-register"
    print("  PASS: re-registering (different source) resets per-cell trust to empty.")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run()
    sys.exit(0)

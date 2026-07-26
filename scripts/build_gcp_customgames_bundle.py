"""Package a subset of custom (non-official) ARC-AGI-3 games into a small tarball
the GCP harness startup script can merge into /opt/arc3/environment_files/,
alongside the official 25 baked into the shared arc3-code-tufa0.tgz object.

This does NOT touch that shared object (many other harness variants depend on
it staying exactly as-is) -- it's a small, separately-named supplementary
tarball, uploaded once and referenced by its own startup-script variant.

Usage: python scripts/build_gcp_customgames_bundle.py [code ...]
(defaults to the 17 custom games currently live on the Games tab)
"""

import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIBLING_DIR = Path("/home/son/GitHub/arc-agi-3/environment_files")
STAGING = ROOT / "gcp" / "_staging_customgames" / "environment_files"
OUT_TGZ = ROOT / "gcp" / "environment-extra-customgames17.tgz"

DEFAULT_CODES = [
    "ac", "ar", "cr", "fr", "gh", "lb", "pc", "pi",
    "ps", "pt", "px", "sh", "sn", "td", "ts", "ws03", "ws04",
]

# taaf's GameAPI (tufa-arc-agi-framework/src/taaf/game_api.py:230-244) sets
# number_of_levels from the engine's actual win_levels, but base_actions_per_level
# straight from metadata.json's baseline_actions -- and taaf/game.py:483 hard-
# asserts the two lengths match, OUTSIDE any per-game try/except, so a mismatch
# kills the entire run, not just that one game (confirmed 2026-07-26: pi01's
# stale 4-entry baseline_actions against its real 9 levels took down a 17-game
# run on the very first non-empty-baseline game it hit). A metadata.json with
# baseline_actions=[] is falsy -> base_actions_per_level stays None -> the
# assert is skipped entirely (same "zero partial credit" path 9 of the 17
# games already use natively). Below: every code whose CURRENT baseline_actions
# length doesn't match its actual level count gets neutralized to [] before
# packaging, rather than guessing at "correct" per-level values nobody recorded.
NEUTRALIZE_BASELINE_ACTIONS = {"pi", "fr", "ps"}  # 4-vs-9, 4-vs-5, 2-vs-1 mismatches


def main():
    codes = sys.argv[1:] or DEFAULT_CODES
    shutil.rmtree(STAGING.parent, ignore_errors=True)
    STAGING.mkdir(parents=True)

    game_ids = []
    for code in codes:
        code_dir = SIBLING_DIR / code
        version_dirs = sorted(d for d in code_dir.iterdir() if d.is_dir() and d.name != "__pycache__")
        vdir = version_dirs[-1]  # latest, matches build_games_manifest.py's selection
        dest = STAGING / code / vdir.name
        dest.mkdir(parents=True)
        for f in vdir.glob("*"):
            if f.name == "__pycache__":
                continue
            shutil.copy2(f, dest / f.name)
        import json
        meta_path = dest / "metadata.json"
        meta = json.loads(meta_path.read_text())
        note = ""
        if code in NEUTRALIZE_BASELINE_ACTIONS and meta.get("baseline_actions"):
            note = f" [baseline_actions {meta['baseline_actions']} -> [] to avoid a level-count mismatch crash]"
            meta["baseline_actions"] = []
            meta_path.write_text(json.dumps(meta, indent=2))
        game_ids.append(meta["game_id"])
        print(f"  {code} -> {vdir.name} ({meta['game_id']}: {meta.get('title')}){note}")

    with tarfile.open(OUT_TGZ, "w:gz") as tar:
        tar.add(STAGING.parent / "environment_files", arcname="environment_files")
    print(f"\n{len(codes)} games -> {OUT_TGZ} ({OUT_TGZ.stat().st_size / 1024:.0f} KB)")
    print(f"\nARC3_GAME_SUBSET=\"{' '.join(game_ids)}\"")


if __name__ == "__main__":
    main()

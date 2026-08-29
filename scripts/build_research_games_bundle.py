"""Build a deterministic ARC environment overlay from research game metadata.

Unlike the historical custom-games script, this builder has no machine-specific
sibling-repository paths and no hard-coded list of game IDs. Research metadata is
the source of truth. The resulting tarball can be unpacked over an existing
``environment_files`` tree for either the ARC3 default harness or Tufa.

Held-out games stay off the public site. Building a local bundle does not change
the browser manifest and does not publish or deploy anything.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
GAME_METADATA_DIR = ROOT / "research" / "games"
DEFAULT_OUTPUT_DIR = ROOT / ".cache" / "research-game-bundles"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", choices=("gpt", "anthropic", "all"), default="all")
    parser.add_argument(
        "--status",
        action="append",
        dest="statuses",
        help="Include a status; repeat for several. Defaults to prototype/qualified/sealed.",
    )
    parser.add_argument("--game", action="append", dest="games", help="Include one game_id; repeatable.")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_metadata(partition: str, statuses: set[str], games: set[str] | None):
    selected = []
    for path in sorted(GAME_METADATA_DIR.glob("*.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if partition != "all" and metadata["author_partition"] != partition:
            continue
        if metadata["status"] not in statuses:
            continue
        if games and metadata["game_id"] not in games:
            continue
        selected.append((path, metadata))
    if not selected:
        raise SystemExit("No research games matched the requested filters")
    return selected


def runtime_metadata(metadata: dict, runtime_dir: str) -> dict:
    game_id = f"{metadata['game_id']}-{metadata['version']}"
    # Keep semantic titles out of evaluator-visible environment metadata.
    return {
        "game_id": game_id,
        "title": metadata["game_id"].upper(),
        "default_fps": 6,
        "tags": [],
        "baseline_actions": [],
        "local_dir": runtime_dir,
        "research": {
            "schema_version": metadata["schema_version"],
            "author_partition": metadata["author_partition"],
            "source_sha256": metadata["artifacts"]["source_sha256"],
            "status": metadata["status"],
        },
    }


def add_bytes(tar: tarfile.TarFile, arcname: str, payload: bytes):
    info = tarfile.TarInfo(arcname)
    info.size = len(payload)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    from io import BytesIO

    tar.addfile(info, BytesIO(payload))


def main():
    args = parse_args()
    statuses = set(args.statuses or ("prototype", "qualified", "sealed"))
    games = set(args.games) if args.games else None
    selected = load_metadata(args.partition, statuses, games)

    output = args.output
    if output is None:
        output = DEFAULT_OUTPUT_DIR / f"research-games-{args.partition}.tgz"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    bundle_manifest = {"schema_version": 1, "games": []}
    with output.open("wb") as raw_output:
        # tarfile's ``w:gz`` path records the current time in the gzip header.
        # Wrap it explicitly so identical inputs produce identical bundle bytes.
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, mtime=0
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as tar:
                for metadata_path, metadata in selected:
                    source_path = (ROOT / metadata["artifacts"]["source"]).resolve()
                    source = source_path.read_bytes()
                    digest = hashlib.sha256(source).hexdigest()
                    expected = metadata["artifacts"]["source_sha256"]
                    if digest != expected:
                        raise SystemExit(
                            f"Source hash mismatch for {metadata['game_id']}: "
                            f"{digest} != {expected}"
                        )

                    code = metadata["game_id"]
                    version = metadata["version"]
                    runtime_dir = f"environment_files/{code}/{version}"
                    source_name = source_path.name
                    add_bytes(tar, f"{runtime_dir}/{source_name}", source)

                    runtime = runtime_metadata(metadata, runtime_dir)
                    add_bytes(
                        tar,
                        f"{runtime_dir}/metadata.json",
                        (json.dumps(runtime, indent=2, sort_keys=True) + "\n").encode(
                            "utf-8"
                        ),
                    )
                    add_bytes(
                        tar,
                        f"{runtime_dir}/research-metadata.json",
                        (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode(
                            "utf-8"
                        ),
                    )
                    bundle_manifest["games"].append(
                        {
                            "game_id": f"{code}-{version}",
                            "author_partition": metadata["author_partition"],
                            "source_sha256": digest,
                            "metadata_file": metadata_path.relative_to(ROOT).as_posix(),
                        }
                    )

                add_bytes(
                    tar,
                    "research-bundle-manifest.json",
                    (json.dumps(bundle_manifest, indent=2, sort_keys=True) + "\n").encode(
                        "utf-8"
                    ),
                )

    bundle_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"{len(bundle_manifest['games'])} game(s) -> {output}")
    print(f"sha256={bundle_hash}")


if __name__ == "__main__":
    main()

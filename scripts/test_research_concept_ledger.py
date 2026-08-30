"""Invariant tests for the expanded 1,000-design inventory."""
import csv,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def rows(path):
 with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f,delimiter="\t"))
def test_expanded_inventory_is_complete_and_unique():
 old=rows(ROOT/"research"/"gpt-ideas-v1.tsv");new=rows(ROOT/"research"/"gpt-ideas-v2.tsv");anth=rows(ROOT/"research"/"anthropic-build-ideas-v1.tsv")
 assert len(old)==200 and len(new)==800 and len(anth)==200 and len(new)+len(anth)==1000
 assert new[:200]==old
 for field in ("id","internal_title","concept"):assert len({r[field] for r in new})==800
 assert set(Counter(r["primary_axis"] for r in new).values())=={40}
 assert [r["id"] for r in new]==[f"q{i:03d}" for i in range(1,801)]
def test_expanded_inventory_audit_matches_bytes():
 a=json.loads((ROOT/"research"/"gpt-ideas-v2.audit.json").read_text());p=ROOT/a["output_ledger"]
 assert hashlib.sha256(p.read_bytes()).hexdigest()==a["output_sha256"] and a["combined_design_inventory"]==1000
 assert len(a["structural_variants"])==30 and len(set(a["structural_variants"]))==30 and a["domain_families"]==30

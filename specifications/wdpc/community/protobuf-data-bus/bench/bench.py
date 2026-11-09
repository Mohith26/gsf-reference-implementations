"""Check WDPC Table 1 budgets and the spec's protobuf-vs-JSON claims.

The spec states protobuf gives "2-6x faster processing and 30-70% smaller
message sizes compared to JSON" and sets per-data-type serialization budgets
in Table 1. This script measures both on the fixtures in wdpc_ref/fixtures.py
and writes results/bench.json and results/bench.md.

    python bench/bench.py [--quick]
"""

import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import google.protobuf
from google.protobuf.internal import api_implementation

from wdpc_ref.fixtures import TABLE_1
from wdpc_ref.measure import measure


def main(argv):
    quick = "--quick" in argv
    loops, runs = (20, 3) if quick else (200, 7)
    rows = []
    for row, (factory, ser_budget, access_budget) in TABLE_1.items():
        m = measure(factory(), loops=loops, runs=runs)
        m.update(table_1_row=row, ser_budget_ms=ser_budget, access_budget_ms=access_budget,
                 ser_within_budget=m["ser_ms_protobuf"] < ser_budget,
                 de_within_budget=m["de_ms_protobuf"] < access_budget)
        rows.append(m)
    env = {
        "python": platform.python_version(),
        "protobuf": google.protobuf.__version__,
        "protobuf_backend": api_implementation.Type(),
        "machine": f"{platform.system()} {platform.machine()}",
        "loops": loops, "runs": runs,
    }
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "bench.json").write_text(json.dumps({"env": env, "rows": rows}, indent=2) + "\n")

    lines = [
        (f"Environment: Python {env['python']}, protobuf {env['protobuf']} "
         f"({env['protobuf_backend']} backend), {env['machine']}; "
         f"median of {runs} runs x {loops} ops."),
        "",
        ("| Table 1 row | Message | PB bytes | JSON bytes | Size cut | Size cut (gzip) "
         "| PB ser ms | Budget | JSON ser ms | Ser speedup | PB parse ms | JSON parse ms "
         "| Parse speedup |"),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['table_1_row']} | {r['message']} | {r['bytes_protobuf']} | {r['bytes_json']} "
            f"| {r['size_reduction_pct']:.0f}% | {r['size_reduction_gzip_pct']:.0f}% "
            f"| {r['ser_ms_protobuf']:.4f} | <{r['ser_budget_ms']:g} "
            f"| {r['ser_ms_json_dict']:.4f} | {r['ser_speedup_vs_json_dict']:.1f}x "
            f"| {r['de_ms_protobuf']:.4f} | {r['de_ms_json_dict']:.4f} "
            f"| {r['de_speedup_vs_json_dict']:.1f}x |")
    (out_dir / "bench.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

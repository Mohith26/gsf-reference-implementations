"""Lint the protobuf definitions embedded in the WDPC spec.

Usage:
    python tools/lint_spec.py [path/to/WDPC-Spec.md] [--json]
Exit code is 1 when any error-severity finding is reported.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wdpc_ref.schema import SPEC_PATH
from wdpc_ref.specparse import lint_file, summary


def main(argv: list[str]) -> int:
    paths = [a for a in argv if not a.startswith("--")]
    model = lint_file(paths[0] if paths else SPEC_PATH)
    if "--json" in argv:
        print(json.dumps({
            "blocks": len(model.blocks),
            "definitions": len(model.by_name()),
            "undefined_types": model.undefined_types(),
            "summary": summary(model),
            "findings": [f.__dict__ for f in model.findings],
        }, indent=2))
    else:
        print(f"{len(model.blocks)} protobuf blocks, {len(model.by_name())} distinct "
              f"definitions, {len(model.undefined_types())} referenced-but-undefined types")
        for code, n in summary(model).items():
            print(f"  {code}: {n}")
        print()
        for f in model.findings:
            print(f)
    return 1 if any(f.severity == "error" for f in model.findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

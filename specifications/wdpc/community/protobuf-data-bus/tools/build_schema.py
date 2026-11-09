"""Regenerate proto/wdpc/v1/wdpc.proto from spec/WDPC-Spec.md.

Usage:
    python tools/build_schema.py          # write the .proto file
    python tools/build_schema.py --check  # exit 1 if the committed file is stale
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wdpc_ref.schema import PROTO_PATH, SPEC_PATH, to_proto_text
from wdpc_ref.specparse import lint_file


def main(argv: list[str]) -> int:
    text = to_proto_text(lint_file(SPEC_PATH))
    if "--check" in argv:
        current = PROTO_PATH.read_text(encoding="utf-8") if PROTO_PATH.exists() else ""
        if current != text:
            print(f"{PROTO_PATH} is out of date; run python tools/build_schema.py")
            return 1
        print("schema up to date")
        return 0
    PROTO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROTO_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {PROTO_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

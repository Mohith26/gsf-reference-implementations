"""Size and timing measurements for WDPC messages: protobuf vs JSON.

Two JSON baselines are measured so the comparison is fair to JSON:

* ``json_dict``: ``json.dumps`` / ``json.loads`` of a plain Python dict
  (what a JSON-first service would actually do on the hot path);
* ``json_pb``: the protobuf canonical JSON mapping
  (``MessageToJson`` / ``Parse``), i.e. the same schema sent as JSON.

Times are per message, median of ``runs`` runs of ``loops`` operations each.
"""

from __future__ import annotations

import gzip
import json
import statistics
import time

from google.protobuf import json_format


def _per_op(fn, loops: int, runs: int) -> float:
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter_ns()
        for _ in range(loops):
            fn()
        samples.append((time.perf_counter_ns() - t0) / loops)
    return statistics.median(samples) / 1e6  # ms


def measure(msg, loops: int = 200, runs: int = 7) -> dict:
    cls = type(msg)
    pb = msg.SerializeToString()
    as_dict = json_format.MessageToDict(msg, preserving_proto_field_name=True)
    js = json.dumps(as_dict, separators=(",", ":")).encode()
    jpb = json_format.MessageToJson(msg, indent=None).encode()

    def pb_parse():
        cls().ParseFromString(pb)

    out = {
        "message": msg.DESCRIPTOR.name,
        "bytes_protobuf": len(pb),
        "bytes_json": len(js),
        "bytes_protobuf_gzip": len(gzip.compress(pb, 6, mtime=0)),
        "bytes_json_gzip": len(gzip.compress(js, 6, mtime=0)),
        "ser_ms_protobuf": _per_op(msg.SerializeToString, loops, runs),
        "ser_ms_json_dict": _per_op(lambda: json.dumps(as_dict, separators=(",", ":")), loops, runs),
        "ser_ms_json_pb": _per_op(lambda: json_format.MessageToJson(msg, indent=None), loops, runs),
        "de_ms_protobuf": _per_op(pb_parse, loops, runs),
        "de_ms_json_dict": _per_op(lambda: json.loads(js), loops, runs),
        "de_ms_json_pb": _per_op(lambda: json_format.Parse(jpb, cls()), loops, runs),
    }
    out["size_reduction_pct"] = 100.0 * (1 - out["bytes_protobuf"] / out["bytes_json"])
    out["size_reduction_gzip_pct"] = 100.0 * (1 - out["bytes_protobuf_gzip"] / out["bytes_json_gzip"])
    out["ser_speedup_vs_json_dict"] = out["ser_ms_json_dict"] / out["ser_ms_protobuf"]
    out["de_speedup_vs_json_dict"] = out["de_ms_json_dict"] / out["de_ms_protobuf"]
    return out

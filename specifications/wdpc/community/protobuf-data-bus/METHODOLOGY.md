# Methodology and choices

## Source

`spec/WDPC-Spec.md` is a verbatim copy of `WDPC-Spec.md` from
Green-Software-Foundation/Workload-Dynamic-Power-and-Cooling at commit
`dd286c300e8fc90707a9b796241b2451c657a1eb` (MIT licensed). Everything in
`proto/` is generated from that file; nothing in the schema is typed by hand.
When the spec changes, replace the copy and run `python tools/build_schema.py`.

## Parsing

The parser handles the proto3 subset the spec uses: top-level `message` and
`enum` blocks, scalar, message, `repeated` and `map<K, V>` fields, `package`
lines and `//` comments. A block's section is the nearest Markdown heading
above it; headings ending in `.proto` mark Annex A.

## How the schema is resolved

1. **Defined types are copied exactly.** Field names, types and numbers come
   from the spec unchanged, including the enums whose zero value is a real
   state. Changing those numbers would make this implementation incompatible
   with any other implementation that follows the spec literally, so they are
   reported by the linter instead of fixed.
2. **Annex A wins over body text.** Annex A is marked normative. For
   `WorkloadDataPublication` this means `future_intent = 7` and the extra
   `metadata` / `dependencies` fields; for `PowerProfile` it adds
   `transitions`.
3. **Truncated definitions keep their complete fields.** Annex A stops in the
   middle of `PowerSystemStatus`, so only `power_system_id = 1` is kept.
4. **Undefined types become empty placeholder messages.** 61 types are
   referenced and never defined. An empty message is wire compatible with any
   later definition: a reader built from this schema keeps the new fields as
   unknown fields and re-serializes them unchanged
   (`tests/test_schema.py::test_placeholder_is_forward_compatible`). Two of
   them, `SensorType` and `EnergySource`, read like enums; they are still
   emitted as messages because the spec gives no values, which is noted here
   rather than guessed.
5. **One package, `wdpc.v1`.** Annex A names three packages
   (`wdpc.core.v1`, `wdpc.workload.v1`, `wdpc.infrastructure.v1`) but the
   third is truncated and the body types have no package. A single package
   keeps every cross-reference resolvable.

## Envelope and security

The Security section requires HMAC-SHA256 integrity, message sequence
numbers and timestamp validation for every message, but `WDPCMessage` has no
field for any of them. This implementation carries them in `custom_headers`
(field 17):

| Header | Meaning |
|---|---|
| `wdpc-payload-type` | full protobuf name of the payload |
| `wdpc-seq` | per-source counter, strictly increasing |
| `wdpc-hmac-sha256` | HMAC over the deterministic serialization of the envelope with this header removed |

The HMAC covers the payload and every other header, so changing the sequence
number or payload type invalidates it. Verification rejects unknown sources,
bad MACs, messages older than `max_age_s` (default 5 s) or more than
`max_skew_s` (default 1 s) in the future, and any sequence number not greater
than the last one accepted from that source. Each subscription keeps its own
replay window. Keys are per source and supplied by the caller; key
distribution is out of scope.

Dedicated envelope fields (for example `uint64 sequence = 6; bytes mac = 7;`)
would be a cleaner fix in a future spec revision.

## Topics

The spec mentions "ticker symbols" for data streams without defining a
format. This implementation uses dot-separated names, for example
`WDPC.<facility>.<rack>.<node>.<stream>`, with `*` matching one segment and
`>` matching the rest, the same convention NATS uses.

## Benchmark

* One fixture per Table 1 row, built only from fields the spec defines.
* Protobuf: `SerializeToString` / `ParseFromString`.
* JSON baseline: `json.dumps` / `json.loads` of the equivalent dict with
  compact separators. The canonical protobuf JSON mapping is also measured
  and stored in `results/bench.json` (`*_json_pb`).
* gzip level 6 for the compressed sizes.
* Per-operation time is the median of 7 runs of 200 operations.
* Results depend on language and runtime. The speed ratios here are
  Python-specific; the byte counts are not.

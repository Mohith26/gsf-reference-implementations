# WDPC: protobuf data model and data bus envelope

A community reference implementation of the
[Workload Dynamic Power and Cooling (WDPC)](https://github.com/Green-Software-Foundation/Workload-Dynamic-Power-and-Cooling)
specification, v1.0 (spec commit `dd286c3`, approved for public release
March 2026).

WDPC defines its data model as protobuf snippets spread through the spec text
and Annex A. This project turns those snippets into something a team can
actually build against, and checks the spec's own numeric claims:

1. **Spec linter** (`tools/lint_spec.py`): extracts every protobuf block from
   `WDPC-Spec.md`, parses it, and reports what stops it from compiling or
   being wire compatible.
2. **Compilable schema** (`proto/wdpc/v1/wdpc.proto`): generated from the
   spec by `tools/build_schema.py`, keeping every field name, type and number
   the spec gives. It compiles with `protoc` and loads at runtime with only
   the `protobuf` package.
3. **Data bus envelope** (`wdpc_ref/bus.py`): the Annex A `WDPCMessage`
   wrapper plus the Security section's HMAC-SHA256 integrity, sequence
   numbers against replay and timestamp freshness, with ticker-style topics
   and wildcard subscriptions over a pluggable transport.
4. **Table 1 benchmark** (`bench/bench.py`): serialization and parse time and
   message size for one message per Table 1 data type, protobuf vs JSON.

## Run it

```bash
pip install -r requirements-dev.txt
python -m pytest                       # 25 tests, offline, < 1 s
python tools/lint_spec.py              # spec findings
python tools/build_schema.py --check   # schema matches the vendored spec
python bench/bench.py                  # writes results/bench.md and .json
python examples/intent_signal_demo.py  # workload -> cooling intent signal
```

## What the linter finds in WDPC v1.0

| Finding | Count | Example |
|---|---:|---|
| Types referenced but never defined | 61 | `ThermalMetrics` (used by `RackSystem.thermal_status`), `ThermalProfile`, `PowerTransition`, `SensorType` |
| Same field with two different field numbers | 1 | `WorkloadDataPublication.future_intent` is `= 16` in the body and `= 7` in Annex A; the two are not wire compatible |
| Message defined twice with different fields | 2 | Annex A adds `metadata`, `dependencies` to `WorkloadDataPublication` and `transitions` to `PowerProfile` |
| Truncated definition | 1 | Annex A `wdpc_infrastructure.proto` ends mid-field at `PowerSystemStatus.total_consumption_mw` |
| Enum whose zero value is meaningful | 6 | an unset `WorkloadType` reads as `AI_TRAINING`; an unset `GridStabilityIndicator` reads as `STABLE` |

The spec defines 38 distinct messages and enums and references 61 more, so as
written it cannot be compiled by `protoc`. The schema in this project resolves
that without changing anything the spec does define; see
[METHODOLOGY.md](./METHODOLOGY.md).

## Benchmark results

From `results/bench.md` (Python 3.12, protobuf 7.36 upb backend, Apple
Silicon arm64, one core, median of 7 runs x 200 operations):

| Table 1 row | Message | Protobuf bytes | JSON bytes | Size cut | Size cut after gzip | Protobuf serialize | Table 1 budget |
|---|---|---:|---:|---:|---:|---:|---:|
| Node power profiling | NodeSystem (8 processors, 16 DIMMs) | 1,294 | 4,195 | 69% | 28% | 0.7 us | 10 ms |
| Component-level monitoring | ComponentDataStream (1 GPU) | 146 | 338 | 57% | 44% | 0.1 us | 5 ms |
| Thermal monitoring | ThermalSystemData (48 sensors) | 1,793 | 5,780 | 69% | 27% | 0.9 us | 20 ms |
| Infrastructure status | FacilityStatus (4 racks x 8 nodes) | 41,976 | 135,499 | 69% | 28% | 20 us | 30 ms |
| External coordination | GridOperatorData | 124 | 335 | 63% | 51% | 0.1 us | 100 ms |

What this says about the spec's claims:

- **Size:** "30-70% smaller than JSON" holds for uncompressed messages
  (57-69% here). Once both sides are gzip-compressed, which a Kafka or Pulsar
  deployment usually does, the gap narrows to 27-51%.
- **Serialization budgets:** every Table 1 budget is met by three to five
  orders of magnitude on one core in Python. Encoding is not the bottleneck;
  transport, batching and the envelope are.
- **Speed:** in Python, protobuf (C-backed upb) serializes 20-32x faster
  and parses 6-17x faster than the standard `json` module. That is larger
  than the spec's "2-6x", but it mostly measures Python's JSON encoder, so it
  should not be quoted as a cross-language number.
- **Envelope cost:** wrapping, HMAC signing, verifying and decoding one
  component sample takes about 9 us, about 115k messages/s on one Python
  thread (`examples/intent_signal_demo.py`). The spec's "1+ million messages
  per second per partition" is a broker property; per-message authentication
  is the part a producer has to budget for.

## Scope

In scope: the data model, the envelope and its authentication rules, topic
routing, and measurement of the Table 1 serialization budgets.

Out of scope: a Kafka, Pulsar or MQTT Sparkplug B client (the transport
interface is one `publish(topic, bytes)` method so one can be dropped in),
X.509 signatures (the spec gives no field or algorithm for them), schema
registry integration, and any control algorithm, which the spec explicitly
does not prescribe.

All sample data is synthetic and generated deterministically by
`wdpc_ref/fixtures.py`. No hardware, broker, or paid service is needed.

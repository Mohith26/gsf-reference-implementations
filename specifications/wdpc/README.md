# WDPC

Reference implementations of the
[Workload Dynamic Power and Cooling (WDPC)](https://github.com/Green-Software-Foundation/Workload-Dynamic-Power-and-Cooling)
specification, which standardizes how workloads, power systems, cooling
systems and grid operators exchange data over a shared protobuf data bus.

| Implementation | Maintainer | What it covers |
|---|---|---|
| [protobuf-data-bus](./community/protobuf-data-bus/) | Community | Spec linter, compilable proto3 schema generated from the spec, authenticated `WDPCMessage` envelope with topic routing, Table 1 serialization benchmark |

Environment: Python 3.12.13, protobuf 7.36.2 (upb backend), Darwin arm64; median of 7 runs x 200 ops.

| Table 1 row | Message | PB bytes | JSON bytes | Size cut | Size cut (gzip) | PB ser ms | Budget | JSON ser ms | Ser speedup | PB parse ms | JSON parse ms | Parse speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Node power profiling | NodeSystem | 1294 | 4195 | 69% | 28% | 0.0007 | <10 | 0.0209 | 29.2x | 0.0009 | 0.0130 | 14.4x |
| Component-level monitoring | ComponentDataStream | 146 | 338 | 57% | 44% | 0.0001 | <5 | 0.0022 | 20.0x | 0.0003 | 0.0016 | 6.1x |
| Thermal monitoring | ThermalSystemData | 1793 | 5780 | 69% | 27% | 0.0009 | <20 | 0.0270 | 29.7x | 0.0012 | 0.0167 | 13.8x |
| Infrastructure status | FacilityStatus | 41976 | 135499 | 69% | 28% | 0.0197 | <30 | 0.6331 | 32.1x | 0.0240 | 0.4150 | 17.3x |
| External coordination | GridOperatorData | 124 | 335 | 63% | 51% | 0.0001 | <100 | 0.0024 | 21.2x | 0.0003 | 0.0017 | 6.3x |

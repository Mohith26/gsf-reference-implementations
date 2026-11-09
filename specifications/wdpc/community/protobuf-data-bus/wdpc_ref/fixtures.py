"""Deterministic sample messages for each row of WDPC Table 1.

Values are synthetic but shaped like real telemetry (a GPU node with eight
accelerators, a 1 s thermal scan of a rack, a training job announcing a power
ramp). Only fields the spec actually defines are populated, so the sizes
measured in bench/ reflect the spec's own schema.
"""

from __future__ import annotations

import random

from .schema import load

T0_NS = 1_780_000_000_000_000_000  # fixed timestamp for reproducible output


def _ts(msg, offset_ms: int = 0) -> None:
    msg.timestamp.FromNanoseconds(T0_NS + offset_ms * 1_000_000)


def component_sample(rng: random.Random | None = None):
    """Component-level monitoring: one GPU sample (100 ms resolution row)."""
    rng = rng or random.Random(1)
    s = load()
    m = s.ComponentDataStream(component_id="fac1.r07.n03.gpu5")
    _ts(m)
    m.type = s.enum_value("ComponentType", "PROCESSOR_GPU")
    m.power_data.instantaneous_power_watts = 700 + rng.random() * 300
    m.power_data.average_power_watts = 820.5
    m.power_data.peak_power_watts = 1012.0
    m.power_data.power_efficiency_percent = 94.1
    m.extended_metrics["junction_temp_c"] = 71.0 + rng.random()
    m.extended_metrics["hbm_temp_c"] = 66.2
    m.extended_metrics["sm_clock_mhz"] = 1980.0
    return m


def node_profile(rng: random.Random | None = None, processors: int = 8, dimms: int = 16):
    """Node power profiling: one node with its processors and memory."""
    rng = rng or random.Random(2)
    s = load()
    n = s.NodeSystem(node_id="fac1.r07.n03")
    _ts(n)
    for i in range(processors):
        p = n.cpus.add(processor_id=f"fac1.r07.n03.gpu{i}")
        _ts(p)
        p.power_consumption_watts = 650 + rng.random() * 350
        p.temperature_celsius = 60 + rng.random() * 15
        p.utilization_percent = 80 + rng.random() * 20
    for i in range(dimms):
        mm = n.memory.add(memory_id=f"fac1.r07.n03.dimm{i}")
        _ts(mm)
        mm.power_consumption_watts = 8 + rng.random() * 4
        mm.temperature_celsius = 45 + rng.random() * 10
    n.node_configuration["cooling"] = "two-phase-cold-plate"
    n.node_configuration["bios"] = "2.4.1"
    return n


def thermal_scan(rng: random.Random | None = None, sensors: int = 48):
    """Thermal monitoring: one rack-level scan of coolant and junction sensors."""
    rng = rng or random.Random(3)
    s = load()
    t = s.ThermalSystemData(thermal_system_id="fac1.r07.hru1")
    _ts(t)
    locs = ["COOLANT_INLET", "COOLANT_OUTLET", "AMBIENT_AIR", "SILICON_JUNCTION"]
    for i in range(sensors):
        m = t.temperatures.add(sensor_id=f"fac1.r07.ts{i:02d}")
        m.location = s.enum_value("SensorLocation", locs[i % len(locs)])
        m.temperature_celsius = 30 + rng.random() * 45
        m.temperature_accuracy = 0.5
    t.thermal_efficiency["ppue"] = 1.02
    return t


def facility_status(rng: random.Random | None = None, racks: int = 4, nodes: int = 8):
    """Infrastructure status: a facility snapshot with racks and nodes."""
    rng = rng or random.Random(4)
    s = load()
    f = s.FacilityStatus(facility_id="fac1")
    _ts(f)
    for r in range(racks):
        rack = f.racks.add(rack_id=f"fac1.r{r:02d}")
        _ts(rack)
        rack.power_consumption.instantaneous_power_watts = 90_000 + rng.random() * 30_000
        rack.power_consumption.average_power_watts = 100_000
        for k in ("inlet_c", "outlet_c", "humidity_pct"):
            rack.sensor_readings[k] = rng.random() * 50
        for n in range(nodes):
            node = rack.nodes.add()
            node.CopyFrom(node_profile(rng, processors=8, dimms=16))
            node.node_id = f"fac1.r{r:02d}.n{n:02d}"
    f.facility_metadata["site"] = "example"
    return f


def workload_publication(rng: random.Random | None = None, intents: int = 12):
    """Workload data publication with forward-looking intent signals."""
    rng = rng or random.Random(5)
    s = load()
    w = s.WorkloadDataPublication(workload_id="train-llm-70b-run42")
    _ts(w)
    w.workload_type = s.enum_value("WorkloadType", "AI_TRAINING")
    w.power_requirements.peak_power_mw = 38.0
    w.power_requirements.baseline_power_mw = 6.5
    w.power_requirements.ramp_rate_mw_per_sec = 780.0
    w.power_requirements.duration_estimate_sec = 86_400
    w.power_requirements.temporal_resolution_ms = 100
    for i in range(intents):
        sig = w.future_intent.add()
        sig.predicted_time.FromNanoseconds(T0_NS + (i + 1) * 2_000_000_000)
        sig.predicted_power_mw = 38.0 if i % 2 == 0 else 6.5
        sig.confidence_level = 0.9 + rng.random() * 0.1
        sig.intent_description = "checkpoint" if i % 2 else "step"
    w.policy_preferences["carbon"] = "prefer-low"
    return w


def grid_update(rng: random.Random | None = None):
    """External coordination: grid operator data (15 min resolution row)."""
    rng = rng or random.Random(6)
    s = load()
    g = s.GridOperatorData(grid_operator_id="ercot")
    _ts(g)
    g.current_status.system_frequency_hz = 60.0 - rng.random() * 0.02
    g.current_status.carbon_intensity_g_co2_kwh = 380.0
    g.current_status.renewable_percentage = 41.5
    g.current_status.stability = s.enum_value("GridStabilityIndicator", "MODERATE_STRESS")
    for k in ("reserve_margin_pct", "lmp_usd_mwh", "load_mw"):
        g.grid_parameters[k] = rng.random() * 1000
    return g


# Table 1 rows -> (fixture, serialization budget ms, deserialization/access budget ms)
TABLE_1 = {
    "Node power profiling": (node_profile, 10.0, 100.0),
    "Component-level monitoring": (component_sample, 5.0, 150.0),
    "Thermal monitoring": (thermal_scan, 20.0, 500.0),
    "Infrastructure status": (facility_status, 30.0, 1000.0),
    "External coordination": (grid_update, 100.0, 5000.0),
}

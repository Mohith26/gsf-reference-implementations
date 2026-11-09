"""Workload-to-cooling intent signaling over the WDPC data bus.

A training job publishes a WorkloadDataPublication whose future_intent lists
upcoming power steps. A cooling controller and a power monitor subscribe by
ticker; each prints how much warning it received before every step. The
script then measures the per-message cost of the envelope (wrap + HMAC +
verify + decode) to show where time goes on the bus path.

    python examples/intent_signal_demo.py
"""

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wdpc_ref.bus import DataBus, Publisher, Verifier
from wdpc_ref.fixtures import component_sample, workload_publication

KEYS = {
    "train-llm-70b-run42": b"demo-key-workload-0000000000000",
    "gpu-telemetry": b"demo-key-telemetry-00000000000",
}


def main() -> int:
    bus = DataBus(Verifier(KEYS))
    received = []

    def cooling(topic, env, msg):
        sent = env.timestamp.ToNanoseconds()
        for sig in msg.future_intent:
            lead_s = (sig.predicted_time.ToNanoseconds() - sent) / 1e9
            received.append((topic, sig.predicted_power_mw, lead_s))

    bus.subscribe("WDPC.fac1.workload.>", cooling)
    bus.subscribe("WDPC.fac1.*.train-llm-70b-run42", lambda t, e, m: None)

    wl = workload_publication(intents=6)
    pub = Publisher("train-llm-70b-run42", KEYS["train-llm-70b-run42"])
    # Re-stamp the fixture to "now" so the freshness check passes.
    base = time.time_ns()
    shift = base - wl.timestamp.ToNanoseconds()
    wl.timestamp.FromNanoseconds(base)
    for sig in wl.future_intent:
        sig.predicted_time.FromNanoseconds(sig.predicted_time.ToNanoseconds() + shift)
    delivered = bus.publish("WDPC.fac1.workload.train-llm-70b-run42",
                            pub.wrap(wl, "WORKLOAD_DATA"))
    print(f"delivered to {delivered} subscribers, rejected {len(bus.rejected)}")
    for topic, mw, lead in received:
        print(f"  cooling saw step to {mw:5.1f} MW with {lead:4.1f} s warning")

    # Envelope cost per message (component telemetry, the 100 ms data type).
    tele = Publisher("gpu-telemetry", KEYS["gpu-telemetry"])
    v = Verifier(KEYS)
    sample = component_sample()
    n, runs = 2000, 5
    per = []
    for _ in range(runs):
        t0 = time.perf_counter_ns()
        for _ in range(n):
            env = tele.wrap(sample, "COMPONENT_METRICS")
            v.verify(env)
            Verifier.open(env)
        per.append((time.perf_counter_ns() - t0) / n / 1000)
    med = statistics.median(per)
    print(f"envelope wrap+HMAC+verify+decode: {med:.1f} us/message median "
          f"(~{1e6 / med:,.0f} messages/s on one Python thread)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

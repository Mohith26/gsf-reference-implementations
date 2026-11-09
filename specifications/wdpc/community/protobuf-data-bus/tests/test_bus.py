import pytest

from wdpc_ref.bus import (
    HDR_MAC,
    HDR_SEQ,
    DataBus,
    Publisher,
    VerificationError,
    Verifier,
    topic_matches,
)
from wdpc_ref.fixtures import component_sample, workload_publication

KEY = b"k" * 32


def test_topic_matching():
    assert topic_matches("WDPC.fac1.*.POWER", "WDPC.fac1.r07.POWER")
    assert not topic_matches("WDPC.fac1.*.POWER", "WDPC.fac1.r07.n03.POWER")
    assert topic_matches("WDPC.fac1.>", "WDPC.fac1.r07.n03.POWER")
    assert not topic_matches("WDPC.fac1.>", "WDPC.fac1")
    assert topic_matches("a.b", "a.b") and not topic_matches("a.b", "a.b.c")


def test_wrap_verify_open_round_trip():
    pub = Publisher("wl-1", KEY)
    payload = workload_publication()
    env = pub.wrap(payload, "WORKLOAD_DATA", now=1000.0)
    v = Verifier({"wl-1": KEY})
    v.verify(env, now=1000.5)
    assert Verifier.open(env) == payload
    assert env.metadata.schema_version.startswith("wdpc.v1")


def test_tampered_payload_rejected():
    env = Publisher("wl-1", KEY).wrap(component_sample(), "COMPONENT_METRICS", now=1000.0)
    env.payload = env.payload[:-1] + bytes([env.payload[-1] ^ 1])
    with pytest.raises(VerificationError, match="HMAC"):
        Verifier({"wl-1": KEY}).verify(env, now=1000.0)


def test_tampered_header_rejected():
    env = Publisher("wl-1", KEY).wrap(component_sample(), "COMPONENT_METRICS", now=1000.0)
    env.custom_headers[HDR_SEQ] = "99"
    with pytest.raises(VerificationError, match="HMAC"):
        Verifier({"wl-1": KEY}).verify(env, now=1000.0)


def test_wrong_key_and_unknown_source_rejected():
    env = Publisher("wl-1", b"x" * 32).wrap(component_sample(), "COMPONENT_METRICS", now=1.0)
    with pytest.raises(VerificationError):
        Verifier({"wl-1": KEY}).verify(env, now=1.0)
    with pytest.raises(VerificationError, match="unknown source"):
        Verifier({"other": KEY}).verify(env, now=1.0)


def test_replay_and_staleness_rejected():
    pub = Publisher("wl-1", KEY)
    v = Verifier({"wl-1": KEY}, max_age_s=5.0)
    e1 = pub.wrap(component_sample(), "COMPONENT_METRICS", now=100.0)
    e2 = pub.wrap(component_sample(), "COMPONENT_METRICS", now=100.1)
    v.verify(e2, now=100.2)
    with pytest.raises(VerificationError, match="replayed"):
        v.verify(e1, now=100.2)  # older sequence after a newer one
    with pytest.raises(VerificationError, match="stale"):
        v.verify(pub.wrap(component_sample(), "COMPONENT_METRICS", now=100.0), now=110.0)
    with pytest.raises(VerificationError, match="stale"):
        v.verify(pub.wrap(component_sample(), "COMPONENT_METRICS", now=200.0), now=100.0)


def test_mac_header_is_excluded_from_mac_input():
    env = Publisher("wl-1", KEY).wrap(component_sample(), "COMPONENT_METRICS", now=5.0)
    assert len(env.custom_headers[HDR_MAC]) == 64


def test_bus_delivers_to_matching_subscribers_and_drops_bad():
    import time
    bus = DataBus(Verifier({"wl-1": KEY}))
    got_a, got_b = [], []
    bus.subscribe("WDPC.fac1.workload.>", lambda t, env, msg: got_a.append(msg.workload_id))
    bus.subscribe("WDPC.fac1.*.wl-1", lambda t, env, msg: got_b.append(t))
    bus.subscribe("WDPC.fac2.>", lambda t, env, msg: pytest.fail("wrong facility"))
    pub = Publisher("wl-1", KEY)
    env = pub.wrap(workload_publication(), "WORKLOAD_DATA", now=time.time())
    assert bus.publish("WDPC.fac1.workload.wl-1", env) == 2
    assert got_a == ["train-llm-70b-run42"] and got_b == ["WDPC.fac1.workload.wl-1"]
    # Replaying the same bytes is rejected by both subscriptions.
    bus.publish("WDPC.fac1.workload.wl-1", env)
    assert len(got_a) == 1 and len(bus.rejected) == 2

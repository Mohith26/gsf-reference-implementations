"""A minimal in-process WDPC central data bus.

Implements the parts of the spec that are about data movement rather than a
specific broker:

* every payload travels inside the Annex A ``WDPCMessage`` envelope;
* message authentication from the "Security requirements" section:
  HMAC-SHA256 integrity, per-source sequence numbers against replay, and a
  timestamp freshness window;
* topics ("ticker symbols") with ``*`` and ``>`` wildcards so any component
  can publish and any other can subscribe, with no intermediary.

The spec names Kafka, Pulsar and MQTT Sparkplug B as transports. This module
is a transport-neutral reference: ``InMemoryTransport`` can be swapped for a
broker client implementing ``publish(topic, bytes)``.

Spec gap: ``WDPCMessage`` has no field for an HMAC, a signature or a sequence
number, although the Security section requires all three. This
implementation carries them in ``custom_headers`` (field 17) under the
``wdpc-`` prefix and documents that choice in METHODOLOGY.md.
"""

from __future__ import annotations

import hashlib
import hmac
import itertools
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .schema import load

HDR_SEQ = "wdpc-seq"
HDR_MAC = "wdpc-hmac-sha256"
HDR_TYPE = "wdpc-payload-type"
SCHEMA_VERSION = "wdpc.v1/1.0.0"


class VerificationError(Exception):
    """Raised when an envelope fails integrity, replay or freshness checks."""


def _mac_input(env) -> bytes:
    """Canonical bytes covered by the HMAC: the envelope minus the MAC header."""
    clone = type(env)()
    clone.CopyFrom(env)
    if HDR_MAC in clone.custom_headers:
        del clone.custom_headers[HDR_MAC]
    return clone.SerializeToString(deterministic=True)


def topic_matches(pattern: str, topic: str) -> bool:
    """Dot-separated ticker matching. ``*`` = one segment, ``>`` = the rest."""
    p, t = pattern.split("."), topic.split(".")
    for i, seg in enumerate(p):
        if seg == ">":
            return len(t) > i
        if i >= len(t) or (seg != "*" and seg != t[i]):
            return False
    return len(p) == len(t)


@dataclass
class Publisher:
    source_component_id: str
    key: bytes
    _seq: itertools.count = field(default_factory=lambda: itertools.count(1))

    def wrap(self, payload, message_type: str, now: float | None = None):
        s = load()
        env = s.WDPCMessage(message_id=str(uuid.uuid4()),
                            source_component_id=self.source_component_id)
        env.timestamp.FromNanoseconds(int((now if now is not None else time.time()) * 1e9))
        env.message_type = s.enum_value("MessageType", message_type)
        env.payload = payload.SerializeToString()
        env.metadata.schema_version = SCHEMA_VERSION
        env.custom_headers[HDR_TYPE] = payload.DESCRIPTOR.full_name
        env.custom_headers[HDR_SEQ] = str(next(self._seq))
        env.custom_headers[HDR_MAC] = hmac.new(self.key, _mac_input(env),
                                               hashlib.sha256).hexdigest()
        return env


@dataclass
class Verifier:
    keys: dict[str, bytes]
    max_age_s: float = 5.0
    max_skew_s: float = 1.0
    _last_seq: dict[str, int] = field(default_factory=dict)

    def verify(self, env, now: float | None = None):
        now = now if now is not None else time.time()
        key = self.keys.get(env.source_component_id)
        if key is None:
            raise VerificationError(f"unknown source {env.source_component_id!r}")
        mac = env.custom_headers.get(HDR_MAC, "")
        want = hmac.new(key, _mac_input(env), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, want):
            raise VerificationError("HMAC mismatch")
        age = now - env.timestamp.ToNanoseconds() / 1e9
        if age > self.max_age_s or age < -self.max_skew_s:
            raise VerificationError(f"stale or future-dated message (age {age:.3f}s)")
        try:
            seq = int(env.custom_headers[HDR_SEQ])
        except (KeyError, ValueError):
            raise VerificationError("missing sequence number") from None
        last = self._last_seq.get(env.source_component_id, 0)
        if seq <= last:
            raise VerificationError(f"replayed or out-of-order sequence {seq} <= {last}")
        self._last_seq[env.source_component_id] = seq
        return env

    @staticmethod
    def open(env):
        """Decode the payload into its declared message class."""
        s = load()
        name = env.custom_headers.get(HDR_TYPE, "").rsplit(".", 1)[-1]
        cls = getattr(s, name)
        msg = cls()
        msg.ParseFromString(env.payload)
        return msg


class InMemoryTransport:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[str, bytes], None]]] = defaultdict(list)

    def subscribe(self, pattern: str, fn: Callable[[str, bytes], None]) -> None:
        self._subs[pattern].append(fn)

    def publish(self, topic: str, data: bytes) -> int:
        delivered = 0
        for pattern, fns in list(self._subs.items()):
            if topic_matches(pattern, topic):
                for fn in fns:
                    fn(topic, data)
                    delivered += 1
        return delivered


class DataBus:
    """Central data bus: components publish envelopes and subscribe by ticker."""

    def __init__(self, verifier: Verifier, transport: InMemoryTransport | None = None):
        self.transport = transport or InMemoryTransport()
        self.verifier = verifier
        self.rejected: list[tuple[str, str]] = []

    def publish(self, topic: str, envelope) -> int:
        return self.transport.publish(topic, envelope.SerializeToString())

    def subscribe(self, pattern: str, handler: Callable[[str, object, object], None]) -> None:
        s = load()
        # Each subscription keeps its own replay window, so two subscribers
        # can both accept the same message.
        verifier = Verifier(self.verifier.keys, self.verifier.max_age_s,
                            self.verifier.max_skew_s)

        def on_bytes(topic: str, data: bytes) -> None:
            env = s.WDPCMessage()
            env.ParseFromString(data)
            try:
                verifier.verify(env)
            except VerificationError as e:
                self.rejected.append((topic, str(e)))
                return
            handler(topic, env, Verifier.open(env))

        self.transport.subscribe(pattern, on_bytes)

import importlib.util
import subprocess
import sys

import pytest

from wdpc_ref.schema import PROTO_PATH, SPEC_PATH, load, to_proto_text
from wdpc_ref.specparse import lint_file


def test_committed_proto_matches_generator():
    assert PROTO_PATH.read_text(encoding="utf-8") == to_proto_text(lint_file(SPEC_PATH))


@pytest.mark.skipif(importlib.util.find_spec("grpc_tools") is None,
                    reason="grpcio-tools not installed")
def test_proto_compiles_with_protoc(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "grpc_tools.protoc", f"-I{PROTO_PATH.parents[2]}",
         f"--python_out={tmp_path}", str(PROTO_PATH)],
        check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "wdpc" / "v1" / "wdpc_pb2.py").exists()


def test_every_spec_type_is_loadable():
    s = load()
    model = lint_file(SPEC_PATH)
    messages = {n for n, d in model.by_name().items() if d[0].kind == "message"}
    assert messages | set(model.undefined_types()) == set(s.names())
    assert set(s.enums) == {n for n, d in model.by_name().items() if d[0].kind == "enum"}


def test_annex_a_wins_for_future_intent():
    s = load()
    field = s.WorkloadDataPublication.DESCRIPTOR.fields_by_name["future_intent"]
    assert field.number == 7
    assert "dependencies" in s.WorkloadDataPublication.DESCRIPTOR.fields_by_name


def test_spec_field_numbers_preserved():
    s = load()
    f = s.FacilityStatus.DESCRIPTOR.fields_by_name
    assert (f["facility_id"].number, f["racks"].number, f["grid_interface"].number) == (1, 5, 16)
    assert f["facility_metadata"].message_type.GetOptions().map_entry


def test_round_trip_and_json():
    from google.protobuf import json_format
    s = load()
    m = s.ProcessorUnit(processor_id="gpu0", power_consumption_watts=712.5)
    m.timestamp.FromSeconds(1_780_000_000)
    again = s.ProcessorUnit.FromString(m.SerializeToString())
    assert again == m
    assert json_format.MessageToDict(m)["powerConsumptionWatts"] == 712.5


def test_placeholder_is_forward_compatible():
    """A v1 reader keeps fields a future spec adds to a placeholder type."""
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    s = load()
    future = descriptor_pb2.FileDescriptorProto(name="future.proto", package="future",
                                                syntax="proto3")
    msg = future.message_type.add(name="ThermalMetrics")
    msg.field.add(name="coolant_temp_c", number=1, type=1, label=1)
    pool = descriptor_pool.DescriptorPool()
    cls = message_factory.GetMessageClass(pool.Add(future).message_types_by_name["ThermalMetrics"])
    data = cls(coolant_temp_c=41.5).SerializeToString()
    old = s.ThermalMetrics.FromString(data)
    assert old.SerializeToString() == data  # unknown field preserved byte for byte

from wdpc_ref.fixtures import TABLE_1, facility_status
from wdpc_ref.measure import measure


def test_fixtures_are_deterministic():
    for factory, _, _ in TABLE_1.values():
        assert factory().SerializeToString(deterministic=True) == \
            factory().SerializeToString(deterministic=True)


def test_facility_shape():
    f = facility_status()
    assert len(f.racks) == 4 and all(len(r.nodes) == 8 for r in f.racks)
    assert len({n.node_id for r in f.racks for n in r.nodes}) == 32


def test_table_1_serialization_budgets_met():
    for row, (factory, ser_budget, access_budget) in TABLE_1.items():
        m = measure(factory(), loops=5, runs=3)
        assert m["ser_ms_protobuf"] < ser_budget, row
        assert m["de_ms_protobuf"] < access_budget, row
        assert m["bytes_protobuf"] < m["bytes_json"], row

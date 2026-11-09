from wdpc_ref.schema import SPEC_PATH
from wdpc_ref.specparse import extract_blocks, lint, lint_file, summary


def codes(model):
    return summary(model)


def test_spec_v1_findings_are_stable():
    model = lint_file(SPEC_PATH)
    assert len(model.blocks) == 17
    assert len(model.by_name()) == 38
    assert len(model.undefined_types()) == 61
    s = codes(model)
    assert s["CONFLICTING_FIELD_NUMBER"] == 1
    assert s["UNCLOSED_DEFINITION"] == 1
    assert s["UNTERMINATED_BLOCK"] == 1
    assert s["ENUM_ZERO_IS_MEANINGFUL"] == 6


def test_detects_future_intent_wire_conflict():
    model = lint_file(SPEC_PATH)
    conflicts = [f for f in model.findings if f.code == "CONFLICTING_FIELD_NUMBER"]
    assert conflicts[0].subject == "WorkloadDataPublication.future_intent"
    assert "= 16" in conflicts[0].detail and "= 7" in conflicts[0].detail


def test_truncated_annex_is_reported():
    model = lint_file(SPEC_PATH)
    trunc = [f for f in model.findings if f.code == "TRUNCATED_FIELD"]
    assert trunc and trunc[0].subject == "PowerSystemStatus"


def test_parses_maps_repeated_and_comments():
    text = """# S
```protobuf
message A {
  string id = 1;              // comment = 9;
  repeated B items = 2;
  map<string, double> m = 17;
}
message B { }
```
"""
    # "message B { }" on one line is not in the spec's style; B is undefined here.
    model = lint(text)
    a = model.by_name()["A"][0]
    assert [(f.name, f.number) for f in a.fields] == [("id", 1), ("items", 2), ("m", 17)]
    assert a.fields[1].repeated and a.fields[2].map_value == "double"
    assert model.undefined_types() == ["B"]


def test_clean_schema_has_no_errors():
    text = """## x
```protobuf
message A {
  string id = 1;
  Kind kind = 2;
}
enum Kind {
  KIND_UNSPECIFIED = 0;
  KIND_X = 1;
}
```
"""
    model = lint(text)
    assert model.findings == []


def test_duplicate_field_number_and_enum_conflict():
    text = """## x
```protobuf
message A {
  string a = 1;
  string b = 1;
}
enum E {
  E_UNSPECIFIED = 0;
}
```
## y
```protobuf
enum E {
  E_UNSPECIFIED = 0;
  E_X = 1;
}
```
"""
    s = summary(lint(text))
    assert s == {"CONFLICTING_ENUM": 1, "DUPLICATE_FIELD_NUMBER": 1}


def test_heading_is_recorded_per_block():
    blocks = extract_blocks("## one\n```protobuf\n```\n### two.proto\n```protobuf\n```\n")
    assert [b.section for b in blocks] == ["one", "two.proto"]

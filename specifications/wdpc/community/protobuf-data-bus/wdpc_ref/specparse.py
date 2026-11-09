"""Extract and lint the protobuf definitions embedded in the WDPC specification.

The WDPC spec (WDPC-Spec.md) defines its data model as ```protobuf blocks
spread across the body and the normative Annex A. This module pulls those
blocks out, parses the small proto3 subset they use (messages, enums,
scalar / repeated / map fields) and reports problems that stop the schema
from being compiled or used on the wire as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SCALARS = {
    "double", "float", "int32", "int64", "uint32", "uint64", "sint32",
    "sint64", "fixed32", "fixed64", "sfixed32", "sfixed64", "bool",
    "string", "bytes",
}
WELL_KNOWN = {"google.protobuf.Timestamp": "google/protobuf/timestamp.proto"}

_FENCE_OPEN = re.compile(r"^```protobuf\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_MSG = re.compile(r"^\s*(message|enum)\s+(\w+)\s*\{\s*$")
_FIELD = re.compile(
    r"^\s*(?:(repeated)\s+)?(map<\s*(\w+)\s*,\s*([\w.]+)\s*>|[\w.]+)\s+(\w+)\s*=\s*(\d+)\s*;"
)
_ENUM_VAL = re.compile(r"^\s*(\w+)\s*=\s*(-?\d+)\s*;")
_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;")


@dataclass
class Field:
    name: str
    type: str
    number: int
    repeated: bool = False
    map_key: str | None = None
    map_value: str | None = None

    def referenced_types(self) -> list[str]:
        if self.map_key is not None:
            return [self.map_value] if self.map_value not in SCALARS else []
        return [self.type] if self.type not in SCALARS else []

    def signature(self) -> tuple:
        return (self.name, self.type, self.repeated, self.map_key, self.map_value)


@dataclass
class Definition:
    kind: str  # "message" | "enum"
    name: str
    block: int
    line: int
    section: str
    package: str | None = None
    fields: list[Field] = field(default_factory=list)
    values: list[tuple[str, int]] = field(default_factory=list)
    closed: bool = False


@dataclass
class Block:
    index: int
    start_line: int
    section: str
    lines: list[str]
    terminated: bool


@dataclass
class Finding:
    code: str
    severity: str  # "error" | "warning"
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} {self.subject}: {self.detail}"


def extract_blocks(text: str) -> list[Block]:
    """Return every ```protobuf block with the heading it appears under."""
    blocks: list[Block] = []
    section = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        h = _HEADING.match(lines[i])
        if h:
            section = h.group(2)
        if _FENCE_OPEN.match(lines[i]):
            start = i + 1
            body: list[str] = []
            i += 1
            terminated = False
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    terminated = True
                    break
                body.append(lines[i])
                i += 1
            blocks.append(Block(len(blocks), start + 1, section, body, terminated))
        i += 1
    return blocks


def parse_block(block: Block) -> tuple[list[Definition], list[Finding]]:
    defs: list[Definition] = []
    findings: list[Finding] = []
    package = None
    current: Definition | None = None
    for offset, raw in enumerate(block.lines):
        line = raw.split("//", 1)[0]
        lineno = block.start_line + offset
        if not line.strip():
            continue
        p = _PKG.match(line)
        if p:
            package = p.group(1)
            continue
        if current is None:
            m = _MSG.match(line)
            if m:
                current = Definition(m.group(1), m.group(2), block.index, lineno,
                                     block.section, package)
            continue
        if line.strip() == "}":
            current.closed = True
            defs.append(current)
            current = None
            continue
        if current.kind == "enum":
            ev = _ENUM_VAL.match(line)
            if ev:
                current.values.append((ev.group(1), int(ev.group(2))))
            else:
                findings.append(Finding("UNPARSEABLE", "error", current.name,
                                        f"line {lineno}: {raw.strip()!r}"))
            continue
        f = _FIELD.match(line)
        if f:
            if f.group(3):
                current.fields.append(Field(f.group(5), f.group(2).replace(" ", ""),
                                            int(f.group(6)), False, f.group(3), f.group(4)))
            else:
                current.fields.append(Field(f.group(5), f.group(2), int(f.group(6)),
                                            bool(f.group(1))))
        else:
            findings.append(Finding("TRUNCATED_FIELD", "error", current.name,
                                    f"line {lineno}: {raw.strip()!r} has no field number"))
    if current is not None:
        defs.append(current)
        findings.append(Finding("UNCLOSED_DEFINITION", "error", current.name,
                                f"{current.kind} starting at line {current.line} is never "
                                "closed (the block ends mid-definition)"))
    if not block.terminated:
        findings.append(Finding("UNTERMINATED_BLOCK", "error", f"block@{block.start_line}",
                                "```protobuf fence is never closed before end of document"))
    return defs, findings


@dataclass
class SpecModel:
    blocks: list[Block]
    definitions: list[Definition]
    findings: list[Finding]

    def by_name(self) -> dict[str, list[Definition]]:
        out: dict[str, list[Definition]] = {}
        for d in self.definitions:
            out.setdefault(d.name, []).append(d)
        return out

    def undefined_types(self) -> list[str]:
        known = set(self.by_name()) | set(WELL_KNOWN)
        missing = set()
        for d in self.definitions:
            for f in d.fields:
                for t in f.referenced_types():
                    if t not in known:
                        missing.add(t)
        return sorted(missing)


def lint(text: str) -> SpecModel:
    blocks = extract_blocks(text)
    defs: list[Definition] = []
    findings: list[Finding] = []
    for b in blocks:
        d, f = parse_block(b)
        defs.extend(d)
        findings.extend(f)
    model = SpecModel(blocks, defs, findings)

    for name, group in model.by_name().items():
        # Same message defined more than once with different wire layouts.
        if len(group) > 1 and group[0].kind == "message":
            base = {f.name: f for f in group[0].fields}
            for other in group[1:]:
                for f in other.fields:
                    b = base.get(f.name)
                    if b is not None and b.number != f.number:
                        findings.append(Finding(
                            "CONFLICTING_FIELD_NUMBER", "error", f"{name}.{f.name}",
                            f"= {b.number} at line {group[0].line} ({group[0].section}) but "
                            f"= {f.number} at line {other.line} ({other.section}); "
                            "the two definitions are not wire compatible"))
                only_a = sorted(set(base) - {f.name for f in other.fields})
                only_b = sorted({f.name for f in other.fields} - set(base))
                if only_a or only_b:
                    findings.append(Finding(
                        "DIVERGENT_DEFINITION", "warning", name,
                        f"line {group[0].line} vs line {other.line}: fields only in first "
                        f"{only_a}, only in second {only_b}"))
        if len(group) > 1 and group[0].kind == "enum":
            vals = {tuple(g.values) for g in group}
            if len(vals) > 1:
                findings.append(Finding("CONFLICTING_ENUM", "error", name,
                                        "enum is defined more than once with different values"))
        for d in group[:1]:
            if d.kind == "enum" and d.values:
                zero = [n for n, v in d.values if v == 0]
                if zero and not zero[0].endswith("UNSPECIFIED"):
                    findings.append(Finding(
                        "ENUM_ZERO_IS_MEANINGFUL", "warning", name,
                        f"proto3 default value is {zero[0]}, so an unset field reads as "
                        f"{zero[0]} (consider a *_UNSPECIFIED = 0 entry)"))
            if d.kind == "message":
                seen: dict[int, str] = {}
                for f in d.fields:
                    if f.number in seen:
                        findings.append(Finding("DUPLICATE_FIELD_NUMBER", "error", name,
                                                f"{seen[f.number]} and {f.name} both use {f.number}"))
                    seen[f.number] = f.name

    for t in model.undefined_types():
        users = sorted({f"{d.name}.{f.name}" for d in defs for f in d.fields
                        if t in f.referenced_types()})
        findings.append(Finding("UNDEFINED_TYPE", "error", t,
                                f"referenced by {', '.join(users)} but never defined"))
    model.findings = findings
    return model


def lint_file(path: str | Path) -> SpecModel:
    return lint(Path(path).read_text(encoding="utf-8"))


def summary(model: SpecModel) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in model.findings:
        counts[f.code] = counts.get(f.code, 0) + 1
    return dict(sorted(counts.items()))

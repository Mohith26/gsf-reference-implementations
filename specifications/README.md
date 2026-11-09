# Specifications

This directory holds reference implementations of
[Green Software Foundation specifications](https://greensoftware.foundation/specifications/)
applied to specific workload classes.

Each implementation demonstrates one possible way to apply a GSF
specification end-to-end on a concrete workload, with the methodology
choices made along the way documented in each project. The
implementations are educational starting points, not production
systems or recommended toolchains.

## Structure

```
specifications/
└── <specification>/
    ├── gsf/                   Implementations maintained by the GSF
    │   └── <workload>/        One implementation per workload class
    └── community/             Implementations maintained by the community
        └── <workload>/        One or more, contributed and stewarded by others
```

Each specification has its own subdirectory (e.g., `sci-for-ai/`).
Within each specification, implementations are split by **maintainer**:
work the foundation stewards lives under `gsf/`, and work the broader
community stewards lives under `community/`. Both are valuable; the
folder simply reflects who maintains the code.

Within `gsf/` or `community/`, individual implementations are named
after the **workload class** they cover (`llm-inference`,
`model-training`, `image-classification`, etc.), with optional
differentiators when multiple implementations of the same workload
class coexist (`llm-inference-batched`, `llm-inference-self-hosted`).

## Available specifications

| Specification | Description |
|---|---|
| [sci-for-ai](./sci-for-ai/) | [SCI for AI](https://sci-for-ai.greensoftware.foundation/) — extends SCI for AI-specific workload considerations |
| [wdpc](./wdpc/) | [Workload Dynamic Power and Cooling](https://github.com/Green-Software-Foundation/Workload-Dynamic-Power-and-Cooling) — data distribution between workloads, power and cooling |

Other GSF specifications will be added as implementations become
available.

## Contributing

See the top-level [CONTRIBUTING.md](../CONTRIBUTING.md) for the full
contribution process. Contributions implementing new GSF specifications,
or covering new workload classes for existing specifications, or
demonstrating alternative valid approaches to already-covered ground,
are all welcome.

Note: this directory holds implementations of **GSF specifications**.
Implementations of related sustainability standards from other
organisations are valuable but outside the scope of this repository,
and are typically best hosted by those communities directly.

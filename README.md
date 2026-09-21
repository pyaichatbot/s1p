# s1p

System 1 Router (S1Router) and System 1 Model (S1M): a local-model inference
router with calibrated acceptance, remote fallback, budgets/deadlines, and
service-level concurrency/rate limiting.

This repository is currently a single monorepo, checked in under the
[`S1Router/`](S1Router) directory, which contains **both** products as
packages:

| Product | Package | Purpose | Docs |
| --- | --- | --- | --- |
| S1Router | `S1Router/packages/router` (`s1router`) | Policy, routing, admission, acceptance gating | [intent](S1Router/docs/s1router/intent.md) · [design](S1Router/docs/s1router/design.md) · [spec](S1Router/docs/s1router/spec.md) |
| S1M | `S1Router/packages/model` (`s1m`) | Prediction/model lifecycle, artifacts, data curation, calibration, reporting | [intent](S1Router/docs/s1m/intent.md) · [design](S1Router/docs/s1m/design.md) · [spec](S1Router/docs/s1m/spec.md) |

Shared request/response contracts live in `S1Router/packages/contracts`
(`s1_contracts`); the wire format is defined once in the
[decision contract](S1Router/docs/contracts/decision-v1.md).

## Getting started

All commands run from the `S1Router/` directory:

```
cd S1Router
uv sync            # or: pip install -e . (see pyproject.toml)
make check          # lint, types, kanban, architecture, tooling coverage
make ci              # full product suite + release evidence gate
```

## Requirement traceability

Every product requirement is tracked by a stable ID in
[`S1Router/docs/traceability.json`](S1Router/docs/traceability.json) and
mapped to its implementing code and passing tests. The
[working contract](S1Router/AGENTS.md) and
[delivery controls](S1Router/docs/engineering/delivery.md) define how
requirements move from `planned` to `implemented`.

See [`S1Router/docs/README.md`](S1Router/docs/README.md) for the full
documentation index.

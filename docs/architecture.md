# Architecture

k8s-rightsizer-report is a single-file, minimal-dependency CLI. It queries
the Kubernetes metrics-server, applies a deterministic headroom model, and
renders a rightsizing report or patch YAML.

## Overview

```
metrics-server (kubectl top) ─▶ usage snapshot ─▶ headroom model ─▶ report / patch YAML / JSON
```

## Components

- **Metrics reader** — shells out to `kubectl top pods --containers` to collect
  point-in-time CPU and memory usage for all containers in a namespace.
- **Recommendation model** — applies configurable headroom multipliers
  (default: 1.4× CPU, 1.25× memory), rounds to sane steps (25m / 32Mi), and
  derives limits (2× CPU request, 1.5× memory request).
- **Renderer** — formats results as a Markdown table, patch YAML, or JSON
  depending on the requested output mode.

## Data flow

1. Query `kubectl top pods --containers -n <namespace>` for live usage.
2. Compare against current requests/limits from `kubectl get pods -o json`.
3. Apply headroom model to compute recommendations.
4. Render in the requested format (table / `--diff` / `--json`).

## Decisions

- **Minimal dependencies** (`pyyaml` only) — keeps install trivial.
- **Point-in-time snapshot** — deliberately simple; Prometheus percentile
  support is on the roadmap for more accurate long-running recommendations.
- **Explainable model** — the headroom multipliers are visible and adjustable,
  making recommendations easy to reason about and audit.

Record further significant choices here (or in a `docs/adr/` folder if they
pile up).

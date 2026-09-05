# Architecture

k8s-rightsizer-report is a single-file, minimal-dependency CLI. It queries
the Kubernetes metrics-server, applies a deterministic headroom model, and
renders a rightsizing report or patch YAML.

## Overview

```text
metrics-server (kubectl top) ─▶ usage snapshot ─▶ headroom model ─▶ report / patch YAML / JSON
```

## Components

- **Usage readers** — three interchangeable sources of the same
  `{pod: {container: {cpu, memory}}}` shape: `kubectl top pods --containers`
  (point-in-time, the default), a PromQL `quantile_over_time` p95 over a
  lookback window (`--prometheus`), and VerticalPodAutoscaler targets
  (`--vpa`).
- **Recommendation model** — applies configurable headroom multipliers
  (default: 1.4× CPU, 1.25× memory), rounds to sane steps (25m / 32Mi), and
  derives limits (2× CPU request, 1.5× memory request).
- **Renderer** — formats results as a Markdown table, patch YAML, or JSON
  depending on the requested output mode.

## Data flow

1. Query the selected usage source for per-container CPU and memory.
1. Compare against current requests from `kubectl get deployments,
   statefulsets, daemonsets -o json`, minus anything the exclude annotations
   opt out.
1. Apply headroom model to compute recommendations.
1. Render in the requested format (table / `--diff` / `--json`).

## Decisions

- **Minimal dependencies** (`pyyaml` only) — keeps install trivial.
- **Point-in-time snapshot by default** — deliberately simple; `--prometheus`
  swaps in a p95 over a lookback window when a point sample is not enough.
- **Explainable model** — the headroom multipliers are visible and adjustable,
  making recommendations easy to reason about and audit.

Record further significant choices here (or in a `docs/adr/` folder if they
pile up).

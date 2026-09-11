# Architecture

k8s-rightsizer-report is a single-file, minimal-dependency CLI. It does not
compute recommendations: [KRR](https://github.com/robusta-dev/krr) does that from
Prometheus history. This tool decides which of KRR's recommendations have settled
enough to propose, and renders those as a reviewable change.

## Overview

```text
krr simple --formatter json
        │
        ▼
   normalise ──▶ history/ (committed, one dated JSON per run)
                     │
                     ▼
              stability rule ──▶ proposed  ──▶ Kustomize patches / Helm values diff ──▶ PR
                                └▶ not yet — flapping (with its range)
```

## Components

- **Ingest** — reads `krr simple --formatter json` from a file, from stdin, or by
  running `krr` when it is on PATH (`--krr-arg` passes krr's own flags through).
  Normalises the `scans` list to one recommendation per workload container,
  keyed `namespace/kind/workload/container` so the same container is
  recognisable from one run to the next.
- **History** — each run is written to `.rightsizer/history/<timestamp>.json`.
  That directory is the entire state of the tool, and it is meant to be
  committed: the evidence lives in the same repository as the change it
  justifies.
- **Stability rule** — per dimension (`requests.cpu`, `requests.memory`,
  `limits.cpu`, `limits.memory`), the longest streak of recent consecutive runs
  whose proposals all sit within `--tolerance` of each other. At or above
  `--runs`, the recommendation is proposed; below it, it is reported as "not yet"
  with the range it has been moving over.
- **Emit** — Kustomize strategic-merge patches, one per workload, or an updated
  Helm values file rendered as a unified diff. `--pr` commits the change and the
  run file on a branch and opens a pull request with the `gh` CLI.

## Data flow

1. Obtain a KRR document (run krr, or read one).
1. Normalise it to per-workload-container recommendations.
1. Append it to the history directory (unless `--no-record`).
1. Classify every recommendation in the newest run against the runs before it.
1. Render the stable ones as patches or a values diff; report the rest, with
   their ranges, as "not yet".

## Decisions

- **KRR is the engine.** Instantaneous usage (metrics-server, `kubectl top`) is
  the wrong input for sizing, so the tool that used to read it does not any more.
  [Goldilocks](https://github.com/FairwindsOps/goldilocks) is the VPA-based
  alternative to KRR if you would rather not run Prometheus queries.
- **Stability is the product.** Applying KRR's output directly is one command;
  knowing which of its numbers to believe this week is the part that needs a
  tool. The rule is printed with every report, in the JSON, and in the pull
  request body — a reviewer should never have to guess why something was held
  back.
- **State is a committed directory.** No server, no database, no CRD, no
  cluster-side component. History that lives next to the manifests it argues
  about can be reviewed, reverted and blamed like anything else in the repo.
- **No `--apply`.** The tool proposes; the merge and the GitOps rollout apply.
  The flag is refused by name rather than left to fail as an unknown argument.
- **Minimal dependencies** (`pyyaml` only) — keeps install trivial. The cost is
  that a rewritten Helm values file comes back without its comments, which the
  output says out loud.

Record further significant choices here (or in a `docs/adr/` folder if they
pile up).

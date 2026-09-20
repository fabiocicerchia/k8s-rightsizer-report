# Basic Example

Turn a KRR scan into a stability-filtered set of proposed changes.

## Prerequisites

- [KRR](https://github.com/robusta-dev/krr) on PATH, pointed at a Prometheus that
  holds your cluster's usage history — or a saved `krr simple --formatter json`
  run to feed in
- `k8s-rightsizer-report` installed

## Run

```sh
# Run krr, record the run, print what is stable enough to propose:
k8s-rightsizer-report -n default

# Or ingest a run you already have:
krr simple --formatter json -n default > krr.json
k8s-rightsizer-report --krr-json krr.json

# JSON output (pipe to jq or feed a dashboard):
k8s-rightsizer-report -n default --json | jq '.proposed[].key'
```

## Expected output

```text
# Rightsizing — KRR recommendations, filtered for stability

Engine: KRR (robusta-dev/krr) · history: `.rightsizer/history` (3 runs)
Rule: a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs.

## Proposed (1)

| workload          | container | current req  | proposed req | current lim | proposed lim | stable for |
| ----------------- | --------- | ------------ | ------------ | ----------- | ------------ | ---------- |
| Deployment/api    | app       | 1000m/1024Mi | 118m/180Mi   | –/2048Mi    | –/180Mi      | 3 runs     |

## Not yet (1)

| workload          | container | why                | range over the last 3 runs    |
| ----------------- | --------- | ------------------ | ----------------------------- |
| Deployment/worker | app       | not yet — flapping | requests.cpu 60m–400m (+567%) |
```

followed by one Kustomize strategic-merge patch per proposed workload.

## The first two runs propose nothing

That is the rule working, not a failure: with fewer than three runs on record
every recommendation reads "not yet — 1 of 3 runs". Run it on a schedule, commit
`.rightsizer/history/`, and the numbers that hold still start coming through.

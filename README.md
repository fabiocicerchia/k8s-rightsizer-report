# k8s-rightsizer-report

[![CI](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Security](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/security.yml/badge.svg)](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/fabiocicerchia/k8s-rightsizer-report/badge)](https://securityscorecards.dev/viewer/?uri=github.com/fabiocicerchia/k8s-rightsizer-report)
[![CI carbon](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/fabiocicerchia/k8s-rightsizer-report/gh-pages/badge.json)](.github/workflows/carbon-badge.yml)
[![Release](https://img.shields.io/github/v/release/fabiocicerchia/k8s-rightsizer-report)](https://github.com/fabiocicerchia/k8s-rightsizer-report/releases)

**[KRR](https://github.com/robusta-dev/krr) is the engine. This adds stability
and the pull request.**

KRR reads Prometheus history and does the sizing maths. This tool does not size
anything: it records every KRR run in a directory you commit, proposes only the
recommendations that have *stopped moving*, and turns those into Kustomize
patches or a Helm values diff — and, with `--pr`, into a pull request someone
can actually review.

```console
$ k8s-rightsizer-report -n payments
# Rightsizing — KRR recommendations, filtered for stability

Engine: KRR (robusta-dev/krr) · history: `.rightsizer/history` (5 runs)
Rule: a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs.

## Proposed (1)

| workload          | container | current req  | proposed req | current lim | proposed lim | stable for |
| ----------------- | --------- | ------------ | ------------ | ----------- | ------------ | ---------- |
| Deployment/api    | app       | 1000m/1024Mi | 118m/180Mi   | –/2048Mi    | –/180Mi      | 4 runs     |

## Not yet (1)

| workload          | container | why                | range over the last 3 runs     |
| ----------------- | --------- | ------------------ | ------------------------------ |
| Deployment/worker | app       | not yet — flapping | requests.cpu 60m–400m (+567%)  |
```

## Why not just apply KRR's output

Because a recommendation computed this morning is not the same number it was
last week, and a pull request that halves a worker's CPU on a Tuesday and
doubles it on a Thursday teaches reviewers to stop reading. KRR is right about
the numbers; the missing piece is *when to believe one*.

So every run is recorded, and the rule is the product:

> a recommendation is proposed only once it has stayed within **15%** across
> **3 consecutive runs**

Anything still moving is reported as **not yet — flapping**, with the range it
has been moving over, so you can see why it was held back rather than take it on
trust. Both knobs are yours: `--tolerance` and `--runs`.

Prefer VPA to Prometheus history? [Goldilocks](https://github.com/FairwindsOps/goldilocks)
is the other option — it surfaces VPA recommendations in a dashboard.

## How it runs

```sh
# Run krr for you (it must be on PATH), record the run, print what is proposed:
k8s-rightsizer-report -n payments

# Or ingest a krr run you already have ('-' reads stdin):
krr simple --formatter json > krr.json
k8s-rightsizer-report --krr-json krr.json

# Pass krr's own flags straight through:
k8s-rightsizer-report -n payments --krr-arg -p --krr-arg http://prometheus:9090

# Open the pull request (needs the gh CLI, authenticated):
k8s-rightsizer-report -n payments --pr
```

There is no `--apply`. The cluster changes when the pull request merges and your
GitOps tooling rolls it out — not when this runs.

## State: the history directory

The only state is `.rightsizer/history/`, one dated JSON file per run, and it is
**meant to be committed**:

```text
.rightsizer/history/
├── 2026-08-25T06-00-11Z.json
├── 2026-09-01T06-00-09Z.json
└── 2026-09-08T06-00-14Z.json
```

No server, no database, no cluster-side component. The history is reviewable in
the same diff as the change it justifies, and `--pr` links the run that produced
each proposal.

## Output

**Kustomize strategic-merge patches** (the default), one per workload, matched by
kind, name and namespace:

```yaml
# payments-deployment-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: payments
spec:
  template:
    spec:
      containers:
        - name: app
          resources:
            requests:
              cpu: 118m
              memory: 180Mi
            limits:
              memory: 180Mi
```

A resource KRR deliberately leaves unset (it recommends no CPU limit) stays
unset — the patch proposes what KRR proposed, and nothing else.

**A Helm values diff** when you point at a values file:

```sh
k8s-rightsizer-report -n payments --helm-values charts/payments/values.yaml
```

It writes `<workload>.resources` when the chart has a subtree named after the
workload (or the container), or the top-level `resources` of a single-workload
chart. For anything else, say where:

```sh
--helm-key api/app=backend.api.resources
```

Note that `--write`/`--pr` rewrite the values file through PyYAML, which
normalises comments and formatting away. Review the diff.

## Install

```sh
pipx install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
```

Or with pip:

```sh
pip install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
```

You also need [KRR](https://github.com/robusta-dev/krr) — on PATH to have it run
for you, or just its JSON output to pass to `--krr-json`.

## Development

`make dev` then `make test` / `make lint`.

## Documentation

Full docs live in [`docs/`](docs/). Runnable examples live in [`examples/`](examples/).

## Support

Need help implementing this? [Get in touch](https://fabiocicerchia.it/contact).

## License

Apache 2.0 — see [LICENSE](LICENSE).

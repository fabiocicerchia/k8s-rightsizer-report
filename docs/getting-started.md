# Getting Started

## Prerequisites

- Python 3.10+
- [KRR](https://github.com/robusta-dev/krr) — on PATH to have it run for you, or
  just its JSON output (`krr simple --formatter json`) to pass in
- KRR itself needs a Prometheus that holds your cluster's usage history
- The [`gh` CLI](https://cli.github.com), authenticated, for `--pr`

## Install

```sh
pip install k8s-rightsizer-report
```

Or directly from source:

```sh
pipx install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
```

## Run

```sh
# Run krr, record the run, print what is stable enough to propose:
k8s-rightsizer-report -n production

# Ingest a krr run you already have ('-' reads stdin):
k8s-rightsizer-report --krr-json krr.json

# Pass krr's own flags through:
k8s-rightsizer-report -n production --krr-arg -p --krr-arg http://prometheus:9090

# JSON output, for a dashboard or another step in a pipeline:
k8s-rightsizer-report -n production --json
```

The first run proposes nothing, and says so: there is no history to be stable
against yet. That is the point — run it on a schedule (weekly is a sensible
cadence for a KRR window of a week or two) and commit the history directory. By
the third run, the recommendations that have held still start coming through.

## The stability rule

> a recommendation is proposed only once it has stayed within **15%** across
> **3 consecutive runs**

Tune it with `--tolerance PCT` and `--runs N`. A stricter rule (`--tolerance 5
--runs 5`) proposes less, later, and is harder to argue with; a looser one moves
faster. Everything that does not clear the rule is listed under "Not yet", with
the range it has been moving over:

```text
| workload          | container | why                | range over the last 3 runs    |
| Deployment/worker | app       | not yet — flapping | requests.cpu 60m–400m (+567%) |
```

A recommendation that simply has not been seen enough times yet reads
"not yet — 2 of 3 runs" instead.

## Commit the history

```sh
git add .rightsizer/history
git commit -m "chore(rightsizing): record run"
```

`.rightsizer/history/` is the tool's only state. Keep it in the repository: it is
what makes "this has been stable for four runs" a claim a reviewer can check.

## Open the pull request

```sh
k8s-rightsizer-report -n production --pr
```

This writes one Kustomize patch per stable workload under `.rightsizer/patches/`,
commits them together with the run file on a new branch, pushes, and opens a pull
request whose body carries, per workload: current versus proposed requests and
limits, how many runs it has been stable, the projected monthly saving when KRR
reports cost, and a link to the history file that backs it.

Use `--write` to produce the same files without opening anything, and `--branch`
to name the branch yourself.

## Helm charts

```sh
k8s-rightsizer-report -n production --helm-values charts/app/values.yaml
```

The values file is updated in place of patches, and the change is printed as a
unified diff. Where a chart does not spell the path obviously, point at it:

```sh
--helm-key api/app=backend.api.resources
```

With `--write` or `--pr`, the values file is rewritten through PyYAML, which
normalises comments and formatting away — review the diff before merging.

## What this will not do

There is no `--apply`, deliberately. The cluster changes when the pull request
merges and your GitOps tooling rolls it out.

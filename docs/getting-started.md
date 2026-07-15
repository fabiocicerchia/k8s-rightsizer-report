# Getting Started

## Prerequisites

- Python 3.10+
- `kubectl` configured against your cluster
- `metrics-server` installed and running in the cluster

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
# Human-readable rightsizing report for a namespace:
k8s-rightsizer-report -n production

# Output patch YAML ready to commit:
k8s-rightsizer-report -n production --diff > rightsizing-patch.yaml

# JSON output for dashboard ingestion:
k8s-rightsizer-report -n production --json
```

The report shows current requests, peak observed usage, and recommended
requests/limits per workload container, together with the percentage delta.
Commit the patch YAML to your repository and open a PR to apply the changes.

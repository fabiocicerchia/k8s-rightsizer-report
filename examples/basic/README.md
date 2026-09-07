# Basic Example

Generate a rightsizing report for a Kubernetes namespace using metrics-server.

## Prerequisites

- `kubectl` configured and pointing at a live cluster
- `metrics-server` running in the cluster (`kubectl top pods` must work)
- `k8s-rightsizer-report` installed

## Run

```sh
# Print a human-readable rightsizing report for the 'default' namespace:
k8s-rightsizer-report -n default

# Save a patch YAML you can commit and PR:
k8s-rightsizer-report -n default --diff > rightsizing-patch.yaml

# JSON output (pipe to jq or feed a dashboard):
k8s-rightsizer-report -n default --json | jq .
```

## Expected output

```text
| kind/workload/container | current req | peak usage | recommended req | Δ cpu |
| ----------------------- | ----------- | ---------- | --------------- | ----- |
| Deployment/api/app      | 1000m/1Gi   | 180m/210Mi | 250m/288Mi      | -75%  |
| Deployment/worker/main  | (unset)     | 350m/800Mi | 500m/1024Mi     | new   |
```

Every container with observed usage is listed; a container metrics-server has
no sample for is the only one left out.

# k8s-rightsizer-report

[![CI](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Security](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/security.yml/badge.svg)](https://github.com/fabiocicerchia/k8s-rightsizer-report/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/fabiocicerchia/k8s-rightsizer-report/badge)](https://securityscorecards.dev/viewer/?uri=github.com/fabiocicerchia/k8s-rightsizer-report)
[![CI carbon](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/fabiocicerchia/k8s-rightsizer-report/gh-pages/badge.json)](.github/workflows/carbon-badge.yml)
[![Release](https://img.shields.io/github/v/release/fabiocicerchia/k8s-rightsizer-report)](https://github.com/fabiocicerchia/k8s-rightsizer-report/releases)

Turns **metrics-server usage into PR-ready requests/limits changes**: a
human-readable rightsizing report, or patch YAML you can commit. Closes the
loop that VPA recommendations leave open — getting the numbers *into the repo*.

```console
$ k8s-rightsizer-report -n app
| kind/workload/container | current req | peak usage | recommended req | Δ cpu |
|---|---|---|---|---|
| Deployment/api/app     | 1000m/1Gi | 180m/210Mi | 250m/288Mi | -75% |
| Deployment/worker/main | (unset)   | 350m/800Mi | 500m/1024Mi | new |

$ k8s-rightsizer-report -n app --diff > rightsizing-patch.yaml   # commit this
```

Sizes Deployments, StatefulSets, and DaemonSets. Opt a workload or specific
containers (sidecars, agents) out via pod-template annotations:

```yaml
metadata:
  annotations:
    k8s-rightsizer-report/exclude: "true"                       # skip the whole workload
    k8s-rightsizer-report/exclude-containers: "istio-proxy,vault-agent"  # skip just these
```

## Model

`recommended request = peak observed usage × headroom` (1.4× CPU, 1.25×
memory), rounded to sane steps (25m / 32Mi); `limits = requests × 2 (CPU) /
1.5 (memory)`. Deliberately simple and explainable. The peak comes from
`kubectl top` by default, or from a PromQL p95 with `--prometheus`, or from
VerticalPodAutoscaler targets with `--vpa`.

## Install

```sh
pipx install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
```

Or with pip:

```sh
pip install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
```

## Usage

```sh
pipx install .
k8s-rightsizer-report -n production            # needs kubectl + metrics-server
k8s-rightsizer-report -n production --json     # feed dashboards
```

## Development

`make dev` then `make test` / `make lint`.

## Documentation

Full docs live in [`docs/`](docs/). Runnable examples live in [`examples/`](examples/).

## Support

Need help implementing this? [Get in touch](https://fabiocicerchia.it/contact).

## License

Apache 2.0 — see [LICENSE](LICENSE).

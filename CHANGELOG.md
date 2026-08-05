# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.1.0...v0.1.1) (2026-08-05)


### Bug Fixes

* declare Apache-2.0 consistently, matching LICENSE ([feb6cce](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/feb6cce56cc1650eca5ad9ca6ff9ad5b461bdf03))
* **pre-commit:** stop check-yaml failing on Helm templates and multi-doc manifests ([dfdc9be](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/dfdc9bec32029d62c7b4d6ae76c3d72aac7a445e))
* **security:** skip the SARIF upload on private repos ([663ad96](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/663ad96e081d583b3bbfc3e3b65378cd9ebe486b))

## [Unreleased]

## [0.1.0]

### Added

- Kubernetes rightsizing report generated from metrics-server usage data.
- Human-readable table output with current requests, peak usage, and recommended
  requests/limits per workload and container.
- Patch YAML output (`--diff`) ready to commit into the repository.
- Headroom-based recommendation model: 1.4× CPU, 1.25× memory, rounded to sane
  steps (25m / 32Mi); limits = requests × 2 (CPU) / 1.5 (memory).
- JSON output (`--json`) for dashboard ingestion.
- Namespace filtering (`-n`) to scope the report.

[Unreleased]: https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fabiocicerchia/k8s-rightsizer-report/releases/tag/v0.1.0

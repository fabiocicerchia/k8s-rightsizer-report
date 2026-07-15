# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

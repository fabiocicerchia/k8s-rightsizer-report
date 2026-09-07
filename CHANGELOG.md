# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1](https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.2.0...v0.2.1) (2026-08-29)

### Bug Fixes

- **prometheus:** require an http(s) scheme on --prometheus ([#47](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/47)) ([5026995](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/5026995059ac7a2805ba788763d5251cd32364bf))
- unblock quality and clear the Scorecard pinned-dependencies finding ([#49](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/49)) ([dab4349](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/dab4349046ac5bf1059555e33b56ae531954d609))

## [0.2.0](https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.1.2...v0.2.0) (2026-08-25)

### Features

- **docs:** build the docs site in Actions and drop Read the Docs ([#39](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/39)) ([0c0a8b8](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/0c0a8b8e1afbf96893d84f1c4fd2b2ea8cb004d3))

### Bug Fixes

- **ci:** compute the next release PR after the draft is published ([#36](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/36)) ([e3d66fa](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/e3d66fa0873cb7d2848636001d14e0fd78052c88))

## [0.1.2](https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.1.1...v0.1.2) (2026-08-13)

### Bug Fixes

- security and code-quality findings ([#26](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/26)) ([dbafba9](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/dbafba9979d381aad94a5900810b3d630dc29a49))

## [0.1.1](https://github.com/fabiocicerchia/k8s-rightsizer-report/compare/v0.1.0...v0.1.1) (2026-08-06)

### Bug Fixes

- declare Apache-2.0 consistently, matching LICENSE ([feb6cce](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/feb6cce56cc1650eca5ad9ca6ff9ad5b461bdf03))
- **pre-commit:** stop check-yaml failing on Helm templates and multi-doc manifests ([dfdc9be](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/dfdc9bec32029d62c7b4d6ae76c3d72aac7a445e))
- **security:** skip the SARIF upload on private repos ([663ad96](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/663ad96e081d583b3bbfc3e3b65378cd9ebe486b))

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

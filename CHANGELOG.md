# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 (2026-07-29)


### Features

* add --vpa to source recommendations from VPA CRs ([1f1a453](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/1f1a453a49f953a8e5d89d946042e35735c37b82))
* add GitHub Action opening a weekly rightsizing PR ([987e44f](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/987e44f94db783db058a9f7255e9079d6330ecd6))
* add install.sh one-liner installer ([088a6e3](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/088a6e33b3d3aaae76044707659d29877bae97d7))
* add Prometheus range queries as a usage source ([8c66148](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/8c66148bedb78eadee9139ea922b97620f9e1899))
* add StatefulSet/DaemonSet support and exclusion annotations ([d032682](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/d0326823d103874369a3f0cb62a64045ea42994f))


### Bug Fixes

* restore executable bit and drop stale noqa directive ([#14](https://github.com/fabiocicerchia/k8s-rightsizer-report/issues/14)) ([471b53c](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/471b53cb85eba172471346d4f6be77521a3eed90))


### Documentation

* add GitHub Pages site, trim completed roadmap items from README ([3369c82](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/3369c828beb35189ccc5258dbfc0b819225ebc81))
* add missing badges (security, scorecard, fossa) and install section ([7e99c75](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/7e99c75f26d5c7323038fe3ebb2a769a02cf5a88))
* add release badge ([064cb06](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/064cb0678ddae367cfa22e186f349528745869b4))
* remove the broken FOSSA badge ([18b64eb](https://github.com/fabiocicerchia/k8s-rightsizer-report/commit/18b64ebd28ac8cc7b0dabf278f128d0117f48506))

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

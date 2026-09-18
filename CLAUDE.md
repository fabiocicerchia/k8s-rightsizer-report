# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repo.

## Project

k8s-rightsizer-report is a single-file Python 3.10+ CLI (`k8s_rightsizer_report.py`,
entry point `k8s_rightsizer_report:main`). [KRR](https://github.com/robusta-dev/krr)
is the engine: it reads Prometheus history and computes the recommendations. This
tool records every KRR run in a committed history directory, proposes only the
recommendations that have stayed within a tolerance for N consecutive runs, and
emits Kustomize patches, a Helm values diff, or a pull request.

The stability rule is the product. It is deliberately visible in every output,
and there is deliberately no `--apply` — don't add one.

## Commands

```sh
make dev     # editable install with dev deps (pytest, ruff, build)
make test    # pytest -q
make lint    # ruff check .
make build   # python -m build
make help    # Show this help
make install # Install the package
```

## Tooling

- `make setup` installs the pre-commit hook, and that is the whole of it.
  Don't add a `.githooks/` directory: `core.hooksPath` replaces `.git/hooks/`
  wholesale, so setting it silently stops every pre-commit hook from running.
- Hooks are pinned by commit SHA with the tag in a trailing comment. A tag can
  be moved, a SHA cannot.
- CI runs this same `.pre-commit-config.yaml` through `pre-commit/action`, so
  what passes locally is what gates the pull request.

## Conventions

- Match existing style; don't reformat unrelated code. Ruff, line length 100.
- Runtime dependencies are minimal (`pyyaml`); avoid adding more without good reason.
- Update docs/ and examples/ with behavior changes. Don't hand-edit CHANGELOG.md
  or the pyproject version — release-please generates both from commit messages.
- Use Conventional Commits (`feat:`/`fix:`/…); they drive the release version bump.
- Never commit secrets; CI runs gitleaks/trivy. Keep `.env` out of git.
- Tests live in `tests/` and use pytest. Keep coverage meaningful.

## Guardrails

- Don't add heavy dependencies; prefer stdlib + the existing pyyaml.
- Don't touch generated files (`*.egg-info/`, caches) by hand.
- Ask before large refactors or destructive operations.

# GitHub Action Example

What it shows: a scheduled workflow that runs KRR, records the run in the
committed `.rightsizer/history/` directory, and opens a PR with the
recommendations that have stayed within 15% for three consecutive runs — no
manual step to remember to run, and no PR full of numbers that will have moved
again by Thursday.

## Run

Copy [`auto-pr.yml`](auto-pr.yml) into a consuming repo's
`.github/workflows/`. It uses the `gh` CLI already on GitHub-hosted runners.
You still need to give the runner cluster access and a Prometheus krr can query
(kubeconfig secret, OIDC to your cloud provider, a self-hosted runner already
inside the VPC — whatever this repo already uses) — that part is too
environment-specific to template.

## Note on the history directory

Most weeks the workflow opens no PR, because nothing new has settled. It still
commits the run to the default branch — and it does so even when a PR *was*
opened, because a run that only exists on a PR branch is lost if that PR is never
merged. A run that proposed nothing is one of the runs a later recommendation
will claim to have been stable across; losing it would reset every streak.

Two details in the workflow are load-bearing:

- `git add` before `git diff --cached --quiet`. A brand-new run file is
  untracked, and `git diff` does not see untracked files at all — checking with a
  plain `git diff` would silently never commit anything.
- `--krr-arg=-p`, not `--krr-arg -p`. A value starting with a dash needs the `=`
  or argparse reads it as a missing argument and exits 2, failing the job.

If krr scans nothing — a Prometheus outage, the wrong namespace — the tool exits
non-zero and records nothing, so the step fails loudly rather than quietly
resetting every streak in the history.

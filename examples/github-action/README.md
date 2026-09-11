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
commits the run: a run that proposes nothing is one of the runs a later
recommendation will claim to have been stable across. Losing it would reset
every streak.

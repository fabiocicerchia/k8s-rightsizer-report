# GitHub Action Example

What it shows: a scheduled workflow that runs `k8s-rightsizer-report --diff`
and opens a PR with the patch YAML whenever recommendations change — no
manual step to remember to run.

## Run

Copy [`auto-pr.yml`](auto-pr.yml) into a consuming repo's
`.github/workflows/`. It uses the `gh` CLI already on GitHub-hosted runners.
You still need to give the runner cluster access (kubeconfig secret, OIDC to
your cloud provider, a self-hosted runner already inside the VPC — whatever
this repo already uses) — that part is too environment-specific to template.

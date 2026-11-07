# Specifications of k8s-rightsizer-report

What this code does, one atomic Gherkin scenario per behaviour, read from the code by code-atlas.
Tags: `@verified` a test asserts it · `@inferred` read from the code only · `@gap` an entry point no test covers · `@human` written or amended by a person, never rewritten.

## Change generation
Turning proposed recommendations into changes ready to commit to a GitOps repository.

- **Helm values**: [Updating a Helm chart's values](change-generation/helm-values/helm-values.feature) (5)
- **Kustomize patches**: [Generating Kustomize patches](change-generation/kustomize-patches/kustomize-patches.feature) (5)
- **Writing changes**: [Writing changes only when asked](change-generation/writing-changes/writing-changes.feature) (3)

## Change review
Getting proposed changes in front of humans for approval rather than applying them.

- **No direct apply**: [Refusing to apply changes to the cluster](change-review/no-direct-apply/no-direct-apply.feature) (1)
- **Pull request description**: [Explaining the change in the pull request](change-review/pull-request-description/pull-request-description.feature) (3)
- **Pull requests**: [Opening a pull request for review](change-review/pull-requests/pull-requests.feature) (5)

## Installation and developer tooling
Installing the tool and the build, test and quality tasks used to develop it.

- **Installation**: [Installing the CLI with the one-line installer](developer-tooling/installation/one-line-installer.feature) (2)

## Recommendation intake
Getting KRR's resource recommendations into the tool, whether by running KRR or reading its saved output.

- **Live KRR scan**: [Scanning the cluster with KRR](recommendation-intake/live-krr-scan/live-krr-scan.feature) (3)
- **Namespace scoping**: [Scoping a run to one namespace](recommendation-intake/namespace-scoping/namespace-scoping.feature) (3)
- **Resource quantities**: [Reading and writing CPU and memory quantities](recommendation-intake/resource-quantities/resource-quantities.feature) (2)
- **Saved KRR output**: [Reading saved KRR output](recommendation-intake/saved-krr-output/saved-krr-output.feature) (4)
- **Scan errors**: [Guarding the history against failed scans](recommendation-intake/scan-errors/scan-errors.feature) (2)

## Reporting
Showing people and machines what is proposed, what is held, and what it is worth.

- **Cost savings**: [Estimating the monthly saving](reporting/cost-savings/cost-savings.feature) (3)
- **JSON output**: [Machine-readable results](reporting/json-output/json-output.feature) (2)
- **Rightsizing report**: [Reading the rightsizing report](reporting/rightsizing-report/rightsizing-report.feature) (2)

## Run history
A committed, append-only record of every KRR run that the stability rule is judged against.

- **Reading history**: [Reading the run history](run-history/reading-history/reading-history.feature) (1)
- **Recording runs**: [Recording every run as evidence](run-history/recording-runs/recording-runs.feature) (4)
- **Workload identity**: [Recognising the same container across runs](run-history/workload-identity/workload-identity.feature) (2)

## Stability rule
Decides which recommendations are trustworthy enough to propose: only those that stayed within a tolerance for N consecutive runs.

- **Consecutive runs**: [Requiring consecutive stable runs](stability-rule/consecutive-runs/consecutive-runs.feature) (5)
- **Held recommendations**: [Explaining recommendations that are held back](stability-rule/held-recommendations/held-recommendations.feature) (2)
- **Limit conflicts**: [Holding back proposals that would break request and limit rules](stability-rule/limit-conflicts/limit-conflicts.feature) (3)
- **Tolerance**: [Deciding whether a recommendation has changed](stability-rule/tolerance/stability-tolerance.feature) (3)

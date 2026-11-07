@domain:change-generation @area:helm-values @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Updating a Helm chart's values
  Lets teams that deploy with Helm receive the proposals as a values-file diff instead of Kustomize patches.

  Background:
    Given prod/Deployment/api/app is proposed at 100m CPU and 100Mi memory

  @id:change-generation.helm-values.001 @rule:change-generation.helm-values.located-by-name @verified @source:k8s_rightsizer_report.py#values_path @test:tests/test_rightsizer.py#test_helm_values_diff_sets_resources_under_the_workload_key
  Scenario Outline: Resources are placed under the container's or workload's block in the values file
    Given values.yaml has a top-level `<block>` mapping
    When the operator runs the rightsizer with `--helm-values values.yaml`
    Then a unified diff of values.yaml is printed, setting `<block>.resources.requests` to cpu 100m and memory 100Mi
    And other keys under `<block>` are unchanged

    Examples:
      | block |
      | api   |
      | app   |

  @id:change-generation.helm-values.002 @rule:change-generation.helm-values.explicit-key-mapping @verified @source:k8s_rightsizer_report.py#parse_helm_keys @test:tests/test_rightsizer.py#test_helm_key_points_at_a_path_the_chart_does_not_spell_obviously
  Scenario: An explicit key mapping says where a workload's resources live
    Given values.yaml has `backend.api` but no top-level api or app block
    When the operator runs the rightsizer with `--helm-values values.yaml --helm-key api/app=backend.api.resources`
    Then the diff sets `backend.api.resources.requests.cpu` to 100m
    And nothing is skipped

  @id:change-generation.helm-values.003 @rule:change-generation.helm-values.unplaceable-warned @verified @source:k8s_rightsizer_report.py#helm_values_update @test:tests/test_rightsizer.py#test_helm_reports_a_workload_it_cannot_place @test:tests/test_rightsizer.py#test_helm_never_guesses_the_top_level_resources_of_a_chart
  Scenario: A proposal with no place in the values file is skipped with a hint
    Given values.yaml has a top-level `resources` block and no api or app block
    When the operator runs the rightsizer with `--helm-values values.yaml`
    Then values.yaml is not changed and no diff is printed
    And stderr shows `warning: prod/Deployment/api/app not written to values.yaml (no place found for it) — say where with --helm-key=api/app=some.dotted.path`

  @id:change-generation.helm-values.004 @rule:change-generation.helm-values.colliding-containers-skipped @verified @source:k8s_rightsizer_report.py#helm_values_update @test:tests/test_rightsizer.py#test_helm_skips_sidecars_that_resolve_to_one_workloads_path
  Scenario: Containers that would share one values path are all skipped
    Given Deployment api has proposed containers app and sidecar
    And values.yaml has an `api` block only
    When the operator runs the rightsizer with `--helm-values values.yaml`
    Then neither container is written
    And each is reported as skipped because `2 containers resolve to api.resources`

  @id:change-generation.helm-values.005 @rule:change-generation.helm-values.malformed-key-refused @verified @source:k8s_rightsizer_report.py#parse_helm_keys @test:tests/test_rightsizer.py#test_parse_helm_keys_rejects_a_malformed_mapping
  Scenario Outline: A malformed key mapping is refused
    Given values.yaml exists
    When the operator runs the rightsizer with `--helm-values values.yaml --helm-key <entry>`
    Then stderr shows `error: --helm-key wants WORKLOAD[/CONTAINER]=DOTTED.PATH, got '<entry>'`
    And the command exits with status 1

    Examples:
      | entry          |
      | api.resources  |
      | =api.resources |
      | api=           |

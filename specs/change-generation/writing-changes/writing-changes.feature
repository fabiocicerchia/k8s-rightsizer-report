@domain:change-generation @area:writing-changes @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Writing changes only when asked
  Keeps the working tree untouched on an ordinary run, so the operator decides when generated changes land on disk.

  @id:change-generation.writing-changes.001 @rule:change-generation.writing-changes.dry-run-by-default @verified @source:k8s_rightsizer_report.py#_emit_kustomize @test:tests/test_rightsizer.py#test_end_to_end_dry_run_prints_the_patches
  Scenario: By default the change is only previewed
    Given prod/Deployment/api/app has been stable for 3 runs
    When the operator runs the rightsizer with no write option
    Then the report and the patch for api are printed
    And no patch directory is created
    And only the history gains a file

  @id:change-generation.writing-changes.002 @rule:change-generation.writing-changes.write-patch-files @verified @source:k8s_rightsizer_report.py#write_patches @test:tests/test_rightsizer.py#test_write_puts_one_patch_file_per_workload_on_disk
  Scenario Outline: Asking to write puts one patch file per workload in the patch directory
    Given Deployments api and worker in prod have been stable for 3 runs
    When the operator runs the rightsizer with `<option> --patch-dir patches`
    Then `patches/prod-deployment-api.yaml` and `patches/prod-deployment-worker.yaml` exist
    And each names its workload and namespace prod

    Examples:
      | option  |
      | --write |
      | --pr    |

  @id:change-generation.writing-changes.003 @rule:change-generation.writing-changes.values-rewrite-normalised @inferred @source:k8s_rightsizer_report.py#_emit_helm
  Scenario: Writing a Helm values update rewrites the whole file and warns about it
    Given values.yaml has comments and an `api` block
    And prod/Deployment/api/app has been stable for 3 runs
    When the operator runs the rightsizer with `--helm-values values.yaml --write`
    Then values.yaml holds the new api resources
    And its comments and formatting are gone
    And stderr shows `warning: values.yaml was rewritten by PyYAML: comments and formatting are normalised — review the diff`

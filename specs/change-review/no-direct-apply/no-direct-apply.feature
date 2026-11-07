@domain:change-review @area:no-direct-apply @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Refusing to apply changes to the cluster
  Keeps every change going through review and GitOps by refusing the habit of applying directly.

  @id:change-review.no-direct-apply.001 @rule:change-review.no-direct-apply.apply-refused @verified @source:k8s_rightsizer_report.py#_RefuseApply @test:tests/test_rightsizer.py#test_apply_is_refused_with_a_reason
  Scenario: Asking to apply directly is refused with the reason
    Given the operator wants changes rolled out immediately
    When the operator runs the rightsizer with `--apply`
    Then stderr shows `--apply is deliberately not provided: this tool proposes changes for review. Merge the pull request and let your GitOps tooling roll it out.`
    And the command exits with status 2
    And nothing is scanned or recorded

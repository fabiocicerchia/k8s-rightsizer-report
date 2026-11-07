@domain:recommendation-intake @area:resource-quantities @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Reading and writing CPU and memory quantities
  Makes sure the numbers an operator reviews and merges are KRR's numbers in the units Kubernetes manifests use.

  @id:recommendation-intake.resource-quantities.001 @rule:recommendation-intake.resource-quantities.rounded-up-in-manifest-units @verified @source:k8s_rightsizer_report.py#fmt_resource @test:tests/test_rightsizer.py#test_units_round_up_so_a_rendering_never_proposes_less
  Scenario Outline: Proposed sizes are written in millicores and MiB, never below KRR's number
    Given KRR recommends <krr value> for <resource>
    When the operator runs the rightsizer and the recommendation is proposed
    Then the report and the patch show `<shown>`

    Examples:
      | resource | krr value          | shown |
      | cpu      | 0.0111 cores       | 12m   |
      | cpu      | 0.25 cores         | 250m  |
      | memory   | 100.5 MiB in bytes | 101Mi |
      | memory   | 100 MiB in bytes   | 100Mi |

  @id:recommendation-intake.resource-quantities.002 @rule:recommendation-intake.resource-quantities.quantity-strings-and-unknowns @verified @source:k8s_rightsizer_report.py#quantity @test:tests/test_rightsizer.py#test_normalise_tolerates_quantity_strings_and_unknowns
  Scenario Outline: Kubernetes quantity strings are understood and KRR's unknown is shown as unset
    Given KRR reports the current <field> as `<krr value>`
    When the operator runs the rightsizer
    Then the report shows that value as `<shown>`

    Examples:
      | field                   | krr value | shown |
      | cpu request             | 250m      | 250m  |
      | memory request          | 256Mi     | 256Mi |
      | memory request          | 1G        | 954Mi |
      | recommended cpu request | ?         | –     |

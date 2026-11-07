@domain:change-generation @area:kustomize-patches @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Generating Kustomize patches
  Turns the proposed recommendations into strategic-merge patches a GitOps repository can merge as-is.

  Background:
    Given Given every recommendation below has held steady for 3 runs

  @id:change-generation.kustomize-patches.001 @rule:change-generation.kustomize-patches.one-patch-per-workload @verified @source:k8s_rightsizer_report.py#kustomize_patches @test:tests/test_rightsizer.py#test_one_patch_per_workload_with_every_stable_container
  Scenario: Each workload gets one patch covering all its proposed containers
    Given Deployment api in prod has proposed containers app and sidecar
    And StatefulSet cache in prod has proposed container app
    When the operator runs the rightsizer
    Then two patches are produced: `prod-deployment-api.yaml` and `prod-statefulset-cache.yaml`
    And the api patch lists containers app and sidecar

  @id:change-generation.kustomize-patches.002 @rule:change-generation.kustomize-patches.only-what-krr-sized @verified @source:k8s_rightsizer_report.py#resources_block @test:tests/test_rightsizer.py#test_patches_carry_only_what_krr_sized
  Scenario: A patch sets only the sizes KRR proposed
    Given KRR proposes 100m CPU and 100Mi memory requests, a 100Mi memory limit and no CPU limit for prod/Deployment/api/app
    When the operator runs the rightsizer
    Then the patch for api sets requests cpu 100m, memory 100Mi and limits memory 100Mi
    And the patch sets no CPU limit
    And the patch names the Deployment api in namespace prod with apiVersion apps/v1

  @id:change-generation.kustomize-patches.003 @rule:change-generation.kustomize-patches.kind-shaped-patch @verified @source:k8s_rightsizer_report.py#workload_patch @test:tests/test_rightsizer.py#test_cronjob_patch_nests_the_pod_template_under_jobtemplate
  Scenario Outline: A patch carries the API version and pod template path of its workload kind
    Given a proposed recommendation for a <kind> named nightly
    When the operator runs the rightsizer
    Then its patch has apiVersion `<api version>`
    And the containers sit under `<template path>`

    Examples:
      | kind       | api version          | template path                       |
      | Deployment | apps/v1              | spec.template.spec                  |
      | CronJob    | batch/v1             | spec.jobTemplate.spec.template.spec |
      | Job        | batch/v1             | spec.template.spec                  |
      | Rollout    | argoproj.io/v1alpha1 | spec.template.spec                  |

  @id:change-generation.kustomize-patches.004 @rule:change-generation.kustomize-patches.held-container-left-out @verified @source:k8s_rightsizer_report.py#kustomize_patches @test:tests/test_rightsizer.py#test_a_flapping_container_stays_out_of_its_workload_patch
  Scenario: A held-back container stays out of its workload's patch
    Given in Deployment api, container app is steady but container sidecar went 20m, 300m, 20m
    When the operator runs the rightsizer
    Then the api patch lists only container app
    And sidecar is listed under `Not yet`

  @id:change-generation.kustomize-patches.005 @rule:change-generation.kustomize-patches.preview-multi-document-yaml @verified @source:k8s_rightsizer_report.py#render_patches @test:tests/test_rightsizer.py#test_render_patches_is_loadable_yaml
  Scenario: The patch preview is one YAML stream with each file named
    Given Deployments api and worker in prod are proposed
    When the operator runs the rightsizer without `--write`
    Then stdout shows `# prod-deployment-api.yaml` then its patch, `---`, then `# prod-deployment-worker.yaml` and its patch
    And the stream loads as YAML documents for api and worker

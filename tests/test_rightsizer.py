"""Fixture KRR runs -> stable / flapping classification -> patches.

The stability rule is the whole product, so most of what is asserted here is
"which recommendations does a sequence of runs let through, and why".
"""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

import k8s_rightsizer_report as m
from k8s_rightsizer_report import (
    Rule,
    classify,
    fmt_cpu,
    fmt_memory,
    kustomize_patches,
    load_history,
    normalise,
    parse_cpu,
    parse_memory,
    stability,
    within_tolerance,
)

MIB = 2**20
EPOCH = datetime(2026, 9, 1, 6, 0, 0, tzinfo=timezone.utc)


def krr_scan(
    workload: str = "api",
    container: str = "app",
    kind: str = "Deployment",
    namespace: str = "prod",
    *,
    cpu: float = 0.1,
    memory: float = 100 * MIB,
    current_cpu: float = 1.0,
    current_memory: float = 1024 * MIB,
    current_cpu_limit: float | None = None,
    cost: dict[str, float] | None = None,
) -> dict[str, object]:
    """One entry of `krr simple --formatter json`'s `scans` list."""
    scan: dict[str, object] = {
        "object": {
            "cluster": "staging",
            "name": workload,
            "container": container,
            "namespace": namespace,
            "kind": kind,
            "allocations": {
                "requests": {"cpu": current_cpu, "memory": current_memory},
                "limits": {"cpu": current_cpu_limit, "memory": current_memory * 2},
                "info": {},
            },
        },
        "recommended": {
            "requests": {
                "cpu": {"value": cpu, "severity": "CRITICAL"},
                "memory": {"value": memory, "severity": "WARNING"},
            },
            "limits": {
                "cpu": {"value": None, "severity": "GOOD"},
                "memory": {"value": memory, "severity": "WARNING"},
            },
            "info": {},
        },
        "severity": "CRITICAL",
    }
    if cost is not None:
        scan["cost"] = cost
    return scan


def krr_document(*scans: dict[str, object]) -> dict[str, object]:
    return {"scans": list(scans), "score": 71, "resources": ["cpu", "memory"], "errors": [], "strategy": {}}


def record(history_dir: Path, document: dict[str, object], index: int = 0) -> Path:
    """Record a run, one hour apart so the filenames sort as they happened."""
    when = EPOCH + timedelta(hours=index)
    return m.write_run(history_dir, m.as_run(normalise(document), "test", when), when)


# ----------------------------------------------------------------- ingestion


def test_normalise_reads_krr_values_and_allocations() -> None:
    recommendations = normalise(krr_document(krr_scan()))
    recommendation = recommendations["prod/Deployment/api/app"]
    assert recommendation["proposed"]["requests"] == {"cpu": 0.1, "memory": float(100 * MIB)}
    assert recommendation["current"]["requests"] == {"cpu": 1.0, "memory": float(1024 * MIB)}
    # KRR deliberately recommends no CPU limit; that stays unset rather than invented.
    assert recommendation["proposed"]["limits"]["cpu"] is None
    assert recommendation["severity"] == "CRITICAL"


def test_normalise_tolerates_quantity_strings_and_unknowns() -> None:
    scan = krr_scan()
    scan["object"]["allocations"]["requests"] = {"cpu": "250m", "memory": "256Mi"}  # type: ignore[index]
    scan["recommended"]["requests"]["cpu"] = {"value": "?", "severity": "UNKNOWN"}  # type: ignore[index]
    recommendation = normalise(krr_document(scan))["prod/Deployment/api/app"]
    assert recommendation["current"]["requests"] == {"cpu": 0.25, "memory": float(256 * MIB)}
    assert recommendation["proposed"]["requests"]["cpu"] is None


def test_normalise_filters_by_namespace() -> None:
    document = krr_document(krr_scan(namespace="prod"), krr_scan(workload="other", namespace="staging"))
    assert set(normalise(document, "staging")) == {"staging/Deployment/other/app"}


def test_parse_krr_output_skips_a_banner_before_the_json() -> None:
    text = "krr is scanning {this is not json}\n" + '{"scans": [], "score": 100}'
    assert m.parse_krr_output(text) == {"scans": [], "score": 100}


def test_parse_krr_output_rejects_output_with_no_document() -> None:
    with pytest.raises(m.RightsizerError, match="no krr JSON document"):
        m.parse_krr_output("krr: connection refused")


def test_parse_krr_output_rejects_json_that_is_not_a_krr_run() -> None:
    """Some other JSON object would read as a scan of nothing, which is exactly
    the run that must never be recorded."""
    with pytest.raises(m.RightsizerError, match="no krr JSON document"):
        m.parse_krr_output('{"error": "context deadline exceeded"}')


def test_a_scan_of_nothing_is_refused_rather_than_recorded(tmp_path: Path) -> None:
    """Prometheus down, wrong namespace, a selector that matched nothing: an
    empty scan is a failed observation, and recording it would break every
    streak in the history."""
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    with pytest.raises(m.RightsizerError, match="scanned nothing"):
        m.observed(krr_document())
    assert len(list(tmp_path.glob("*.json"))) == 3
    # The three good runs still stand, because the empty one never landed.
    proposed, _held = classify(load_history(tmp_path), Rule())
    assert [r["key"] for r in proposed] == ["prod/Deployment/api/app"]


# ------------------------------------------------------------------- history


def test_history_round_trips_runs_oldest_first(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(cpu=0.1 + index / 100)), index)
    runs = load_history(tmp_path)
    assert [run["recorded_at"] for run in runs] == [
        "2026-09-01T06:00:00Z",
        "2026-09-01T07:00:00Z",
        "2026-09-01T08:00:00Z",
    ]
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_two_runs_in_the_same_second_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """Overwriting a run would quietly shorten a streak, so the second one takes
    a suffix — and the suffix still sorts after the run it followed."""
    first = record(tmp_path, krr_document(krr_scan(cpu=0.1)), 0)
    second = m.write_run(tmp_path, m.as_run(normalise(krr_document(krr_scan(cpu=0.2))), "test", EPOCH), EPOCH)
    assert first != second
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [first.name, second.name]
    assert [
        run["recommendations"]["prod/Deployment/api/app"]["proposed"]["requests"]["cpu"]
        for run in load_history(tmp_path)
    ] == [0.1, 0.2]


def test_load_history_refuses_a_corrupt_run(tmp_path: Path) -> None:
    record(tmp_path, krr_document(krr_scan()))
    (tmp_path / "2026-09-02T06-00-00Z.json").write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(m.RightsizerError, match="not readable as a recorded run"):
        load_history(tmp_path)


# ----------------------------------------------------------------- stability


def test_within_tolerance_counts_small_moves_as_unchanged() -> None:
    assert within_tolerance([100.0, 110.0], 15)
    assert not within_tolerance([100.0, 120.0], 15)
    # A dimension KRR never sizes is stable; one that appears and disappears is not.
    assert within_tolerance([None, None], 15)
    assert not within_tolerance([None, 100.0], 15)


def test_three_steady_runs_are_proposed(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.100, 0.105, 0.110]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert [r["key"] for r in proposed] == ["prod/Deployment/api/app"]
    assert held == []
    assert proposed[0]["status"] == "stable for 3 runs"


def test_two_steady_runs_are_not_yet_proposed(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.100, 0.105]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert proposed == []
    assert held[0]["status"] == "not yet — 2 of 3 runs"


def test_an_oscillating_recommendation_is_reported_as_flapping(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.100, 0.400, 0.120, 0.500]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert proposed == []
    assert held[0]["status"] == "not yet — flapping"
    assert held[0]["stability"]["streak"] == 1
    # The range is the evidence: a reviewer can judge the verdict, not just take it.
    assert m.range_text(held[0]["stability"]).startswith("requests.cpu 120m–500m (+317%)")


def test_a_settled_recommendation_survives_an_old_swing(tmp_path: Path) -> None:
    """Three steady runs propose even when the history before them was wild."""
    for index, cpu in enumerate([0.900, 0.100, 0.100, 0.105, 0.108]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    assert proposed[0]["stability"]["streak"] == 4


def test_a_gap_in_the_history_breaks_the_streak(tmp_path: Path) -> None:
    """A workload that vanished and came back has not been stable across the gap."""
    record(tmp_path, krr_document(krr_scan(cpu=0.1)), 0)
    record(tmp_path, krr_document(), 1)  # workload absent from this scan
    record(tmp_path, krr_document(krr_scan(cpu=0.1)), 2)
    record(tmp_path, krr_document(krr_scan(cpu=0.1)), 3)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert proposed == []
    assert held[0]["status"] == "not yet — 2 of 3 runs"


def test_memory_flapping_holds_back_a_steady_cpu(tmp_path: Path) -> None:
    for index, memory in enumerate([100 * MIB, 100 * MIB, 400 * MIB]):
        record(tmp_path, krr_document(krr_scan(cpu=0.1, memory=memory)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert proposed == []
    assert "requests.memory 100Mi–400Mi" in m.range_text(held[0]["stability"])


def test_the_range_names_the_dimension_that_moved(tmp_path: Path) -> None:
    """A steady memory number should not bury the CPU number that is swinging."""
    for index, cpu in enumerate([0.1, 0.4, 0.1]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    _proposed, held = classify(load_history(tmp_path), Rule())
    assert m.range_text(held[0]["stability"]) == "requests.cpu 100m–400m (+300%)"


def test_tolerance_and_run_count_are_configurable(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.10, 0.15]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu)), index)
    assert classify(load_history(tmp_path), Rule(tolerance_pct=15, runs=3))[0] == []
    proposed, _held = classify(load_history(tmp_path), Rule(tolerance_pct=60, runs=2))
    assert [r["key"] for r in proposed] == ["prod/Deployment/api/app"]


def test_stability_of_an_unknown_key_is_zero() -> None:
    assert stability([], "prod/Deployment/ghost/app", Rule()) == {
        "runs_seen": 0,
        "streak": 0,
        "stable": False,
        "ranges": {},
    }


def test_a_request_above_an_existing_limit_is_held_back(tmp_path: Path) -> None:
    """KRR recommends no CPU limit by design, so a raised request under an
    existing lower limit would merge into a spec the API server rejects."""
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(cpu=0.12, current_cpu_limit=0.1)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert proposed == []
    assert held[0]["status"] == "not yet — cpu request 120m exceeds its 100m limit"
    # The recommendation is settled; it is the limit that blocks it.
    assert held[0]["stability"]["stable"] is True
    assert m.kustomize_patches(proposed) == []


def test_a_request_under_the_existing_limit_is_proposed(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(cpu=0.08, current_cpu_limit=0.1)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert (held, [r["conflicts"] for r in proposed]) == ([], [[]])


def test_a_flapping_number_reads_as_flapping_even_when_it_also_conflicts(tmp_path: Path) -> None:
    """Next week's number may not conflict at all, so the unsettled number is the
    story until it settles."""
    for index, cpu in enumerate([0.12, 0.40, 0.12]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu, current_cpu_limit=0.1)), index)
    _proposed, held = classify(load_history(tmp_path), Rule())
    assert held[0]["status"] == "not yet — flapping"
    assert held[0]["conflicts"] == ["cpu request 120m exceeds its 100m limit"]


def test_a_limit_krr_proposes_itself_settles_the_conflict(tmp_path: Path) -> None:
    """The check reads the limit that will be in force after the merge, not the
    one that happens to be set now."""
    scan = krr_scan(cpu=0.12, memory=100 * MIB, current_cpu_limit=0.1)
    scan["recommended"]["limits"]["cpu"] = {"value": 0.2, "severity": "OK"}  # type: ignore[index]
    for index in range(3):
        record(tmp_path, krr_document(scan), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    assert held == []
    assert proposed[0]["proposed"]["limits"]["cpu"] == 0.2


# -------------------------------------------------------------------- output


def test_patches_carry_only_what_krr_sized(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    (filename, patch), *rest = kustomize_patches(proposed)
    assert rest == []
    assert filename == "prod-deployment-api.yaml"
    assert patch == {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "api", "namespace": "prod"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "app",
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "100Mi"},
                                # No CPU limit: KRR proposes none, so the patch sets none.
                                "limits": {"memory": "100Mi"},
                            },
                        }
                    ]
                }
            }
        },
    }


def test_one_patch_per_workload_with_every_stable_container(tmp_path: Path) -> None:
    document = krr_document(
        krr_scan(container="app"),
        krr_scan(container="sidecar", cpu=0.02, memory=32 * MIB),
        krr_scan(workload="cache", kind="StatefulSet"),
    )
    for index in range(3):
        record(tmp_path, document, index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    patches = dict(kustomize_patches(proposed))
    assert set(patches) == {"prod-deployment-api.yaml", "prod-statefulset-cache.yaml"}
    containers = patches["prod-deployment-api.yaml"]["spec"]["template"]["spec"]["containers"]
    assert [container["name"] for container in containers] == ["app", "sidecar"]
    assert patches["prod-statefulset-cache.yaml"]["kind"] == "StatefulSet"


def test_a_flapping_container_stays_out_of_its_workload_patch(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.02, 0.30, 0.02]):
        record(tmp_path, krr_document(krr_scan(container="app"), krr_scan(container="sidecar", cpu=cpu)), index)
    proposed, held = classify(load_history(tmp_path), Rule())
    (_filename, patch), *_ = kustomize_patches(proposed)
    assert [c["name"] for c in patch["spec"]["template"]["spec"]["containers"]] == ["app"]
    assert [r["container"] for r in held] == ["sidecar"]


def test_cronjob_patch_nests_the_pod_template_under_jobtemplate(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(workload="nightly", kind="CronJob")), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    (_filename, patch), *_ = kustomize_patches(proposed)
    assert patch["apiVersion"] == "batch/v1"
    assert "containers" in patch["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def test_render_patches_is_loadable_yaml(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(), krr_scan(workload="worker")), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    documents = [doc for doc in yaml.safe_load_all(m.render_patches(kustomize_patches(proposed))) if doc]
    assert [doc["metadata"]["name"] for doc in documents] == ["api", "worker"]


def test_report_shows_the_rule_and_both_verdicts(tmp_path: Path) -> None:
    for index, cpu in enumerate([0.1, 0.1, 0.1]):
        record(tmp_path, krr_document(krr_scan(cpu=cpu), krr_scan(workload="worker", cpu=cpu * (index + 1))), index)
    runs = load_history(tmp_path)
    proposed, held = classify(runs, Rule())
    report = m.render_report(proposed, held, Rule(), tmp_path, len(runs))
    assert "stayed within 15% across 3 consecutive runs" in report
    assert "## Proposed (1)" in report
    assert "## Not yet (1)" in report
    assert "not yet — flapping" in report


def test_pr_body_links_the_history_file_and_counts_the_runs(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(cost={"current": 30.0, "recommended": 8.5})), index)
    runs = load_history(tmp_path)
    proposed, held = classify(runs, Rule())
    run_path = Path(".rightsizer/history/2026-09-01T08-00-00Z.json")
    body = m.render_pr_body(proposed, held, Rule(), m.Target("rightsizer/x", "acme/infra", run_path))
    assert "| 3 runs |" in body  # the stability streak, per container
    assert "1000m/1024Mi → 100m/100Mi" in body
    assert "**21.50/month**" in body
    assert f"https://github.com/acme/infra/blob/rightsizer/x/{run_path.as_posix()}" in body


def test_saving_is_dropped_when_krr_does_not_cost_the_workload(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    assert m.monthly_saving(proposed) is None


# ---------------------------------------------------------------- helm mode


def test_helm_values_diff_sets_resources_under_the_workload_key(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    values: dict[str, object] = {"api": {"replicaCount": 2, "resources": {"requests": {"cpu": "1", "memory": "1Gi"}}}}
    updated, written, unmatched = m.helm_values_update(values, proposed, {})
    assert written == ["api.resources"]
    assert unmatched == []
    assert updated["api"]["resources"]["requests"] == {"cpu": "100m", "memory": "100Mi"}
    assert updated["api"]["replicaCount"] == 2
    diff = m.helm_values_diff(Path("values.yaml"), values, updated)
    assert "-      cpu: '1'" in diff
    assert "+      cpu: 100m" in diff


def test_helm_key_points_at_a_path_the_chart_does_not_spell_obviously(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    values: dict[str, object] = {"global": {}, "backend": {"api": {}}}
    updated, written, unmatched = m.helm_values_update(values, proposed, {"api/app": "backend.api.resources"})
    assert (written, unmatched) == (["backend.api.resources"], [])
    assert updated["backend"]["api"]["resources"]["requests"]["cpu"] == "100m"


def test_helm_reports_a_workload_it_cannot_place(tmp_path: Path) -> None:
    for index in range(3):
        record(tmp_path, krr_document(krr_scan(), krr_scan(workload="worker")), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    _updated, written, skipped = m.helm_values_update({"api": {}}, proposed, {})
    assert written == ["api.resources"]
    assert [(r["workload"], why) for r, why in skipped] == [("worker", "no place found for it")]


def test_helm_never_guesses_the_top_level_resources_of_a_chart(tmp_path: Path) -> None:
    """Guessing from how many recommendations happened to be stable this run
    would write one workload's sizing into another's block, and would write
    somewhere different next week. --helm-key says it instead."""
    for index in range(3):
        record(tmp_path, krr_document(krr_scan()), index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    values: dict[str, object] = {"resources": {"requests": {"cpu": "2"}}, "worker": {}}
    updated, written, skipped = m.helm_values_update(values, proposed, {})
    assert (written, [why for _r, why in skipped]) == ([], ["no place found for it"])
    assert updated == values
    # ... and with the path spelled out, it lands exactly there.
    updated, written, skipped = m.helm_values_update(values, proposed, {"api/app": "resources"})
    assert (written, skipped) == (["resources"], [])
    assert updated["resources"]["requests"]["cpu"] == "100m"


def test_helm_skips_sidecars_that_resolve_to_one_workloads_path(tmp_path: Path) -> None:
    """Both containers guess `api.resources`; writing them in turn would keep
    whichever went last and report both as written."""
    document = krr_document(krr_scan(container="app", cpu=0.5), krr_scan(container="sidecar", cpu=0.05))
    for index in range(3):
        record(tmp_path, document, index)
    proposed, _held = classify(load_history(tmp_path), Rule())
    values: dict[str, object] = {"api": {"resources": {}}}
    updated, written, skipped = m.helm_values_update(values, proposed, {})
    assert written == []
    assert [why for _r, why in skipped] == ["2 containers resolve to api.resources"] * 2
    assert updated == values
    # Naming each container's path resolves it.
    _updated, written, skipped = m.helm_values_update(
        values, proposed, {"api/app": "api.resources", "api/sidecar": "api.sidecar.resources"}
    )
    assert (sorted(written), skipped) == (["api.resources", "api.sidecar.resources"], [])


def test_parse_helm_keys_rejects_a_malformed_mapping() -> None:
    assert m.parse_helm_keys(["api=api.resources"]) == {"api": "api.resources"}
    with pytest.raises(m.RightsizerError, match="WORKLOAD"):
        m.parse_helm_keys(["api.resources"])


# ----------------------------------------------------------------------- CLI


def test_apply_is_refused_with_a_reason() -> None:
    parser = m.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--apply"])


def test_end_to_end_dry_run_prints_the_patches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan())), encoding="utf-8")
    history = tmp_path / "history"
    for index in range(2):  # two prior runs, so this one is the third
        record(history, krr_document(krr_scan()), index)
    monkeypatch.chdir(tmp_path)

    exit_code = m.main(["--krr-json", str(krr_json), "--history-dir", str(history)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "## Proposed (1)" in out
    assert "kind: Deployment" in out
    assert "cpu: 100m" in out
    # The run was recorded: that is the state this tool keeps.
    assert len(list(history.glob("*.json"))) == 3
    # ... and nothing was written to the working tree without --write.
    assert not (tmp_path / ".rightsizer" / "patches").exists()


def test_no_record_leaves_the_history_alone_but_still_classifies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan())), encoding="utf-8")
    history = tmp_path / "history"
    for index in range(2):
        record(history, krr_document(krr_scan()), index)

    m.main(["--krr-json", str(krr_json), "--history-dir", str(history), "--no-record", "--json"])

    payload = m.json.loads(capsys.readouterr().out)
    assert len(list(history.glob("*.json"))) == 2
    assert payload["history_file"] is None
    assert [r["key"] for r in payload["proposed"]] == ["prod/Deployment/api/app"]
    assert payload["rule"] == {
        "tolerance_pct": 15.0,
        "runs": 3,
        "description": "a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs",
    }


def test_write_puts_one_patch_file_per_workload_on_disk(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan(), krr_scan(workload="worker"))), encoding="utf-8")
    history = tmp_path / "history"
    for index in range(2):
        record(history, krr_document(krr_scan(), krr_scan(workload="worker")), index)
    patches = tmp_path / "patches"

    m.main(
        ["--krr-json", str(krr_json), "--history-dir", str(history), "--patch-dir", str(patches), "--write"],
    )
    capsys.readouterr()

    assert sorted(path.name for path in patches.glob("*.yaml")) == [
        "prod-deployment-api.yaml",
        "prod-deployment-worker.yaml",
    ]
    patch = yaml.safe_load((patches / "prod-deployment-api.yaml").read_text(encoding="utf-8"))
    assert patch["metadata"] == {"name": "api", "namespace": "prod"}


def test_nothing_stable_opens_no_pull_request(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan())), encoding="utf-8")

    exit_code = m.main(
        ["--krr-json", str(krr_json), "--history-dir", str(tmp_path / "history"), "--pr", "--patch-dir", str(tmp_path)]
    )

    assert exit_code == 0
    assert "no pull request opened" in capsys.readouterr().err


def test_pr_commits_the_patches_with_the_run_that_justifies_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan())), encoding="utf-8")
    history = tmp_path / "history"
    for index in range(2):
        record(history, krr_document(krr_scan()), index)
    patches = tmp_path / "patches"
    calls: list[list[str]] = []

    def fake_run(argv: list[str], *, stdin: str | None = None) -> str:
        calls.append(argv)
        if argv[:2] == ["gh", "repo"]:
            return "acme/infra\n"
        if argv[:3] == ["gh", "pr", "create"]:
            assert "stayed within 15%" in (stdin or "")
            return "https://github.com/acme/infra/pull/7\n"
        if argv[:2] == ["git", "diff"]:  # `--quiet` exits non-zero when staged
            raise subprocess.CalledProcessError(1, argv)
        return ""

    monkeypatch.setattr(m, "_run", fake_run)

    m.main(
        [
            "--krr-json",
            str(krr_json),
            "--history-dir",
            str(history),
            "--patch-dir",
            str(patches),
            "--pr",
            "--branch",
            "rightsizer/test",
        ]
    )

    assert "https://github.com/acme/infra/pull/7" in capsys.readouterr().out
    assert ["git", "switch", "-c", "rightsizer/test"] in calls
    added = next(call for call in calls if call[:2] == ["git", "add"])
    # The patch and the run that justifies it land in the same commit: the PR
    # body's "stable for 3 runs" is checkable against the history beside it.
    assert str(patches / "prod-deployment-api.yaml") in added
    assert any(name.endswith(".json") and str(history) in name for name in added)
    assert ["git", "push", "-u", "origin", "rightsizer/test"] in calls


def test_pr_is_not_opened_when_the_patches_already_match_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ordinary state of a re-run. Committing nothing would fail mid-way and
    leave the checkout parked on an empty branch."""
    krr_json = tmp_path / "krr.json"
    krr_json.write_text(m.json.dumps(krr_document(krr_scan())), encoding="utf-8")
    history = tmp_path / "history"
    for index in range(2):
        record(history, krr_document(krr_scan()), index)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], *, stdin: str | None = None) -> str:
        calls.append(argv)
        return ""  # including `git diff --cached --quiet`: nothing is staged

    monkeypatch.setattr(m, "_run", fake_run)

    exit_code = m.main(
        [
            "--krr-json",
            str(krr_json),
            "--history-dir",
            str(history),
            "--patch-dir",
            str(tmp_path / "patches"),
            "--pr",
            "--branch",
            "rightsizer/test",
        ]
    )

    assert exit_code == 0
    assert "already match the repository" in capsys.readouterr().err
    assert not any(call[:2] == ["git", "commit"] for call in calls)
    # The checkout is left as it was found, not on an empty branch.
    assert ["git", "switch", "-"] in calls
    assert ["git", "branch", "-D", "rightsizer/test"] in calls


# ----------------------------------------------------------------- rendering


def test_units_round_up_so_a_rendering_never_proposes_less() -> None:
    assert fmt_cpu(0.0111) == "12m"
    assert fmt_memory(100.5 * MIB) == "101Mi"
    assert parse_cpu("250m") == 0.25
    assert parse_memory("256Mi") == 256 * MIB

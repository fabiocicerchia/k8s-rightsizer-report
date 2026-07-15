from k8s_rightsizer_report import (aggregate_by_owner, build_report, fmt_cpu, fmt_memory,
                                   parse_cpu, parse_memory, recommend, render_report)


def test_unit_parsing_roundtrip():
    assert parse_cpu("250m") == 0.25
    assert parse_memory("256Mi") == 256 * 2**20
    assert fmt_cpu(0.26) == "275m" or fmt_cpu(0.26) == "250m"  # 25m rounding
    assert fmt_memory(300 * 2**20) == "288Mi" or fmt_memory(300 * 2**20) == "320Mi"


def test_recommendation_adds_headroom():
    rec = recommend({"cpu": 0.2, "memory": 256 * 2**20})
    assert parse_cpu(rec["requests"]["cpu"]) >= 0.2 * 1.4 - 0.025
    assert parse_cpu(rec["limits"]["cpu"]) > parse_cpu(rec["requests"]["cpu"])


def test_aggregate_takes_peak_across_replicas():
    usage = {
        "api-6d9f8-abc12": {"app": {"cpu": 0.1, "memory": 100.0}},
        "api-6d9f8-def34": {"app": {"cpu": 0.3, "memory": 80.0}},
    }
    peaks = aggregate_by_owner(usage)
    assert peaks[("api", "app")] == {"cpu": 0.3, "memory": 100.0}


def test_report_flags_unset_requests():
    deployments = [{"metadata": {"name": "api"},
                    "spec": {"template": {"spec": {"containers": [{"name": "app"}]}}}}]
    peaks = {("api", "app"): {"cpu": 0.2, "memory": 128 * 2**20}}
    rows = build_report(deployments, peaks)
    assert rows[0]["current_requests"] is None
    assert "(unset)" in render_report(rows, "app")

import k8s_rightsizer_report as m
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


def test_top_pods_prometheus_parses_p95_vectors():
    def fake_fetcher(url):
        metric = "cpu" if "container_cpu_usage_seconds_total" in url else "memory"
        value = "0.3" if metric == "cpu" else str(300 * 2**20)
        return {"data": {"result": [
            {"metric": {"pod": "api-abc", "container": "app"}, "value": [0, value]}]}}

    usage = m.top_pods_prometheus("prod", "http://prom:9090", days=7, fetcher=fake_fetcher)
    assert usage == {"api-abc": {"app": {"cpu": 0.3, "memory": 300 * 2**20}}}


def test_vpa_recommendations_reads_target(monkeypatch):
    def fake_kubectl_json(args):
        assert args == ["get", "verticalpodautoscalers", "-n", "prod"]
        return {"items": [{
            "spec": {"targetRef": {"name": "api"}},
            "status": {"recommendation": {"containerRecommendations": [
                {"containerName": "app", "target": {"cpu": "300m", "memory": "256Mi"}}]}},
        }]}

    monkeypatch.setattr(m, "kubectl_json", fake_kubectl_json)
    peaks = m.vpa_recommendations("prod")
    assert peaks == {("api", "app"): {"cpu": 0.3, "memory": 256 * 2**20}}

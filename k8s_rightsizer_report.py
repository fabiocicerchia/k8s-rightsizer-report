#!/usr/bin/env python3
"""k8s-rightsizer-report — turn live usage into PR-ready requests/limits diffs.

Reads current requests/limits from deployments and actual usage from
metrics-server (`kubectl top pods`), recommends new values with headroom,
and emits either a report or a unified YAML diff you can commit.

  k8s-rightsizer-report --namespace app                 # report
  k8s-rightsizer-report --namespace app --diff          # PR-ready diff
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

HEADROOM = {"cpu": 1.4, "memory": 1.25}  # recommendation = peak usage * headroom
LIMIT_FACTOR = {"cpu": 2.0, "memory": 1.5}  # limits = requests * factor

MILLICORES_PER_CORE = 1000
CPU_STEP_MILLICORES = 25  # recommendations round up to whole 25m / 32Mi steps
MEMORY_STEP_MIB = 32

# kubectl names a pod "<workload>-<replicaset-hash>-<pod-id>", so the owning
# workload is the name minus this many trailing dash-separated parts.
POD_SUFFIX_PARTS = 2

DEFAULT_LOOKBACK_DAYS = 7  # --prometheus lookback; the flag default and this must agree

# kubectl resource name -> (apiVersion, kind) — every workload kind this tool sizes
# Kubernetes objects as kubectl hands them over: deep, variable, and not worth
# modelling past the handful of fields this file reads.
Manifest = dict[str, Any]
# pod -> container -> {"cpu": cores, "memory": bytes}
Usage = dict[str, dict[str, dict[str, float]]]
# (workload, container) -> {"cpu": cores, "memory": bytes}
Peaks = dict[tuple[str, str], dict[str, float]]
# The seam the tests swap in for the Prometheus call.
Fetcher = Callable[[str], Manifest]
# One line of the report, before it is rendered as text or as a patch.
Row = dict[str, Any]

# `kubectl top pods --containers --no-headers` prints pod, container, cpu, memory.
_TOP_COLUMNS = 4
_HTTP_TIMEOUT_SECONDS = 10

WORKLOAD_KINDS = {
    "deployments": ("apps/v1", "Deployment"),
    "statefulsets": ("apps/v1", "StatefulSet"),
    "daemonsets": ("apps/v1", "DaemonSet"),
}

# pod-template annotations that opt a workload/container out of sizing
ANNOTATION_EXCLUDE = "k8s-rightsizer-report/exclude"
ANNOTATION_EXCLUDE_CONTAINERS = "k8s-rightsizer-report/exclude-containers"


def parse_cpu(value: str) -> float:
    """'250m' -> 0.25 cores, '2' -> 2.0"""
    value = str(value)
    return float(value[:-1]) / MILLICORES_PER_CORE if value.endswith("m") else float(value)


def parse_memory(value: str) -> float:
    """'256Mi' -> bytes"""
    units = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "K": 1e3, "M": 1e6, "G": 1e9}
    value = str(value)
    for suffix, mult in units.items():
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * mult
    return float(value)


def fmt_cpu(cores: float) -> str:
    millicores = cores * MILLICORES_PER_CORE / CPU_STEP_MILLICORES
    return f"{max(round(millicores) * CPU_STEP_MILLICORES, CPU_STEP_MILLICORES)}m"


def fmt_memory(byte_count: float) -> str:
    mebibytes = byte_count / 2**20 / MEMORY_STEP_MIB
    return f"{max(round(mebibytes) * MEMORY_STEP_MIB, MEMORY_STEP_MIB)}Mi"


def kubectl(args: list[str]) -> str:
    """Run kubectl and return its stdout. Every shell-out goes through here so
    the failure behaviour (check=True) is decided in one place."""
    kubectl_path = shutil.which("kubectl")
    if kubectl_path is None:
        msg = "kubectl is not on PATH"
        raise RuntimeError(msg)
    # Fixed argv, no shell, absolute path: nothing here is caller-controlled
    # beyond the namespace and resource names this tool builds itself.
    return subprocess.run(  # noqa: S603 — argv is built here, never a string
        [kubectl_path, *args], check=True, capture_output=True, text=True
    ).stdout


def kubectl_json(args: list[str]) -> Manifest:
    return json.loads(kubectl([*args, "-o", "json"]))


def fetch_workloads(
    namespace: str, kinds: dict[str, tuple[str, str]] = WORKLOAD_KINDS
) -> list[tuple[str, str, Manifest]]:
    """Return [(apiVersion, kind, resource_dict), ...] across every workload
    kind this tool sizes (Deployment/StatefulSet/DaemonSet)."""
    workloads = []
    for resource, (api_version, kind) in kinds.items():
        for item in kubectl_json(["get", resource, "-n", namespace])["items"]:
            workloads.append((api_version, kind, item))
    return workloads


def top_pods(namespace: str) -> Usage:
    """Return {pod: {container: {cpu, memory}}} from metrics-server."""
    out = kubectl(["top", "pods", "-n", namespace, "--containers", "--no-headers"])
    usage = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= _TOP_COLUMNS:
            pod, container, cpu, mem = parts[0], parts[1], parts[2], parts[3]
            usage.setdefault(pod, {})[container] = {
                "cpu": parse_cpu(cpu),
                "memory": parse_memory(mem),
            }
    return usage


# urlopen honours whatever scheme it is handed, including file:, ftp: and the
# data: URLs — so a --prometheus value that arrives from a config file or a CI
# variable rather than a person's shell could read a local file instead of
# querying anything. The endpoint is meant to be an HTTP(S) Prometheus, so say
# so and refuse the rest.
ALLOWED_SCHEMES = ("http", "https")


def default_http_get(url: str) -> Manifest:
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"--prometheus must be an http(s) URL, got {scheme or 'no'} scheme")
    with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 — scheme checked above
        return json.loads(resp.read())


def prometheus_query(base_url: str, query: str, fetcher: Fetcher = default_http_get) -> list[Manifest]:
    """Run an instant PromQL query, return the raw `data.result` vector."""
    url = f"{base_url.rstrip('/')}/api/v1/query?query={urllib.parse.quote(query)}"
    return fetcher(url).get("data", {}).get("result", [])


def top_pods_prometheus(
    namespace: str,
    base_url: str,
    days: int = DEFAULT_LOOKBACK_DAYS,
    fetcher: Fetcher = default_http_get,
) -> Usage:
    """Return {pod: {container: {cpu, memory}}}, p95 over `days` via PromQL
    quantile_over_time — same shape as top_pods() so it drops into
    aggregate_by_owner() unchanged."""
    window = f"{days}d"
    queries = {
        "cpu": f"quantile_over_time(0.95, rate(container_cpu_usage_seconds_total"
        f'{{namespace="{namespace}",container!="",container!="POD"}}[5m])[{window}:5m])',
        "memory": f"quantile_over_time(0.95, container_memory_working_set_bytes"
        f'{{namespace="{namespace}",container!="",container!="POD"}}[{window}:5m])',
    }
    usage = {}
    for metric, query in queries.items():
        for series in prometheus_query(base_url, query, fetcher):
            pod, container = series["metric"].get("pod"), series["metric"].get("container")
            if not pod or not container:
                continue
            usage.setdefault(pod, {}).setdefault(container, {"cpu": 0.0, "memory": 0.0})[metric] = float(
                series["value"][1]
            )
    return usage


def aggregate_by_owner(usage: Usage) -> Peaks:
    """Collapse pod-level usage to peak per (workload-prefix, container)."""
    peaks = {}
    for pod, containers in usage.items():
        owner = pod.rsplit("-", POD_SUFFIX_PARTS)[0] if pod.count("-") >= POD_SUFFIX_PARTS else pod
        for container, usage_of_container in containers.items():
            peak = peaks.setdefault((owner, container), {"cpu": 0.0, "memory": 0.0})
            peak["cpu"] = max(peak["cpu"], usage_of_container["cpu"])
            peak["memory"] = max(peak["memory"], usage_of_container["memory"])
    return peaks


def vpa_recommendations(namespace: str) -> Peaks:
    """(workload, container) -> {cpu, memory} target from VerticalPodAutoscaler CRs —
    already a percentile-based recommendation, so it drops straight into the
    same `peaks` shape metrics-server/Prometheus produce."""
    peaks = {}
    for vpa in kubectl_json(["get", "verticalpodautoscalers", "-n", namespace])["items"]:
        workload = vpa["spec"]["targetRef"]["name"]
        for recommendation in vpa.get("status", {}).get("recommendation", {}).get("containerRecommendations", []):
            target = recommendation.get("target", {})
            if not target:
                continue
            peaks[(workload, recommendation["containerName"])] = {
                "cpu": parse_cpu(target.get("cpu", "0")),
                "memory": parse_memory(target.get("memory", "0")),
            }
    return peaks


def recommend(peak: dict[str, float]) -> dict[str, dict[str, str]]:
    req_cpu = peak["cpu"] * HEADROOM["cpu"]
    req_mem = peak["memory"] * HEADROOM["memory"]
    return {
        "requests": {"cpu": fmt_cpu(req_cpu), "memory": fmt_memory(req_mem)},
        "limits": {
            "cpu": fmt_cpu(req_cpu * LIMIT_FACTOR["cpu"]),
            "memory": fmt_memory(req_mem * LIMIT_FACTOR["memory"]),
        },
    }


def sizable_containers(resource: Manifest) -> list[Manifest]:
    """The containers of one workload the pod-template exclude annotations
    leave in scope; an excluded workload contributes none."""
    template = resource["spec"]["template"]
    annotations = template.get("metadata", {}).get("annotations", {}) or {}
    if annotations.get(ANNOTATION_EXCLUDE, "").lower() == "true":
        return []
    excluded = {
        excluded_name.strip()
        for excluded_name in annotations.get(ANNOTATION_EXCLUDE_CONTAINERS, "").split(",")
        if excluded_name.strip()
    }
    return [container for container in template["spec"]["containers"] if container["name"] not in excluded]


def build_report(workloads: list[tuple[str, str, Manifest] | Manifest], peaks: Peaks) -> list[Row]:
    """Yield rows: kind, workload, container, current requests, peak usage,
    recommendation. `workloads` is [(apiVersion, kind, resource_dict), ...];
    plain resource dicts (implicitly Deployment) are accepted too."""
    rows = []
    for workload in workloads:
        api_version, kind, resource = workload if isinstance(workload, tuple) else ("apps/v1", "Deployment", workload)
        name = resource["metadata"]["name"]
        for container in sizable_containers(resource):
            peak = peaks.get((name, container["name"]))
            if not peak:
                continue
            current = container.get("resources", {}).get("requests", {})
            rec = recommend(peak)
            cur_cpu = parse_cpu(current.get("cpu", "0"))
            rec_cpu = parse_cpu(rec["requests"]["cpu"])
            rows.append(
                {
                    "api_version": api_version,
                    "kind": kind,
                    "workload": name,
                    "container": container["name"],
                    "current_requests": current or None,
                    "peak": {
                        "cpu": fmt_cpu(peak["cpu"]),
                        "memory": fmt_memory(peak["memory"]),
                    },
                    "recommended": rec,
                    "cpu_change_pct": (round((rec_cpu - cur_cpu) / cur_cpu * 100) if cur_cpu else None),
                }
            )
    return rows


def render_report(rows: list[Row], namespace: str) -> str:
    lines = [
        f"# Rightsizing report — namespace `{namespace}`\n",
        "| kind/workload/container | current req | peak usage | recommended req | Δ cpu |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        current = row["current_requests"]
        current_cell = f"{current.get('cpu', '–')}/{current.get('memory', '–')}" if current else "(unset)"
        recommended = row["recommended"]["requests"]
        delta = f"{row['cpu_change_pct']:+d}%" if row["cpu_change_pct"] is not None else "new"
        lines.append(
            f"| {row.get('kind', 'Deployment')}/{row['workload']}/{row['container']} "
            f"| {current_cell} "
            f"| {row['peak']['cpu']}/{row['peak']['memory']} "
            f"| {recommended['cpu']}/{recommended['memory']} | {delta} |"
        )
    return "\n".join(lines)


def render_diff(rows: list[Row]) -> str:
    """Kustomize-style patch snippets, one per workload container — commit-ready."""
    # Only the --diff path renders YAML; the report itself must work without
    # PyYAML installed.
    import yaml  # noqa: PLC0415

    docs = []
    for row in rows:
        docs.append(
            {
                "apiVersion": row.get("api_version", "apps/v1"),
                "kind": row.get("kind", "Deployment"),
                "metadata": {"name": row["workload"]},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": row["container"],
                                    "resources": row["recommended"],
                                }
                            ]
                        }
                    }
                },
            }
        )
    return yaml.dump_all(docs, sort_keys=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-rightsizer-report",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--namespace", "-n", required=True)
    parser.add_argument("--diff", action="store_true", help="emit patch YAML instead of a report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--prometheus",
        metavar="URL",
        help="use PromQL p95-over-time instead of a point-in-time kubectl top",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"lookback window for --prometheus (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--vpa",
        action="store_true",
        help="use VerticalPodAutoscaler recommendations instead of metrics-server",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    workloads = fetch_workloads(args.namespace)
    if args.vpa:
        peaks = vpa_recommendations(args.namespace)
    elif args.prometheus:
        peaks = aggregate_by_owner(top_pods_prometheus(args.namespace, args.prometheus, args.days))
    else:
        peaks = aggregate_by_owner(top_pods(args.namespace))
    rows = build_report(workloads, peaks)

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
    elif args.diff:
        print(render_diff(rows))  # noqa: T201 — the tool's output
    else:
        print(render_report(rows, args.namespace))  # noqa: T201 — the tool's output
    return 0


if __name__ == "__main__":
    sys.exit(main())

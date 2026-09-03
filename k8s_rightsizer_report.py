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
import subprocess
import sys
import urllib.parse
import urllib.request

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
WORKLOAD_KINDS = {
    "deployments": ("apps/v1", "Deployment"),
    "statefulsets": ("apps/v1", "StatefulSet"),
    "daemonsets": ("apps/v1", "DaemonSet"),
}

# pod-template annotations that opt a workload/container out of sizing
ANNOTATION_EXCLUDE = "k8s-rightsizer-report/exclude"
ANNOTATION_EXCLUDE_CONTAINERS = "k8s-rightsizer-report/exclude-containers"


def parse_cpu(value):
    """'250m' -> 0.25 cores, '2' -> 2.0"""
    value = str(value)
    return float(value[:-1]) / MILLICORES_PER_CORE if value.endswith("m") else float(value)


def parse_memory(value):
    """'256Mi' -> bytes"""
    units = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "K": 1e3, "M": 1e6, "G": 1e9}
    value = str(value)
    for suffix, mult in units.items():
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * mult
    return float(value)


def fmt_cpu(cores):
    millicores = cores * MILLICORES_PER_CORE / CPU_STEP_MILLICORES
    return f"{max(round(millicores) * CPU_STEP_MILLICORES, CPU_STEP_MILLICORES)}m"


def fmt_memory(byte_count):
    mebibytes = byte_count / 2**20 / MEMORY_STEP_MIB
    return f"{max(round(mebibytes) * MEMORY_STEP_MIB, MEMORY_STEP_MIB)}Mi"


def kubectl(args):
    """Run kubectl and return its stdout. Every shell-out goes through here so
    the failure behaviour (check=True) is decided in one place."""
    return subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True).stdout


def kubectl_json(args):
    return json.loads(kubectl([*args, "-o", "json"]))


def fetch_workloads(namespace, kinds=WORKLOAD_KINDS):
    """Return [(apiVersion, kind, resource_dict), ...] across every workload
    kind this tool sizes (Deployment/StatefulSet/DaemonSet)."""
    workloads = []
    for resource, (api_version, kind) in kinds.items():
        for item in kubectl_json(["get", resource, "-n", namespace])["items"]:
            workloads.append((api_version, kind, item))
    return workloads


def top_pods(namespace):
    """Return {pod: {container: {cpu, memory}}} from metrics-server."""
    out = kubectl(["top", "pods", "-n", namespace, "--containers", "--no-headers"])
    usage = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
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


def default_http_get(url):
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"--prometheus must be an http(s) URL, got {scheme or 'no'} scheme")
    with urllib.request.urlopen(url, timeout=10) as resp:  # nosec B310 — scheme checked above
        return json.loads(resp.read())


def prometheus_query(base_url, query, fetcher=default_http_get):
    """Run an instant PromQL query, return the raw `data.result` vector."""
    url = f"{base_url.rstrip('/')}/api/v1/query?query={urllib.parse.quote(query)}"
    return fetcher(url).get("data", {}).get("result", [])


def top_pods_prometheus(namespace, base_url, days=DEFAULT_LOOKBACK_DAYS, fetcher=default_http_get):
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
            usage.setdefault(pod, {}).setdefault(container, {"cpu": 0.0, "memory": 0.0})[metric] = (
                float(series["value"][1])
            )
    return usage


def aggregate_by_owner(usage):
    """Collapse pod-level usage to peak per (workload-prefix, container)."""
    peaks = {}
    for pod, containers in usage.items():
        owner = pod.rsplit("-", POD_SUFFIX_PARTS)[0] if pod.count("-") >= POD_SUFFIX_PARTS else pod
        for container, usage_of_container in containers.items():
            peak = peaks.setdefault((owner, container), {"cpu": 0.0, "memory": 0.0})
            peak["cpu"] = max(peak["cpu"], usage_of_container["cpu"])
            peak["memory"] = max(peak["memory"], usage_of_container["memory"])
    return peaks


def vpa_recommendations(namespace):
    """(workload, container) -> {cpu, memory} target from VerticalPodAutoscaler CRs —
    already a percentile-based recommendation, so it drops straight into the
    same `peaks` shape metrics-server/Prometheus produce."""
    peaks = {}
    for vpa in kubectl_json(["get", "verticalpodautoscalers", "-n", namespace])["items"]:
        workload = vpa["spec"]["targetRef"]["name"]
        for recommendation in (
            vpa.get("status", {}).get("recommendation", {}).get("containerRecommendations", [])
        ):
            target = recommendation.get("target", {})
            if not target:
                continue
            peaks[(workload, recommendation["containerName"])] = {
                "cpu": parse_cpu(target.get("cpu", "0")),
                "memory": parse_memory(target.get("memory", "0")),
            }
    return peaks


def recommend(peak):
    req_cpu = peak["cpu"] * HEADROOM["cpu"]
    req_mem = peak["memory"] * HEADROOM["memory"]
    return {
        "requests": {"cpu": fmt_cpu(req_cpu), "memory": fmt_memory(req_mem)},
        "limits": {
            "cpu": fmt_cpu(req_cpu * LIMIT_FACTOR["cpu"]),
            "memory": fmt_memory(req_mem * LIMIT_FACTOR["memory"]),
        },
    }


def sizable_containers(resource):
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
    return [
        container
        for container in template["spec"]["containers"]
        if container["name"] not in excluded
    ]


def build_report(workloads, peaks):
    """Yield rows: kind, workload, container, current requests, peak usage,
    recommendation. `workloads` is [(apiVersion, kind, resource_dict), ...];
    plain resource dicts (implicitly Deployment) are accepted too."""
    rows = []
    for workload in workloads:
        api_version, kind, resource = (
            workload if isinstance(workload, tuple) else ("apps/v1", "Deployment", workload)
        )
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
                    "cpu_change_pct": (
                        round((rec_cpu - cur_cpu) / cur_cpu * 100) if cur_cpu else None
                    ),
                }
            )
    return rows


def render_report(rows, namespace):
    lines = [
        f"# Rightsizing report — namespace `{namespace}`\n",
        "| kind/workload/container | current req | peak usage | recommended req | Δ cpu |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        current = row["current_requests"]
        current_cell = (
            f"{current.get('cpu', '–')}/{current.get('memory', '–')}" if current else "(unset)"
        )
        recommended = row["recommended"]["requests"]
        delta = f"{row['cpu_change_pct']:+d}%" if row["cpu_change_pct"] is not None else "new"
        lines.append(
            f"| {row.get('kind', 'Deployment')}/{row['workload']}/{row['container']} "
            f"| {current_cell} "
            f"| {row['peak']['cpu']}/{row['peak']['memory']} "
            f"| {recommended['cpu']}/{recommended['memory']} | {delta} |"
        )
    return "\n".join(lines)


def render_diff(rows):
    """Kustomize-style patch snippets, one per workload container — commit-ready."""
    import yaml

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


def build_parser():
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


def main(argv=None):
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
        print(render_diff(rows))
    else:
        print(render_report(rows, args.namespace))
    return 0


if __name__ == "__main__":
    sys.exit(main())

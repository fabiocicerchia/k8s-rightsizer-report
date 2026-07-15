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

HEADROOM = {"cpu": 1.4, "memory": 1.25}   # recommendation = peak usage * headroom
LIMIT_FACTOR = {"cpu": 2.0, "memory": 1.5}  # limits = requests * factor


def parse_cpu(value):
    """'250m' -> 0.25 cores, '2' -> 2.0"""
    value = str(value)
    return float(value[:-1]) / 1000 if value.endswith("m") else float(value)


def parse_memory(value):
    """'256Mi' -> bytes"""
    units = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "K": 1e3, "M": 1e6, "G": 1e9}
    value = str(value)
    for suffix, mult in units.items():
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * mult
    return float(value)


def fmt_cpu(cores):
    return f"{max(round(cores * 1000 / 25) * 25, 25)}m"   # round to 25m steps


def fmt_memory(b):
    mi = max(round(b / 2**20 / 32) * 32, 32)               # round to 32Mi steps
    return f"{mi}Mi"


def kubectl_json(args):
    out = subprocess.run(["kubectl", *args, "-o", "json"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def top_pods(namespace):
    """Return {pod: {container: {cpu, memory}}} from metrics-server."""
    out = subprocess.run(
        ["kubectl", "top", "pods", "-n", namespace, "--containers", "--no-headers"],
        check=True, capture_output=True, text=True).stdout
    usage = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            pod, container, cpu, mem = parts[0], parts[1], parts[2], parts[3]
            usage.setdefault(pod, {})[container] = {
                "cpu": parse_cpu(cpu), "memory": parse_memory(mem)}
    return usage


def aggregate_by_owner(usage):
    """Collapse pod-level usage to peak per (workload-prefix, container)."""
    peaks = {}
    for pod, containers in usage.items():
        owner = pod.rsplit("-", 2)[0] if pod.count("-") >= 2 else pod
        for container, u in containers.items():
            key = (owner, container)
            cur = peaks.setdefault(key, {"cpu": 0.0, "memory": 0.0})
            cur["cpu"] = max(cur["cpu"], u["cpu"])
            cur["memory"] = max(cur["memory"], u["memory"])
    return peaks


def recommend(peak):
    req_cpu = peak["cpu"] * HEADROOM["cpu"]
    req_mem = peak["memory"] * HEADROOM["memory"]
    return {
        "requests": {"cpu": fmt_cpu(req_cpu), "memory": fmt_memory(req_mem)},
        "limits": {"cpu": fmt_cpu(req_cpu * LIMIT_FACTOR["cpu"]),
                   "memory": fmt_memory(req_mem * LIMIT_FACTOR["memory"])},
    }


def build_report(deployments, peaks):
    """Yield rows: workload, container, current requests, peak usage, recommendation."""
    rows = []
    for d in deployments:
        name = d["metadata"]["name"]
        for c in d["spec"]["template"]["spec"]["containers"]:
            peak = peaks.get((name, c["name"]))
            if not peak:
                continue
            current = c.get("resources", {}).get("requests", {})
            rec = recommend(peak)
            cur_cpu = parse_cpu(current.get("cpu", "0"))
            rec_cpu = parse_cpu(rec["requests"]["cpu"])
            rows.append({
                "workload": name, "container": c["name"],
                "current_requests": current or None,
                "peak": {"cpu": fmt_cpu(peak["cpu"]), "memory": fmt_memory(peak["memory"])},
                "recommended": rec,
                "cpu_change_pct": round((rec_cpu - cur_cpu) / cur_cpu * 100) if cur_cpu else None,
            })
    return rows


def render_report(rows, namespace):
    lines = [f"# Rightsizing report — namespace `{namespace}`\n",
             "| workload/container | current req | peak usage | recommended req | Δ cpu |",
             "|---|---|---|---|---|"]
    for r in rows:
        cur = r["current_requests"]
        cur_s = f"{cur.get('cpu', '–')}/{cur.get('memory', '–')}" if cur else "(unset)"
        rec = r["recommended"]["requests"]
        delta = f"{r['cpu_change_pct']:+d}%" if r["cpu_change_pct"] is not None else "new"
        lines.append(f"| {r['workload']}/{r['container']} | {cur_s} "
                     f"| {r['peak']['cpu']}/{r['peak']['memory']} "
                     f"| {rec['cpu']}/{rec['memory']} | {delta} |")
    return "\n".join(lines)


def render_diff(rows):
    """Kustomize-style patch snippets, one per workload — commit-ready."""
    import yaml
    docs = []
    for r in rows:
        docs.append({
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": r["workload"]},
            "spec": {"template": {"spec": {"containers": [{
                "name": r["container"],
                "resources": r["recommended"],
            }]}}},
        })
    return yaml.dump_all(docs, sort_keys=False)


def main(argv=None):
    p = argparse.ArgumentParser(prog="k8s-rightsizer-report", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--namespace", "-n", required=True)
    p.add_argument("--diff", action="store_true", help="emit patch YAML instead of a report")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    deployments = kubectl_json(["get", "deployments", "-n", args.namespace])["items"]
    peaks = aggregate_by_owner(top_pods(args.namespace))
    rows = build_report(deployments, peaks)

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
    elif args.diff:
        print(render_diff(rows))
    else:
        print(render_report(rows, args.namespace))
    return 0


if __name__ == "__main__":
    sys.exit(main())

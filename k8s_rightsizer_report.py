#!/usr/bin/env python3
"""k8s-rightsizer-report — turn KRR recommendations into reviewable changes.

KRR (robusta-dev/krr) reads Prometheus history and does the sizing maths. This
tool does not size anything: it decides which of KRR's recommendations are
settled enough to propose, and turns those into a reviewable change.

Every run is recorded as a dated JSON file in a history directory meant to be
committed. A recommendation is proposed only once it has stayed within a
tolerance across several consecutive runs; anything still moving is reported as
"not yet — flapping", with its range, instead of being pushed at a reviewer.

  k8s-rightsizer-report -n app                     # run krr, record, dry-run
  k8s-rightsizer-report --krr-json run.json        # ingest a saved krr run
  k8s-rightsizer-report -n app --pr                # open the pull request

Applying to a cluster is deliberately not offered: the cluster changes when the
pull request merges and the GitOps tooling rolls it out, not when this runs.
"""

import argparse
import copy
import difflib
import json
import math
import shutil
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

DEFAULT_HISTORY_DIR = ".rightsizer/history"
DEFAULT_PATCH_DIR = ".rightsizer/patches"
DEFAULT_TOLERANCE_PCT = 15.0  # "stayed within X%"
DEFAULT_STABLE_RUNS = 3  # "... for N consecutive runs"

MILLICORES_PER_CORE = 1000
HISTORY_SCHEMA = 1
# Sorts chronologically as a plain string, and has no colon in it: `:` is
# illegal in a Windows filename, and this directory is meant to be committed.
RUN_FILENAME_FORMAT = "%Y-%m-%dT%H-%M-%SZ"

# A KRR document, a Kubernetes manifest, a Helm values tree: someone else's
# deep, variable JSON, not worth modelling past the fields read here.
Manifest = dict[str, Any]
# One workload container: where it lives, what it has, what KRR proposes.
Recommendation = dict[str, Any]
# One recorded run: {"schema", "recorded_at", "source", "recommendations"}.
Run = dict[str, Any]

# `krr simple --formatter json`, quiet so the progress chrome stays off stdout.
KRR_BASE_ARGS = ("simple", "--formatter", "json", "--quiet")
_SUBPROCESS_TIMEOUT_SECONDS = 900  # krr scans a whole cluster; be patient

# The four numbers a recommendation can move. Stability is judged per dimension:
# a settled CPU request does not excuse a memory limit that is still swinging.
DIMENSIONS = (("requests", "cpu"), ("requests", "memory"), ("limits", "cpu"), ("limits", "memory"))
RESOURCES = ("cpu", "memory")

# KRR names the workload kind; the patch has to name its apiVersion too.
API_VERSIONS = {
    "Deployment": "apps/v1",
    "StatefulSet": "apps/v1",
    "DaemonSet": "apps/v1",
    "ReplicaSet": "apps/v1",
    "Job": "batch/v1",
    "CronJob": "batch/v1",
    "Rollout": "argoproj.io/v1alpha1",
    "DeploymentConfig": "apps.openshift.io/v1",
}
DEFAULT_API_VERSION = "apps/v1"

# Cost is optional in KRR's output and has moved around between builds, so read
# every spelling we know of and drop the saving column when none of them is there.
COST_KEYS = ("monthly_cost", "cost_monthly", "cost")

UNSET = "–"  # en dash: "KRR proposes nothing here", as distinct from zero


# ------------------------------------------------------ reading foreign JSON

# A KRR document, a recorded run and a chart's values file are all someone
# else's JSON: every level of them can be absent, null, or a different shape
# than last release. These three read it without a pile of isinstance at every
# call site — a missing branch reads as empty rather than raising.


def mapping(value: Any) -> Manifest:
    """Anything out of a JSON document, as a mapping; {} when it is not one."""
    return cast(Manifest, value) if isinstance(value, dict) else {}


def section(node: Manifest, key: str) -> Manifest:
    """One nested mapping of `node`."""
    return mapping(node.get(key))


def text_field(node: Manifest, key: str, default: str = "") -> str:
    """One string of `node`; the default when it is missing, empty or not text."""
    return value if isinstance(value := node.get(key), str) and value else default


# --------------------------------------------------------------------- units


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
    """KRR's number, spelled the way a manifest spells it. Rounds *up* to the
    next whole millicore so rendering never proposes less than KRR did."""
    return f"{math.ceil(cores * MILLICORES_PER_CORE)}m"


def fmt_memory(byte_count: float) -> str:
    """As fmt_cpu: KRR's number in MiB, rounded up rather than down."""
    return f"{math.ceil(byte_count / 2**20)}Mi"


def fmt_resource(resource: str, value: float | None) -> str:
    if value is None:
        return UNSET
    return fmt_cpu(value) if resource == "cpu" else fmt_memory(value)


def fmt_pair(block: Mapping[str, Any] | None) -> str:
    """A requests/limits block as `cpu/memory`, for a report cell."""
    block = block or {}
    return f"{fmt_resource('cpu', block.get('cpu'))}/{fmt_resource('memory', block.get('memory'))}"


def quantity(value: Any, resource: str) -> float | None:
    """KRR emits plain numbers (CPU cores, memory bytes), but tolerate the
    Kubernetes quantity strings and the `"?"` it uses for "unknown"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text == "?":
        return None
    try:
        return parse_cpu(text) if resource == "cpu" else parse_memory(text)
    except ValueError:
        return None


# ----------------------------------------------------------------- ingestion


def _brace_positions(text: str) -> Iterator[int]:
    start = text.find("{")
    while start != -1:
        yield start
        start = text.find("{", start + 1)


def parse_krr_output(text: str) -> Manifest:
    """The KRR document out of whatever krr wrote to stdout. `--quiet` should
    leave nothing but JSON there, but a banner or a warning line ahead of it is
    not worth failing the run over."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return mapping(parsed)
    decoder = json.JSONDecoder()
    for start in _brace_positions(text):
        try:
            document, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict) and "scans" in document:
            return mapping(document)
    raise ValueError("no krr JSON document found in the output — is this `krr simple --formatter json`?")


def load_krr(source: str) -> Manifest:
    """Read a saved `krr simple --formatter json` run; `-` reads stdin."""
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return parse_krr_output(text)


def run_krr(namespace: str | None = None, extra_args: Sequence[str] = ()) -> Manifest:
    """Run krr for the user when it is on PATH."""
    krr_path = shutil.which("krr")
    if krr_path is None:
        raise RuntimeError("krr is not on PATH — install robusta-dev/krr, or pass --krr-json FILE")
    argv = [krr_path, *KRR_BASE_ARGS]
    if namespace:
        argv += ["-n", namespace]
    argv += list(extra_args)
    # Fixed argv, no shell, absolute path: the only caller-controlled parts are
    # the namespace and the --krr-arg passthrough, both of which are krr's own.
    completed = subprocess.run(  # noqa: S603 — argv is built here, never a string
        argv, check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS
    )
    return parse_krr_output(completed.stdout)


def _allocations(block: Manifest) -> Manifest:
    """KRR's `object.allocations` -> {requests: {cpu, memory}, limits: {...}}."""
    return {
        group: {resource: quantity(section(block, group).get(resource), resource) for resource in RESOURCES}
        for group in ("requests", "limits")
    }


def _recommended(block: Manifest) -> Manifest:
    """KRR's `recommended`, whose leaves are `{"value": …, "severity": …}`."""
    sized: Manifest = {}
    for group in ("requests", "limits"):
        proposed = section(block, group)
        # KRR nests the number under "value", next to its severity; a build that
        # writes the bare number instead reads the same way.
        sized[group] = {
            resource: quantity(section(proposed, resource).get("value", proposed.get(resource)), resource)
            for resource in RESOURCES
        }
    return sized


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _cost(node: Manifest, *keys: str) -> float | None:
    """The first of `keys` that holds a number."""
    for key in keys:
        number = _number(node.get(key))
        if number is not None:
            return number
    return None


def krr_cost(scan: Manifest) -> Manifest | None:
    """Monthly cost, current and proposed, when the KRR build reports it.

    Cost is optional in KRR and has lived in a few different places, so read the
    spellings we know and return None rather than guess — a missing cost drops
    the saving column, it does not hold a recommendation back."""
    obj = section(scan, "object")
    recommended = section(scan, "recommended")
    pair = section(scan, "cost")
    if pair:
        current = _cost(pair, "current", *COST_KEYS)
        proposed = _cost(pair, "recommended", "proposed")
    else:
        current = _cost(obj, *COST_KEYS)
        if current is None:
            current = _cost(section(section(obj, "allocations"), "info"), *COST_KEYS)
        proposed = _cost(recommended, *COST_KEYS)
        if proposed is None:
            proposed = _cost(section(recommended, "info"), *COST_KEYS)
    if current is None and proposed is None:
        return None
    return {"current": current, "proposed": proposed}


def recommendation_key(namespace: str, kind: str, workload: str, container: str) -> str:
    return f"{namespace}/{kind}/{workload}/{container}"


def normalise(document: Manifest, namespace: str | None = None) -> dict[str, Recommendation]:
    """KRR's `scans` list -> per-workload-container recommendations, keyed so the
    same container is recognisable from one run to the next."""
    recommendations: dict[str, Recommendation] = {}
    scans: list[Any] = document.get("scans") or []
    for entry in scans:
        scan = mapping(entry)
        obj = section(scan, "object")
        workload, container = text_field(obj, "name"), text_field(obj, "container")
        if not workload or not container:
            continue
        scanned_namespace = text_field(obj, "namespace", "default")
        if namespace and scanned_namespace != namespace:
            continue
        kind = text_field(obj, "kind", "Deployment")
        key = recommendation_key(scanned_namespace, kind, workload, container)
        recommendations[key] = {
            "key": key,
            "cluster": text_field(obj, "cluster"),
            "namespace": scanned_namespace,
            "kind": kind,
            "workload": workload,
            "container": container,
            "current": _allocations(section(obj, "allocations")),
            "proposed": _recommended(section(scan, "recommended")),
            "severity": text_field(scan, "severity"),
            "cost": krr_cost(scan),
        }
    return recommendations


# ------------------------------------------------------------------- history


def as_run(recommendations: Mapping[str, Recommendation], source: str, now: datetime) -> Run:
    return {
        "schema": HISTORY_SCHEMA,
        "recorded_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "recommendations": dict(recommendations),
    }


def next_run_path(history_dir: Path, now: datetime) -> Path:
    """A free filename for this run. Two runs in the same second are unusual but
    not impossible (a retry, a CI matrix), and overwriting one would quietly
    shorten a stability streak — so the second one takes a suffix."""
    stamp = now.strftime(RUN_FILENAME_FORMAT)
    path = history_dir / f"{stamp}.json"
    suffix = 1
    while path.exists():
        suffix += 1
        # `_` sorts after `.`, so the suffixed run still comes after the
        # unsuffixed one when the directory is read in filename order.
        path = history_dir / f"{stamp}_{suffix:02d}.json"
    return path


def write_run(history_dir: Path, run: Run, now: datetime) -> Path:
    """Store the run as a dated JSON file. The directory is state, and it is
    meant to be committed — that is the whole of this tool's persistence."""
    history_dir.mkdir(parents=True, exist_ok=True)
    path = next_run_path(history_dir, now)
    path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_history(history_dir: Path) -> list[Run]:
    """Recorded runs, oldest first. A file that cannot be read is an error, not
    a gap: silently skipping one would silently reset a stability streak."""
    if not history_dir.is_dir():
        return []
    runs: list[Run] = []
    for path in sorted(history_dir.glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not readable as a recorded run: {exc}") from exc
        if not isinstance(run, dict) or "recommendations" not in run:
            raise ValueError(f"{path} is not a k8s-rightsizer-report run (no `recommendations`)")
        runs.append(mapping(run))
    return runs


# ----------------------------------------------------------------- stability


@dataclass(frozen=True)
class Rule:
    """The reason to trust this over KRR's output applied directly.

    Keep it visible: it goes in the report, in the JSON, and in the PR body."""

    tolerance_pct: float = DEFAULT_TOLERANCE_PCT
    runs: int = DEFAULT_STABLE_RUNS

    def describe(self) -> str:
        return (
            f"a recommendation is proposed only once it has stayed within "
            f"{self.tolerance_pct:g}% across {self.runs} consecutive runs"
        )


def _dimension_values(window: Sequence[Manifest], group: str, resource: str) -> list[float | None]:
    return [_number(section(proposed, group).get(resource)) for proposed in window]


def within_tolerance(values: Sequence[float | None], tolerance_pct: float) -> bool:
    """True when every value sits within `tolerance_pct` of the smallest one.

    A dimension KRR never sizes (no CPU limit, say) is stable by definition; one
    that appears in some runs and not others has changed shape, so it is not."""
    present = [value for value in values if value is not None]
    if not present:
        return True
    if len(present) != len(values):
        return False
    low, high = min(present), max(present)
    if low <= 0:
        return high <= 0
    return high <= low * (1 + tolerance_pct / 100)


def _consecutive_proposals(runs: Sequence[Run], key: str) -> list[Manifest]:
    """The proposed block from each of the most recent consecutive runs that
    carries `key`, newest first. A run without it breaks the chain: a workload
    that vanished and came back has not been stable across the gap."""
    window: list[Manifest] = []
    for run in reversed(runs):
        recommendations = section(run, "recommendations")
        if key not in recommendations:
            break
        window.append(section(section(recommendations, key), "proposed"))
    return window


def _ranges(window: Sequence[Manifest]) -> Manifest:
    """Per dimension, what the proposal has ranged over — the evidence behind a
    "flapping" verdict, so the reader can judge it rather than take it."""
    ranges: Manifest = {}
    for group, resource in DIMENSIONS:
        present = [value for value in _dimension_values(window, group, resource) if value is not None]
        if not present:
            continue
        low, high = min(present), max(present)
        ranges[f"{group}.{resource}"] = {
            "resource": resource,
            "min": low,
            "max": high,
            "spread_pct": round((high / low - 1) * 100) if low > 0 else None,
        }
    return ranges


def stability(runs: Sequence[Run], key: str, rule: Rule) -> Manifest:
    """How many of the most recent consecutive runs agree on this recommendation.

    `streak` is the longest run of recent proposals that all sit within the
    tolerance of each other, so it answers the question a reviewer actually
    asks: how long has this number been saying the same thing?"""
    window = _consecutive_proposals(runs, key)
    streak = 0
    for size in range(1, len(window) + 1):
        candidate = window[:size]
        if all(
            within_tolerance(_dimension_values(candidate, group, resource), rule.tolerance_pct)
            for group, resource in DIMENSIONS
        ):
            streak = size
        else:
            break
    return {
        "runs_seen": len(window),
        "streak": streak,
        "stable": streak >= rule.runs,
        "ranges": _ranges(window[: max(rule.runs, 1)]),
    }


def status_text(stab: Manifest, rule: Rule) -> str:
    if stab["stable"]:
        return f"stable for {stab['streak']} runs"
    if stab["runs_seen"] < rule.runs:
        return f"not yet — {stab['runs_seen']} of {rule.runs} runs"
    return "not yet — flapping"


def range_text(stab: Manifest) -> str:
    """`requests.cpu 35m–210m (+500%)`, one dimension per comma.

    The dimensions that moved are the ones worth reading, so they crowd out the
    steady ones; when nothing moved, the steady values are the whole story."""
    ranges: Manifest = stab["ranges"]
    moving = {dimension: span for dimension, span in ranges.items() if span["min"] != span["max"]}
    parts: list[str] = []
    for dimension, span in (moving or ranges).items():
        low = fmt_resource(span["resource"], span["min"])
        high = fmt_resource(span["resource"], span["max"])
        spread = f" (+{span['spread_pct']}%)" if span.get("spread_pct") else ""
        parts.append(f"{dimension} {low}–{high}{spread}" if low != high else f"{dimension} {low}")
    return ", ".join(parts) or UNSET


def classify(runs: Sequence[Run], rule: Rule) -> tuple[list[Recommendation], list[Recommendation]]:
    """(proposed, held back) from the newest run, each with its stability."""
    if not runs:
        return [], []
    proposed: list[Recommendation] = []
    held: list[Recommendation] = []
    latest: Mapping[str, Recommendation] = runs[-1].get("recommendations") or {}
    for key in sorted(latest):
        recommendation = dict(latest[key])
        stab = stability(runs, key, rule)
        recommendation["stability"] = stab
        recommendation["status"] = status_text(stab, rule)
        (proposed if stab["stable"] else held).append(recommendation)
    return proposed, held


def monthly_saving(recommendations: Sequence[Recommendation]) -> float | None:
    """What merging this is projected to save per month, when KRR costed it."""
    savings: list[float] = []
    for recommendation in recommendations:
        cost = section(recommendation, "cost")
        current, proposed = _number(cost.get("current")), _number(cost.get("proposed"))
        if current is not None and proposed is not None:
            savings.append(current - proposed)
    return sum(savings) if savings else None


# -------------------------------------------------------------------- output


def resources_block(proposed: Manifest) -> Manifest:
    """The `resources:` a patch sets — only what KRR actually sized. A resource
    KRR leaves unset (it recommends no CPU limit, deliberately) stays unset."""
    block: Manifest = {}
    for group in ("requests", "limits"):
        sized = section(proposed, group)
        values = {
            resource: fmt_resource(resource, _number(sized.get(resource)))
            for resource in RESOURCES
            if _number(sized.get(resource)) is not None
        }
        if values:
            block[group] = values
    return block


def workload_patch(recommendations: Sequence[Recommendation]) -> Manifest | None:
    """A strategic-merge patch for one workload: enough identity for Kustomize
    to match it, and nothing but the containers' resources to merge in."""
    containers = [
        {"name": recommendation["container"], "resources": block}
        for recommendation in recommendations
        if (block := resources_block(recommendation["proposed"]))
    ]
    if not containers:
        return None
    first = recommendations[0]
    kind = first["kind"]
    pod_template = {"spec": {"containers": containers}}
    # A CronJob wraps its pod template one level deeper than everything else.
    spec = {"jobTemplate": {"spec": {"template": pod_template}}} if kind == "CronJob" else {"template": pod_template}
    return {
        "apiVersion": API_VERSIONS.get(kind, DEFAULT_API_VERSION),
        "kind": kind,
        "metadata": {"name": first["workload"], "namespace": first["namespace"]},
        "spec": spec,
    }


def group_by_workload(recommendations: Sequence[Recommendation]) -> dict[tuple[str, str, str], list[Recommendation]]:
    grouped: dict[tuple[str, str, str], list[Recommendation]] = {}
    for recommendation in recommendations:
        identity = (recommendation["namespace"], recommendation["kind"], recommendation["workload"])
        grouped.setdefault(identity, []).append(recommendation)
    return grouped


def patch_filename(namespace: str, kind: str, workload: str) -> str:
    return f"{namespace}-{kind.lower()}-{workload}.yaml"


def kustomize_patches(recommendations: Sequence[Recommendation]) -> list[tuple[str, Manifest]]:
    """[(filename, patch), ...] — one strategic-merge patch per workload."""
    patches: list[tuple[str, Manifest]] = []
    for (namespace, kind, workload), group in group_by_workload(recommendations).items():
        patch = workload_patch(group)
        if patch is not None:
            patches.append((patch_filename(namespace, kind, workload), patch))
    return patches


def render_patches(patches: Sequence[tuple[str, Manifest]]) -> str:
    if not patches:
        return ""
    documents: list[str] = []
    for filename, patch in patches:
        documents.append(f"# {filename}\n{yaml.dump(patch, sort_keys=False)}")
    return "---\n".join(documents)


def write_patches(patch_dir: Path, patches: Sequence[tuple[str, Manifest]]) -> list[Path]:
    patch_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, patch in patches:
        path = patch_dir / filename
        path.write_text(yaml.dump(patch, sort_keys=False), encoding="utf-8")
        written.append(path)
    return written


# ---------------------------------------------------------------- helm mode


def parse_helm_keys(entries: Sequence[str]) -> dict[str, str]:
    """`--helm-key api/app=api.resources` -> {"api/app": "api.resources"}."""
    mapping: dict[str, str] = {}
    for entry in entries:
        name, separator, path = entry.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise ValueError(f"--helm-key wants WORKLOAD[/CONTAINER]=DOTTED.PATH, got {entry!r}")
        mapping[name.strip()] = path.strip()
    return mapping


def values_path(
    values: Manifest, recommendation: Recommendation, overrides: Mapping[str, str], single: bool
) -> list[str] | None:
    """Where in the values file this container's `resources` live.

    Charts do not agree on this, so guess only where the guess is obvious — a
    subtree named after the workload or the container, or the top-level
    `resources` of a single-workload chart — and let --helm-key say the rest."""
    workload, container = recommendation["workload"], recommendation["container"]
    for candidate in (overrides.get(f"{workload}/{container}"), overrides.get(workload)):
        if candidate:
            return candidate.split(".")
    if isinstance(values.get(workload), dict):
        return [workload, "resources"]
    if isinstance(values.get(container), dict):
        return [container, "resources"]
    if single and "resources" in values:
        return ["resources"]
    return None


def _set_path(tree: Manifest, path: Sequence[str], value: Any) -> None:
    node = tree
    for segment in path[:-1]:
        # section() hands back the branch that is there, or a fresh one when the
        # chart has nothing (or something that is not a mapping) at that key.
        child = section(node, segment)
        node[segment] = child
        node = child
    node[path[-1]] = value


def helm_values_update(
    values: Manifest, recommendations: Sequence[Recommendation], overrides: Mapping[str, str]
) -> tuple[Manifest, list[str], list[Recommendation]]:
    """(updated values, paths written, recommendations with nowhere to go)."""
    updated = copy.deepcopy(values)
    written: list[str] = []
    unmatched: list[Recommendation] = []
    single = len(recommendations) == 1
    for recommendation in recommendations:
        block = resources_block(recommendation["proposed"])
        path = values_path(values, recommendation, overrides, single) if block else None
        if path is None:
            unmatched.append(recommendation)
            continue
        _set_path(updated, path, block)
        written.append(".".join(path))
    return updated, written, unmatched


def helm_values_diff(path: Path, original: Manifest, updated: Manifest) -> str:
    """A unified diff of the values file, normalised through PyYAML on both
    sides so the diff shows the resource changes and nothing else."""
    before = yaml.dump(original, sort_keys=False).splitlines(keepends=True)
    after = yaml.dump(updated, sort_keys=False).splitlines(keepends=True)
    return "".join(difflib.unified_diff(before, after, fromfile=f"a/{path}", tofile=f"b/{path}"))


# ------------------------------------------------------------------ renderers


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = [f"| {' | '.join(header)} |", f"|{'|'.join(['---'] * len(header))}|"]
    lines += [f"| {' | '.join(row)} |" for row in rows]
    return lines


def _proposed_rows(recommendations: Sequence[Recommendation]) -> list[list[str]]:
    return [
        [
            f"{recommendation['kind']}/{recommendation['workload']}",
            recommendation["container"],
            fmt_pair(recommendation["current"].get("requests")),
            fmt_pair(recommendation["proposed"].get("requests")),
            fmt_pair(recommendation["current"].get("limits")),
            fmt_pair(recommendation["proposed"].get("limits")),
            f"{recommendation['stability']['streak']} runs",
        ]
        for recommendation in recommendations
    ]


def _held_rows(recommendations: Sequence[Recommendation]) -> list[list[str]]:
    return [
        [
            f"{recommendation['kind']}/{recommendation['workload']}",
            recommendation["container"],
            recommendation["status"],
            range_text(recommendation["stability"]),
        ]
        for recommendation in recommendations
    ]


def render_report(
    proposed: Sequence[Recommendation],
    held: Sequence[Recommendation],
    rule: Rule,
    history_dir: Path,
    run_count: int,
) -> str:
    lines = [
        "# Rightsizing — KRR recommendations, filtered for stability\n",
        f"Engine: KRR (robusta-dev/krr) · history: `{history_dir}` ({run_count} runs)",
        f"Rule: {rule.describe()}.\n",
    ]
    if proposed:
        lines.append(f"## Proposed ({len(proposed)})\n")
        lines += _table(
            ["workload", "container", "current req", "proposed req", "current lim", "proposed lim", "stable for"],
            _proposed_rows(proposed),
        )
        saving = monthly_saving(proposed)
        if saving is not None:
            lines.append(f"\nProjected saving: {saving:,.2f}/month (KRR's costing).")
        lines.append("")
    else:
        lines.append("## Proposed (0)\n\nNothing has settled yet — nothing to propose.\n")
    if held:
        lines.append(f"## Not yet ({len(held)})\n")
        lines += _table(["workload", "container", "why", f"range over the last {rule.runs} runs"], _held_rows(held))
        lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class Target:
    """Where the change is going: the branch it lands on, the repository that
    serves the links, and the run file the body points a reviewer at."""

    branch: str
    repo: str | None = None
    run_path: Path | None = None

    def history_link(self) -> str:
        if self.run_path is None:
            return "not recorded (`--no-record`)"
        if self.repo:
            return f"[`{self.run_path}`](https://github.com/{self.repo}/blob/{self.branch}/{self.run_path.as_posix()})"
        return f"`{self.run_path}`"


def render_pr_body(
    proposed: Sequence[Recommendation],
    held: Sequence[Recommendation],
    rule: Rule,
    target: Target,
) -> str:
    lines = [
        f"KRR (robusta-dev/krr) computed these recommendations from Prometheus history; this pull request "
        f"proposes only the ones that have settled — {rule.describe()}.\n",
        f"## Proposed ({len(proposed)})\n",
    ]
    for (namespace, kind, workload), group in group_by_workload(proposed).items():
        lines.append(f"### `{kind} {namespace}/{workload}`\n")
        lines += _table(
            ["container", "requests (now → proposed)", "limits (now → proposed)", "stable for"],
            [
                [
                    recommendation["container"],
                    f"{fmt_pair(recommendation['current'].get('requests'))} → "
                    f"{fmt_pair(recommendation['proposed'].get('requests'))}",
                    f"{fmt_pair(recommendation['current'].get('limits'))} → "
                    f"{fmt_pair(recommendation['proposed'].get('limits'))}",
                    f"{recommendation['stability']['streak']} runs",
                ]
                for recommendation in group
            ],
        )
        saving = monthly_saving(group)
        if saving is not None:
            lines.append(f"\nProjected saving: **{saving:,.2f}/month**")
        lines.append("")
    total = monthly_saving(proposed)
    if total is not None:
        lines.append(f"Projected saving across this pull request: **{total:,.2f}/month** (KRR's costing).\n")
    if held:
        lines.append(f"## Held back ({len(held)})\n")
        lines.append("Still moving, so not proposed:\n")
        lines += _table(["workload", "container", "why", f"range over the last {rule.runs} runs"], _held_rows(held))
        lines.append("")
    lines.append(f"History for this run: {target.history_link()}")
    return "\n".join(lines)


# ------------------------------------------------------------- pull requests


def _run(argv: list[str], *, stdin: str | None = None) -> str:
    """Every shell-out goes through here, so the failure behaviour (check=True,
    stderr surfaced) is decided in one place."""
    executable = shutil.which(argv[0])
    if executable is None:
        raise RuntimeError(f"{argv[0]} is not on PATH")
    completed = subprocess.run(  # noqa: S603 — argv is built here, never a string
        [executable, *argv[1:]],
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return completed.stdout


def repo_slug() -> str | None:
    """`owner/repo`, for linking the history file. Best effort: without it the
    body still names the path, it just is not a link."""
    try:
        return _run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip() or None
    except (RuntimeError, subprocess.SubprocessError):
        return None


def default_branch_name(now: datetime) -> str:
    return f"rightsizer/{now.strftime('%Y%m%d-%H%M%S')}"


def open_pull_request(paths: Sequence[Path], branch: str, title: str, body: str) -> str:
    """Commit the change on its own branch and open the pull request with gh."""
    _run(["git", "switch", "-c", branch])
    _run(["git", "add", "--", *[str(path) for path in paths]])
    _run(["git", "commit", "-m", title])
    _run(["git", "push", "-u", "origin", branch])
    return _run(["gh", "pr", "create", "--title", title, "--body-file", "-"], stdin=body).strip()


# ----------------------------------------------------------------------- CLI


class _RefuseApply(argparse.Action):
    """--apply is deliberately not provided, and saying so beats "unrecognized
    argument" when someone reaches for the habit."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        parser.error(
            "--apply is deliberately not provided: this tool proposes changes for review. "
            "Merge the pull request and let your GitOps tooling roll it out."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-rightsizer-report",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--namespace", "-n", help="namespace to scan (passed to krr; filters a --krr-json file)")
    parser.add_argument("--krr-json", metavar="FILE", help="read `krr simple --formatter json` output ('-' for stdin)")
    parser.add_argument(
        "--krr-arg", action="append", default=[], metavar="ARG", help="extra argument for krr (repeatable)"
    )
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR, help=f"default: {DEFAULT_HISTORY_DIR}")
    parser.add_argument("--patch-dir", default=DEFAULT_PATCH_DIR, help=f"default: {DEFAULT_PATCH_DIR}")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE_PCT,
        metavar="PCT",
        help=f"a recommendation counts as unchanged within this %% (default: {DEFAULT_TOLERANCE_PCT:g})",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_STABLE_RUNS,
        metavar="N",
        help=f"consecutive runs within --tolerance before proposing (default: {DEFAULT_STABLE_RUNS})",
    )
    parser.add_argument("--no-record", dest="record", action="store_false", help="do not store this run in the history")
    parser.add_argument("--helm-values", metavar="FILE", help="emit a values diff for this chart instead of patches")
    parser.add_argument(
        "--helm-key",
        action="append",
        default=[],
        metavar="W[/C]=PATH",
        help="where a workload's resources live in the values file (repeatable)",
    )
    parser.add_argument("--write", action="store_true", help="write the patches / values update to disk")
    parser.add_argument("--pr", action="store_true", help="commit the change and open a pull request with gh")
    parser.add_argument("--branch", help="branch name for --pr (default: rightsizer/<timestamp>)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--apply", nargs=0, action=_RefuseApply, help=argparse.SUPPRESS)
    return parser


def ingest(args: argparse.Namespace) -> tuple[Manifest, str]:
    if args.krr_json:
        return load_krr(args.krr_json), f"file:{args.krr_json}"
    return run_krr(args.namespace, args.krr_arg), "krr " + " ".join(KRR_BASE_ARGS)


def _emit_helm(args: argparse.Namespace, proposed: Sequence[Recommendation]) -> tuple[str, list[Path], list[str]]:
    """(diff to print, files changed, warnings)."""
    path = Path(args.helm_values)
    original = mapping(yaml.safe_load(path.read_text(encoding="utf-8")))
    updated, written, unmatched = helm_values_update(original, proposed, parse_helm_keys(args.helm_key))
    warnings = [
        f"no place found in {path} for {recommendation['key']} — point at it with --helm-key"
        for recommendation in unmatched
    ]
    if not written:
        return "", [], warnings
    diff = helm_values_diff(path, original, updated)
    changed: list[Path] = []
    if args.write or args.pr:
        # PyYAML cannot round-trip comments, so the file comes back normalised.
        path.write_text(yaml.dump(updated, sort_keys=False), encoding="utf-8")
        warnings.append(f"{path} was rewritten by PyYAML: comments and formatting are normalised — review the diff")
        changed.append(path)
    return diff, changed, warnings


def _emit_kustomize(args: argparse.Namespace, proposed: Sequence[Recommendation]) -> tuple[str, list[Path]]:
    patches = kustomize_patches(proposed)
    changed = write_patches(Path(args.patch_dir), patches) if (args.write or args.pr) else []
    return render_patches(patches), changed


def _json_payload(
    proposed: Sequence[Recommendation], held: Sequence[Recommendation], rule: Rule, run_path: Path | None
) -> Manifest:
    return {
        "engine": "krr",
        "rule": {"tolerance_pct": rule.tolerance_pct, "runs": rule.runs, "description": rule.describe()},
        "history_file": str(run_path) if run_path else None,
        "proposed": list(proposed),
        "held": list(held),
        "projected_monthly_saving": monthly_saving(proposed),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rule = Rule(tolerance_pct=args.tolerance, runs=args.runs)
    document, source = ingest(args)
    recommendations = normalise(document, args.namespace)

    now = datetime.now(tz=timezone.utc)
    history_dir = Path(args.history_dir)
    runs = load_history(history_dir)
    run = as_run(recommendations, source, now)
    recorded = write_run(history_dir, run, now) if args.record else None
    runs.append(run)

    proposed, held = classify(runs, rule)
    branch = args.branch or default_branch_name(now)

    warnings: list[str] = []
    if args.helm_values:
        change, changed, warnings = _emit_helm(args, proposed)
    else:
        change, changed = _emit_kustomize(args, proposed)

    if args.json:
        payload = _json_payload(proposed, held, rule, recorded)
        payload["change"] = change
        payload["files"] = [str(path) for path in changed]
        payload["warnings"] = warnings
        json.dump(payload, sys.stdout, indent=2)
        print()  # noqa: T201 — the tool's output
    else:
        print(render_report(proposed, held, rule, history_dir, len(runs)))  # noqa: T201 — the tool's output
        if change:
            print(change)  # noqa: T201 — the tool's output
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)  # noqa: T201 — the tool's output

    if args.pr:
        if not changed:
            print("nothing stable to propose — no pull request opened", file=sys.stderr)  # noqa: T201
            return 0
        paths = [*changed, *([recorded] if recorded else [])]
        body = render_pr_body(proposed, held, rule, Target(branch, repo_slug(), recorded))
        title = f"chore(rightsizing): {len(proposed)} stable recommendation(s) from KRR"
        url = open_pull_request(paths, branch, title, body)
        # With --json, stdout is the payload and nothing else; the URL goes
        # where a person reads it rather than where a parser does.
        print(url, file=sys.stderr if args.json else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

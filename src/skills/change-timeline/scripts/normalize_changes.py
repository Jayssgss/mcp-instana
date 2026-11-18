#!/usr/bin/env python3
"""Normalize change-timeline Phase 2 results into the standard timeline envelope.

Offline helper for ``src/skills/change-timeline/SKILL.md`` (Phase 3).
Output follows ``references/output-schema.md``.

Input (JSON, from a file path or stdin)::

    {
      "scope": {
        "scope_type": "application" | "service",
        "application_id": "...", "service_id": "...", "label": "...",
        "kubernetes_cluster_name": "..." | null,
        "kubernetes_namespace_name": "..." | null
      },
      "window": {"from": <epoch_ms>, "to": <epoch_ms>},
      "max_changes": 50,                       # optional
      "sources": {
        "releases":          <get_all_releases response>,
        "events":            <get_events response>,
        "kubernetes_events": <get_kubernetes_info_events response>
      }
    }

A source whose value is ``null``/missing, or a dict containing an ``error`` key,
is treated as failed and reported in ``notes``.

Usage::

    python normalize_changes.py input.json
    cat input.json | python normalize_changes.py -
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_CHANGES = 50
DETAIL_MAX_LEN = 140
ENTITY_EVENT_CAP = 50
K8S_EVENT_CAP = 200
NOT_QUERIED = "not queried (namespace resolved)"

_SEVERITY_BY_VALUE = {10: "critical", 5: "warning", -1: "change"}
_UNRESOLVED_TOPOLOGY = {"", "unknown", NOT_QUERIED}


def _known_topology(value: Any) -> Optional[str]:
    """Return a real cluster/namespace name, or None when it is missing or a placeholder.

    SKILL.md tells the model to record the literal strings ``unknown`` and
    ``not queried (namespace resolved)``; both mean "no usable name".
    """
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _UNRESOLVED_TOPOLOGY else text


def _safe_int_ts(value: Any) -> int:
    """Convert an epoch-ms value (int, float, numeric/float string) to int; 0 if unusable."""
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(value) if isinstance(value, (int, float)) else int(float(str(value).strip()))
    except (ValueError, TypeError, OverflowError):
        return 0


def _iso(ms: Any) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truncate(text: Any, limit: int = DETAIL_MAX_LEN) -> str:
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _source_failure(payload: Any) -> Optional[str]:
    """Return a failure reason, or None when the source responded."""
    if payload is None:
        return "no result provided"
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return None


def _scope_names(release: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for item in release.get("scopes") or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("label")
            if name:
                names.append(str(name))
    return names


def _normalize_releases(
    payload: Dict[str, Any], scope: Dict[str, Any], notes: List[str]
) -> List[Dict[str, Any]]:
    label = str(scope.get("label") or "").lower()
    records: List[Dict[str, Any]] = []
    out_of_scope: List[str] = []
    for release in payload.get("releases") or []:
        if not isinstance(release, dict):
            continue
        name = release.get("name") or ""
        if label and label in (n.lower() for n in _scope_names(release)):
            records.append({
                "id": str(release.get("id") or f"release:{name}:{release.get('start')}"),
                "ts": _safe_int_ts(release.get("start")),
                "type": "release",
                "title": f"Release: {name}",
                "detail": _truncate(f"Release {name} deployed"),
                "entity": scope.get("label"),
                "service_id": scope.get("service_id"),
                "severity": "change",
                "source_layer": "entity",
                "match_confidence": "exact",
            })
        else:
            out_of_scope.append(name)
    if out_of_scope:
        notes.append(
            f"{len(out_of_scope)} release(s) out of scope (scope name did not exactly match "
            f"'{scope.get('label')}'): {', '.join(out_of_scope)}"
        )
    return records


def _event_in_scope(event: Dict[str, Any], scope: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (in_scope, match_confidence) per the SKILL.md entity filter order."""
    entity = event.get("entity")
    if not isinstance(entity, dict):
        entity = {"label": str(entity)} if entity else {}

    if scope.get("scope_type") == "application":
        key, expected = "applicationId", scope.get("application_id")
    else:
        key, expected = "serviceId", scope.get("service_id")
    if entity.get(key):
        return entity[key] == expected, "exact"
    label = str(entity.get("label") or "").lower()
    return label == str(scope.get("label") or "").lower(), "heuristic"


def _normalize_entity_events(
    payload: Dict[str, Any], scope: Dict[str, Any], notes: List[str]
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    dropped = 0
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        in_scope, confidence = _event_in_scope(event, scope)
        if not in_scope:
            dropped += 1
            continue
        raw_ts = event.get("timestamp") if event.get("timestamp") is not None else event.get("start")
        ts = _safe_int_ts(raw_ts)
        entity = event.get("entity")
        if not isinstance(entity, dict):
            entity = {"label": str(entity)} if entity else {}
        problem = event.get("problem") or event.get("type") or "event"
        records.append({
            "id": str(event.get("eventId") or f"event:{ts}:{problem}"),
            "ts": ts,
            "type": "change_event",
            "title": str(problem),
            "detail": _truncate(event.get("detail") or problem),
            "entity": entity.get("label") or scope.get("label"),
            "service_id": entity.get("serviceId") or scope.get("service_id"),
            "severity": _SEVERITY_BY_VALUE.get(event.get("severity"), "change"),
            "source_layer": "entity",
            "match_confidence": confidence,
        })
    if dropped:
        notes.append(f"{dropped} entity event(s) dropped as out of scope (ID/label mismatch).")
    if payload.get("events_returned") == ENTITY_EVENT_CAP:
        notes.append(
            f"Entity events may be truncated: {ENTITY_EVENT_CAP} events returned for '{scope.get('label')}'."
        )
    return records


def _normalize_k8s_events(
    payload: Dict[str, Any], scope: Dict[str, Any], notes: List[str]
) -> List[Dict[str, Any]]:
    if scope.get("k8s_scope_mode") == "non-kubernetes":
        return []

    analyzed = payload.get("events_analyzed")
    total = payload.get("events_count")
    if analyzed == K8S_EVENT_CAP:
        unanalyzed = (total - analyzed) if isinstance(total, int) else "unknown"
        notes.append(
            f"Kubernetes event truncation (tool cap): {K8S_EVENT_CAP} of possibly more matched events analyzed ({unanalyzed} not analyzed)."
        )
    if isinstance(total, int) and (total >= 1000 and total % 1000 == 0 or total == 10000):
        notes.append(
            f"Kubernetes event truncation (API cap): the API returned exactly {total} events, which matches a server-side cap; the effective window may be shorter than requested. Consider re-running with a narrower window."
        )
    if payload.get("events_filtered_out"):
        notes.append(f"Kubernetes events dropped by entity label filter: {payload['events_filtered_out']}.")

    events = [e for e in payload.get("events") or [] if isinstance(e, dict)]
    ns_name = _known_topology(scope.get("kubernetes_namespace_name"))
    cluster_name = _known_topology(scope.get("kubernetes_cluster_name"))

    if not cluster_name and not ns_name:
        if events:
            notes.append(
                f"{len(events)} Kubernetes event(s) not verified to this entity (cluster and namespace "
                "unknown); excluded from the timeline."
            )
        return []

    # Exact namespace post-filter when namespace is known
    matched_events: List[Dict[str, Any]] = []
    if ns_name:
        target_ns = ns_name.strip("/").lower()
        foreign_counts: Dict[str, int] = {}
        for event in events:
            raw_label = str(event.get("entityLabel") or "")
            parts = raw_label.split("/", 1)
            event_ns = parts[0].lower() if len(parts) > 1 else raw_label.lower()
            if event_ns == target_ns:
                matched_events.append(event)
            else:
                foreign_counts[parts[0] if len(parts) > 1 else raw_label] = (
                    foreign_counts.get(parts[0] if len(parts) > 1 else raw_label, 0) + 1
                )
        if foreign_counts:
            summary = ", ".join(f"{ns}: {cnt}" for ns, cnt in foreign_counts.items())
            notes.append(f"Adjacent-namespace events excluded from Timeline: {summary}.")
    else:
        # Cluster-scoped fallback
        matched_events = events
        notes.append(f"Kubernetes scope verification is cluster-level only ({cluster_name}).")

    records: List[Dict[str, Any]] = []
    for event in matched_events:
        problem = event.get("problem") or "Kubernetes event"
        records.append({
            "id": str(event.get("eventId")),
            "ts": _safe_int_ts(event.get("start")),
            "type": "k8s_event",
            "title": str(problem),
            "detail": _truncate(event.get("detail") or problem),
            "entity": event.get("entityLabel") or "",
            "service_id": None,
            "severity": "info",
            "source_layer": "infrastructure",
            "match_confidence": "heuristic",
        })
    return records


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build the get_changes envelope from raw Phase 1 / Phase 2 data."""
    scope_in = data.get("scope") or {}
    window_in = data.get("window") or {}
    sources = data.get("sources") or {}
    max_changes = int(data.get("max_changes") or DEFAULT_MAX_CHANGES)

    # "unknown" / "not queried" placeholders are normalized to None so they can
    # never be mistaken for a real cluster or namespace name.
    k8s_cluster = _known_topology(scope_in.get("kubernetes_cluster_name"))
    k8s_ns = _known_topology(scope_in.get("kubernetes_namespace_name"))
    cluster_not_queried = (
        str(scope_in.get("kubernetes_cluster_name") or "").strip().lower() == NOT_QUERIED
    )
    k8s_mode = scope_in.get("k8s_scope_mode")

    if not k8s_mode:
        if k8s_ns:
            k8s_mode = "namespace-scoped"
        elif k8s_cluster:
            k8s_mode = "cluster-scoped"
        else:
            k8s_mode = "unscoped"

    scope = {
        "scope_type": scope_in.get("scope_type"),
        "service_id": scope_in.get("service_id"),
        "application_id": scope_in.get("application_id"),
        "label": scope_in.get("label"),
        "kubernetes_cluster_name": NOT_QUERIED if cluster_not_queried else k8s_cluster,
        "kubernetes_namespace_name": k8s_ns,
        "k8s_scope_mode": k8s_mode,
    }
    notes: List[str] = []
    if k8s_mode == "non-kubernetes":
        notes.append("Entity is not Kubernetes-backed (k8s_scope_mode: non-kubernetes).")
    else:
        if not k8s_cluster and not cluster_not_queried:
            notes.append("kubernetes_cluster_name is unknown.")
        if not k8s_ns:
            notes.append("kubernetes_namespace_name is unknown.")

    handlers = (
        ("releases", _normalize_releases),
        ("events", _normalize_entity_events),
        ("kubernetes_events", _normalize_k8s_events),
    )
    records: List[Dict[str, Any]] = []
    sources_queried: List[str] = []
    for name, handler in handlers:
        if name == "kubernetes_events" and k8s_mode == "non-kubernetes":
            continue
        payload = sources.get(name)
        failure = _source_failure(payload)
        if failure:
            notes.append(f"Source '{name}' failed: {failure}")
            continue
        sources_queried.append(name)
        records.extend(handler(payload, scope, notes))

    deduped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for record in records:
        deduped.setdefault((record["type"], record["id"]), record)
    changes = sorted(deduped.values(), key=lambda r: (r["ts"], r["id"]))
    undated = sum(1 for r in changes if r["ts"] <= 0)
    if undated:
        notes.append(f"{undated} record(s) had a missing or unparseable timestamp (ts=0); treat their ordering as unreliable.")

    dropped = max(0, len(changes) - max_changes)
    if dropped:
        changes = changes[dropped:]  # keep the most recent max_changes
        notes.append(f"{dropped} oldest record(s) dropped beyond max_changes={max_changes}.")

    counts = {"release": 0, "change_event": 0, "kubernetes_info_event": 0}
    for record in changes:
        if record["type"] == "release":
            counts["release"] += 1
        elif record["type"] == "k8s_event":
            counts["kubernetes_info_event"] += 1
        else:
            counts["change_event"] += 1

    window_from, window_to = window_in.get("from"), window_in.get("to")
    window = {
        "from": window_from,
        "to": window_to,
        "from_iso": _iso(window_from) if window_from is not None else None,
        "to_iso": _iso(window_to) if window_to is not None else None,
    }

    return {
        "scope": scope,
        "window": window,
        "changes": changes,
        "counts_by_type": counts,
        "sources_queried": sources_queried,
        "truncated": dropped > 0,
        "dropped": dropped,
        "notes": notes,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize change-timeline results into a timeline envelope.")
    parser.add_argument("input", help="Path to input JSON, or '-' for stdin")
    args = parser.parse_args(argv)

    try:
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.input, encoding="utf-8") as fh:
                data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("input JSON must be an object")
        result = normalize(data)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

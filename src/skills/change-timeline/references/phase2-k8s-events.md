# Phase 2 — Kubernetes Info Events Call Specification

Full call parameters, entity-label filter rules, response fields, and truncation rules for the
`manage_events(operation="get_kubernetes_info_events", ...)` call in Phase 2.

---

## Call parameters

Issue exactly 1 call:
```
manage_events(
  operation="get_kubernetes_info_events",
  params={
    "from_time": <epoch_ms_start>,
    "to_time": <epoch_ms_end>,
    "entity_label": "<entity_label_filter>",
    "max_events": 200
  }
)
```

Set `entity_label` according to `k8s_scope_mode`:
- If `namespace-scoped`: set `entity_label` to `"<kubernetes_namespace_name>/"` (with trailing slash, e.g. `"robot-shop/"`). The trailing slash ensures the tool's substring match excludes sibling namespaces (such as `robot-shop-dev`) before the 200-event cap. Note: `kubernetes_namespace_name` in Phase 1 output and Phase 3 synthesis remains the bare namespace name (without slash).
- If `cluster-scoped`: set `entity_label` to `kubernetes_cluster_name` (no slash).
- If `unscoped`: omit `entity_label` and still issue the call; the returned events cannot be scoped to the entity.
- Do NOT pass the application or service label as `entity_label` — Kubernetes event entity labels do not contain application or service names, so such a filter drops every event.

---

## Entity label filter (two stages)

`entity_label` is applied by the tool as a case-insensitive **substring** match on each event's `entityLabel`, before the `max_events` cap (200). Because it is a substring match, after the call apply an **exact post-filter**:
- If the call was **namespace-scoped**: split each event's `entityLabel` on the first `/`; keep the event in the Timeline only when the namespace component equals `kubernetes_namespace_name` (case-insensitive **exact** match against bare name). Events from other namespaces (e.g. `robot-shop-dev` when resolved namespace is `robot-shop`) MUST NOT appear in the Timeline and are omitted from the output.
- If the call was **cluster-scoped**: keep all returned events in the Timeline.
- If the call was **unscoped**: guard clause 7 applies — events have unverified scope and are omitted from the Timeline.

---

## Response fields used in Phase 3

- `events_analyzed`: events kept after the tool's substring filter and the `max_events` cap.
- `events_count`: total events the API returned for the window **before** filtering.
- `events_filtered_out`: events dropped by the tool's substring filter (`events_count − events_analyzed`, approximately).

---

## Truncation rules (evaluate both; they are independent)

1. **Tool cap:** if `events_analyzed = max_events` (200), the matched set may be truncated.
2. **API cap:** if `events_count` equals a round cap value (10,000 or any suspiciously exact power-of-ten ≥ 1,000), the API itself likely truncated the window — events may be missing from the window **entirely, before any filtering**.

Truncation is not reported as a separate section of the synthesized output. Never state that a result "hit the cap" when the analyzed count is below the cap.

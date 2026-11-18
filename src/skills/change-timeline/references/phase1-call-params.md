# Phase 1 — Call Parameter Templates

Full JSON call templates for Phase 1 entity resolution and Kubernetes topology discovery.
These cover both Application scope and Service scope paths.

---

### Application Scope Resolution

Follow this sequence exactly when scope type is **application**:

**Step A — Resolve the application:**
```
manage_applications(
  resource_type="resources",
  operation="get_applications",
  params={"name_filter": "<name from query>"}
)
```
- If one or more items have a label that exactly matches the query name (case-insensitive), use the **first exact match's** `id` as `application_id`. Do NOT ask the user to clarify, even if other partial or substring matches are also present.
- If **no** exact match is found but multiple candidates are returned, **stop and ask the user to pick one** from the list. Do NOT proceed to Step B with an ambiguous `application_id`.
- If `get_applications` returns no items, report the failure and do not proceed to Phase 2.

**Step B′ — Discover underlying Kubernetes namespace (always):**
```
manage_applications(
  resource_type="metrics",
  operation="get_grouped_calls_metrics",
  params={
    "metrics": [{"metric": "calls", "aggregation": "SUM"}],
    "tag_filter_expression": {
      "type": "TAG_FILTER",
      "name": "application.name",
      "operator": "EQUALS",
      "entity": "DESTINATION",
      "value": "<resolved application label>"
    },
    "group": {"groupbyTag": "kubernetes.namespace.name", "groupbyTagEntity": "DESTINATION"},
    "order": {"by": "calls", "direction": "DESC"},
    "pagination": {"page": 1, "pageSize": 10},
    "time_frame": {"to": <epoch_ms_end>, "windowSize": <window_ms>},
    "include_internal": false,
    "include_synthetic": false
  }
)
```
Record the top-ranked `kubernetes.namespace.name` value as `kubernetes_namespace_name` (as the bare name, e.g. `robot-shop`). If no results are returned, record `kubernetes_namespace_name` as `unknown`.

**Step C′ — Discover underlying Kubernetes cluster (conditional):**
Issue this call **only if Step B′ returned zero Kubernetes groups**. If Step B′ resolved a namespace, record `kubernetes_cluster_name: not queried (namespace resolved)` and do NOT issue this call.
```
manage_applications(
  resource_type="metrics",
  operation="get_grouped_calls_metrics",
  params={
    "metrics": [{"metric": "calls", "aggregation": "SUM"}],
    "tag_filter_expression": {
      "type": "TAG_FILTER",
      "name": "application.name",
      "operator": "EQUALS",
      "entity": "DESTINATION",
      "value": "<resolved application label>"
    },
    "group": {"groupbyTag": "kubernetes.cluster.name", "groupbyTagEntity": "DESTINATION"},
    "order": {"by": "calls", "direction": "DESC"},
    "pagination": {"page": 1, "pageSize": 10},
    "time_frame": {"to": <epoch_ms_end>, "windowSize": <window_ms>},
    "include_internal": false,
    "include_synthetic": false
  }
)
```
Record the top-ranked `kubernetes.cluster.name` value as `kubernetes_cluster_name`. If no results are returned, record `kubernetes_cluster_name` as `unknown`.

> **Non-Kubernetes detection:** If Steps B′ and C′ both return zero `kubernetes.*` tag groups **and** the entity demonstrably has call traffic in the window (the grouped-metrics responses contain data — just no Kubernetes tag values), set `k8s_scope_mode: non-kubernetes`. If the calls returned nothing at all (no traffic, error, or empty response), the evidence is ambiguous: keep `unknown`/`unscoped` and current behavior. Never classify `non-kubernetes` without positive evidence.

> **NO SERVICE FAN-OUT:** Do NOT call `get_application_services`, `get_tag_catalog`, or any additional `get_grouped_calls_metrics` calls beyond Steps B′ and C′. The scope is the single resolved application — not its individual services.

---

### Service Scope Resolution

Follow this sequence exactly when scope type is **service**:

**Step A — Resolve the service:**
```
manage_applications(
  resource_type="resources",
  operation="get_services",
  params={"name_filter": "<name from query>"}
)
```
- If one or more items have a label that exactly matches the query name (case-insensitive), use the **first exact match's** `id` as `service_id`. Do NOT ask the user to clarify, even if other partial or substring matches are also present.
- If **no** exact match is found but multiple candidates are returned, **stop and ask the user to pick one** from the list. Do NOT proceed to Step B with an ambiguous `service_id`.
- If `get_services` returns no items, report the failure and do not proceed to Phase 2.

**Step B′ — Discover underlying Kubernetes namespace (always):**
```
manage_applications(
  resource_type="metrics",
  operation="get_grouped_calls_metrics",
  params={
    "metrics": [{"metric": "calls", "aggregation": "SUM"}],
    "tag_filter_expression": {
      "type": "TAG_FILTER",
      "name": "service.name",
      "operator": "EQUALS",
      "entity": "DESTINATION",
      "value": "<resolved service label>"
    },
    "group": {"groupbyTag": "kubernetes.namespace.name", "groupbyTagEntity": "DESTINATION"},
    "order": {"by": "calls", "direction": "DESC"},
    "pagination": {"page": 1, "pageSize": 10},
    "time_frame": {"to": <epoch_ms_end>, "windowSize": <window_ms>},
    "include_internal": false,
    "include_synthetic": false
  }
)
```
Record the top-ranked `kubernetes.namespace.name` value as `kubernetes_namespace_name` (as the bare name, e.g. `robot-shop`). If no results are returned, record `kubernetes_namespace_name` as `unknown`.

**Step C′ — Discover underlying Kubernetes cluster (conditional):**
Issue this call **only if Step B′ returned zero Kubernetes groups**. If Step B′ resolved a namespace, record `kubernetes_cluster_name: not queried (namespace resolved)` and do NOT issue this call.
```
manage_applications(
  resource_type="metrics",
  operation="get_grouped_calls_metrics",
  params={
    "metrics": [{"metric": "calls", "aggregation": "SUM"}],
    "tag_filter_expression": {
      "type": "TAG_FILTER",
      "name": "service.name",
      "operator": "EQUALS",
      "entity": "DESTINATION",
      "value": "<resolved service label>"
    },
    "group": {"groupbyTag": "kubernetes.cluster.name", "groupbyTagEntity": "DESTINATION"},
    "order": {"by": "calls", "direction": "DESC"},
    "pagination": {"page": 1, "pageSize": 10},
    "time_frame": {"to": <epoch_ms_end>, "windowSize": <window_ms>},
    "include_internal": false,
    "include_synthetic": false
  }
)
```
Record the top-ranked `kubernetes.cluster.name` value as `kubernetes_cluster_name`. If no results are returned, record `kubernetes_cluster_name` as `unknown`.

> **Non-Kubernetes detection:** If Steps B′ and C′ both return zero `kubernetes.*` tag groups **and** the entity demonstrably has call traffic in the window (the grouped-metrics responses contain data — just no Kubernetes tag values), set `k8s_scope_mode: non-kubernetes`. If the calls returned nothing at all (no traffic, error, or empty response), the evidence is ambiguous: keep `unknown`/`unscoped` and current behavior. Never classify `non-kubernetes` without positive evidence.

> **NO CALLER/CALLEE FAN-OUT:** Do NOT call `get_tag_catalog` or any additional `get_grouped_calls_metrics` calls beyond Steps B′ and C′. The scope is the single resolved service — do NOT expand to callers, callees, or the whole application.

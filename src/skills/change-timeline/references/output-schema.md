# ChangeRecord — Output Schema

> **Scope note:** The skill supports two scope types. In **service scope**, `scope.service_id` is the primary identifier and `scope.application_id` is null. In **application scope**, `scope.application_id` is the primary identifier and `scope.service_id` is null. Both scope types include `scope.kubernetes_cluster_name`, `scope.kubernetes_namespace_name`, and `scope.k8s_scope_mode` reflecting the infrastructure topology discovered in Phase 1.

## get_changes envelope

```json
{
  "scope": {
    "scope_type":                "string  — 'application' | 'service'",
    "service_id":                "string | null  — resolved Instana service ID (service scope) or null (application scope)",
    "application_id":            "string | null  — resolved Instana application ID (application scope) or null (service scope)",
    "label":                     "string  — primary entity display name",
    "kubernetes_cluster_name":   "string | null  — Kubernetes cluster name discovered in Phase 1, 'not queried (namespace resolved)', or null if unknown",
    "kubernetes_namespace_name": "string | null  — Kubernetes namespace name discovered in Phase 1, or null if unknown",
    "k8s_scope_mode":            "string  — 'namespace-scoped' | 'cluster-scoped' | 'unscoped' | 'non-kubernetes'"
  },
  "window": {
    "from":     "integer — epoch ms, window start",
    "to":       "integer — epoch ms, window end",
    "from_iso": "string  — ISO 8601 UTC",
    "to_iso":   "string  — ISO 8601 UTC"
  },
  "changes":         "ChangeRecord[]",
  "counts_by_type":  "{ release: N, change_event: N, kubernetes_info_event: N }",
  "sources_queried": "string[]  — which sources responded",
  "truncated":       "boolean   — true when dropped > 0",
  "dropped":         "integer   — records beyond max_changes",
  "notes":           "string[]  — warnings, clamps, source errors"
}
```

## ChangeRecord

| Field              | Type    | Description |
|--------------------|---------|-------------|
| `id`               | string  | Source record ID (release ID, event ID, or synthetic) |
| `ts`               | integer | Event timestamp in epoch milliseconds |
| `type`             | string  | `release` \| `change_event` \| `incident_event` \| `issue_event` \| `k8s_event` |
| `title`            | string  | Human-readable summary |
| `detail`           | string  | Detail string, truncated to ≤ 140 characters |
| `entity`           | string  | Entity label (application name, service name, pod, namespace, …) |
| `service_id`       | string \| null | Instana service ID if known; null for infrastructure-layer records |
| `severity`         | string  | `change` \| `warning` \| `critical` \| `info` |
| `source_layer`     | string  | `entity` — record from the resolved application or service; `infrastructure` — record from the underlying Kubernetes cluster or namespace |
| `match_confidence` | string  | `exact` — matched by entity ID; `heuristic` — matched by cluster/namespace label substring |

## Type meanings

| `type`                  | Source | Layer |
|-------------------------|--------|-------|
| `release`               | Instana Releases API (`manage_releases`) | entity |
| `change_event`          | Instana Events API, type=CHANGE | entity |
| `incident_event`        | Instana Events API, type=INCIDENT | entity |
| `issue_event`           | Instana Events API, type=ISSUE | entity |
| `k8s_event`             | Instana Kubernetes info events (`get_kubernetes_info_events`) | infrastructure |

> **Note:** `incident_event` and `issue_event` are reserved type values; the current normalizer emits `change_event` for all three input types (CHANGE, INCIDENT, ISSUE). Differentiation is deferred until the two normalizer paths are unified.

## Notes
- Records are sorted by `(ts, id)` for determinism.
- `source_layer: "entity"` records are matched directly by `application_id` or `service_id` from the Events API response.
- `source_layer: "infrastructure"` records (`k8s_event`) are matched by the Kubernetes cluster name or namespace name resolved in Phase 1. In `namespace-scoped` mode, exact namespace post-filtering on `entityLabel` (`<namespace>/<entity>`) is enforced before inclusion in the timeline. `match_confidence: "heuristic"` indicates infrastructure correlation and should be verified before attributing causality.
- `analyze_change_impact` (Phase 3) will extend this schema with `causal_score` and `regression_delta` fields.

## Removed fields (breaking changes from prior schema)

The following fields were present in earlier versions of the schema and have been removed:

| Field         | Removed reason |
|---------------|----------------|
| `scope.hops`  | No longer applicable — service fan-out with hop distances is not used; scope is a single entity with infrastructure topology context. |
| `scope.neighborhood` | Removed — previously listed call-graph neighbor services; replaced by `scope.kubernetes_cluster_name` and `scope.kubernetes_namespace_name`. |
| `NeighborService` | Object type removed — `neighborhood` array has been removed from scope. |
| `hop`         | Removed from ChangeRecord — hop distance is not meaningful in the single-entity model; replaced by `source_layer`. |

## Phase 3 Synthesis Template

Every Phase 3 response MUST fill in both slots below. No slot may be left blank or substituted
with speculative content.

---

**Change Records Found:**
- releases: N
- change_events: N
- kubernetes_info_events: N  *(events passing the exact-namespace post-filter; 0 if not applicable)*
- **Total:** N

**Timeline:**
Chronological list of ChangeRecords sorted by `(ts, id)` — timestamp ascending, then by ID for ties. If all active sources returned empty or zero records, this slot MUST read: `none — all 3 sources queried and returned empty results`. Do not substitute speculative next steps for this slot.

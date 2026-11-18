# Verify Telemetry Reference

> **Loaded by Steps 3, 7, and 8.** Load it once per session — if it is already in context, do not load it again.
> It MUST be loaded before any verification API call. Verification runs by default; skip it only when the user explicitly asked to skip verification.
> On PARTIAL / FAIL, also load `iterate.md` (Step 7a).

**Window**: every query uses `windowSize: 600000` (10 minutes) — the application must have produced traffic in the last 10 minutes.

**SERVICE_FILTER(`<svc>`)** — used by every trace and call query below (both directions, because spans may be recorded as source or destination):

```json
{ "type": "EXPRESSION", "logicalOperator": "OR", "elements": [
  { "type": "TAG_FILTER", "name": "service.name", "operator": "EQUALS", "entity": "DESTINATION", "value": "<svc>" },
  { "type": "TAG_FILTER", "name": "service.name", "operator": "EQUALS", "entity": "SOURCE", "value": "<svc>" } ] }
```

## Return shapes (use only these fields)

- `get_all_traces` → `itemCount`, `items[n].trace.{id,label,erroneous,startTime}`, `items[n].cursor.ingestionTime`.
- `get_trace_details` → call-tree rows: `id`, `parentId`, `name`, `duration`, `errorCount`, `destination.service.label`. **No span attributes** — never reference `data.tags`. `get_call_details` is not exposed through MCP; do not call it.
- `get_grouped_calls_metrics` → `totalHits`, `items[n].name` (the group value), `items[n].metrics`. A non-empty result proves the attribute exists.

---

## Phase 7-A: Confirm service visibility

Call `manage_applications` `analyze` / `get_all_traces` up to **3 attempts** (~10 s apart) until `itemCount > 0`:

```json
{ "payload": {
  "tagFilterExpression": "<SERVICE_FILTER(service_name)>",
  "includeInternal": true, "includeSynthetic": false,
  "timeFrame": { "windowSize": 600000 },
  "order": { "by": "duration", "direction": "DESC" },
  "pagination": { "retrievalSize": 10 } } }
```

- HTTP 401 → stop. Report `AUTH_ERROR`: "The API token configured in the Instana MCP server (e.g. `--headers` in `mcp.json`) was rejected. Verify it is active in Instana UI → Settings → Access Control → API Tokens."
- HTTP 403 → stop. Report `SCOPE_ERROR`: "The Instana MCP server's API token lacks required permissions. Enable **Service & Endpoint Map Read** and **Application Read**."
- `itemCount == 0` after all attempts → `achieved_level = "None"`, `verification_level = "FAIL"`. Load `iterate.md` and go to Step 7a.

Collect `items[n].trace.id` and `items[n].cursor.ingestionTime` (up to 5) for Phase 7-B.

---

## Phase 7-B: Verify GenAI attribute presence via call-group probes

### Service routing

GenAI attributes are split across two services depending on which span emits them:

| Attribute group | Filter by |
|---|---|
| LLM-level: `gen_ai.request.model`, `gen_ai.usage.*`, `gen_ai.provider.name` | The LLM library service (e.g. `langchain`, `openai`, `groq`) |
| Agent-level: `gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.conversation.id` | The user's agent service |

**Before probing**: call `get_trace_details` on one trace; read `destination.service.label` of the `ChatXxx.chat` span — that is `<llm_service_name>`.

### Probe

One `manage_applications` `metrics` / `get_grouped_calls_metrics` call per canonical key in the table below. Filter on the attribute (`NOT_EMPTY`) and group by service, so the result is at most one row whatever the attribute's cardinality. `totalHits > 0` → **present**; `0` → **absent**.

**`attribute_tag` is always the canonical key prefixed with `otel.`** — `attribute_tag = "otel." + <canonical key>` (e.g. `gen_ai.request.model` → `otel.gen_ai.request.model`).

```json
{ "metrics": [{ "metric": "calls", "aggregation": "SUM" }],
  "group": { "groupbyTag": "service.name", "groupbyTagEntity": "DESTINATION" },
  "tag_filter_expression": { "type": "EXPRESSION", "logicalOperator": "AND", "elements": [
    "<SERVICE_FILTER(service_name or llm_service_name)>",
    { "type": "TAG_FILTER", "name": "<attribute_tag>", "operator": "NOT_EMPTY", "entity": "NOT_APPLICABLE" } ] },
  "time_frame": { "windowSize": 600000 },
  "include_internal": true, "include_synthetic": false,
  "pagination": { "page": 1, "pageSize": 1 } }
```

> ⚠️ Always `"entity": "NOT_APPLICABLE"` on the `otel.*` tag filter. Never group by an `otel.*` tag: `pageSize` is not honoured, and tags like `gen_ai.conversation.id` return hundreds of rows.

| Canonical key | Filter by | Level |
|---|---|---|
| `gen_ai.operation.name` | agent service | Basic |
| `gen_ai.provider.name` | LLM service | LLM Calls |
| `gen_ai.request.model` | LLM service | LLM Calls |
| `gen_ai.usage.input_tokens` | LLM service | LLM Calls |
| `gen_ai.usage.output_tokens` | LLM service | LLM Calls |
| `gen_ai.agent.name` | agent service | Agent |
| `gen_ai.tool.name` | agent service | Agent |
| `gen_ai.conversation.id` | agent service | Conversation |

- **Legacy fallback**: if a canonical probe is absent, probe its legacy key from the alias table below with the same `otel.` prefix (e.g. `otel.llm.usage.prompt_tokens` for `gen_ai.usage.input_tokens`). A hit counts as present for that canonical key.
- **Span-name fallback (Agent level)**: if the agent and tool probes are both absent, span names from `get_trace_details` containing `execute_task`, `execute_tool`, `create_agent`, or `invoke_agent` satisfy `gen_ai.agent.name` and `gen_ai.tool.name` respectively.

Build `all_raw_tags` = canonical keys whose probe (or fallback) returned present.

### Content probes (report only — never change the level)

Same probe, one call per key, stopping at the first hit in each group. Filter by the LLM service; if nothing hits, repeat on the agent service (Traceloop records `traceloop.entity.*` there).
- **Prompt:** `gen_ai.input.messages`, `gen_ai.prompt.0.content`, `traceloop.entity.input`
- **Completion:** `gen_ai.output.messages`, `gen_ai.completion.0.content`, `traceloop.entity.output`

`prompt_text_detected = true` if any of these hit.

### Alias resolution

Resolve every raw key to its canonical form; use only canonical names afterwards.

| Raw / legacy keys | Canonical key |
|---|---|
| `gen_ai.usage.prompt_tokens`, `llm.usage.prompt_tokens` | `gen_ai.usage.input_tokens` |
| `gen_ai.usage.completion_tokens`, `llm.usage.completion_tokens` | `gen_ai.usage.output_tokens` |
| `gen_ai.system`, `llm.system`, `llm.vendor` | `gen_ai.provider.name` |
| `traceloop.association_properties.{session_id,conversation_id,chat_id}` | `gen_ai.conversation.id` |
| `traceloop.association_properties.thread_id` | `gen_ai.thread.id` |
| `traceloop.association_properties.user_id` | `gen_ai.user.id` |
| `gen_ai.prompt`, `gen_ai.prompt.<index>.content`, `gen_ai.input.messages`, `llm.prompts`, `traceloop.entity.input` | `gen_ai.content.prompt` |
| `gen_ai.completion`, `gen_ai.completion.<index>.content`, `gen_ai.output.messages`, `llm.completions`, `traceloop.entity.output` | `gen_ai.content.completion` |

### Convention detection

Classify `detected_convention` from the **raw** key set: legacy and canonical both present → `mixed`; only legacy / `llm.*` / `traceloop.*` → `traceloop-legacy`; only canonical `gen_ai.*` / `otel_resource.*` → `otel-genai`.

### Level evaluation (cumulative — each level requires all lower ones)

| Level | Required canonical tags |
|---|---|
| **Basic** | `gen_ai.operation.name` OR `traceloop.workflow.name` OR `llm.request.type` |
| **LLM Calls** | `gen_ai.provider.name` (or `gen_ai.framework`) AND (`gen_ai.request.model` OR `gen_ai.response.model`) AND `gen_ai.usage.input_tokens` AND `gen_ai.usage.output_tokens` |
| **Agent** | LLM Calls AND (`gen_ai.agent.name` OR `traceloop.entity.name`) AND (`gen_ai.tool.name` OR `traceloop.entity.path` OR any span name containing "tool" or "task") |
| **Conversation** | Agent AND (`gen_ai.conversation.id` OR `gen_ai.thread.id` OR `session_id` OR `conversation_id`) |

`achieved_level` = highest level fully met, else `"None"`.

### Outcome

`target_level` comes from `detect-and-credentials.md` §2f (default `Agent`). Rank: `None=0`, `Basic=1`, `LLM Calls=2`, `Agent=3`, `Conversation=4`.

- `rank(achieved) >= rank(target)` → `PASS`
- `0 < rank(achieved) < rank(target)` → `PARTIAL`
- `achieved == "None"` → `FAIL`

`missing_fields` = canonical tags required for `target_level` that are absent.

---

## Phase 7-C: GenAI infrastructure metrics (non-blocking)

`manage_infrastructure` `analyze` / `get_entity_groups`. `pagination` is required (the call fails validation without it):

```json
{ "payload": {
  "type": "oTelLLM", "groupBy": ["metric.tag.service_name"],
  "metrics": [
    { "metric": "metrics.gauges.llm.usage.total_tokens", "granularity": 600000, "aggregation": "SUM" },
    { "metric": "metrics.gauges.llm.response.duration", "granularity": 600000, "aggregation": "MEAN" } ],
  "timeFrame": { "windowSize": 600000 },
  "pagination": { "retrievalSize": 20 },
  "tagFilterExpression": { "type": "TAG_FILTER", "entity": "NOT_APPLICABLE",
    "name": "metric.tag.service_name", "operator": "EQUALS", "value": "<service_name>" } } }
```

`metrics_received = true` if at least one group has a non-null metric value; errors or empty → `false`. This never changes `verification_level`; it is reported in the diagnosis. `oTelLLM` metrics appear only when the app emits OTel **metrics**, so `false` with traces present is expected for trace-only setups.

---

## Phase 7-D: Evaluation block and routing

```
verification_level  : PASS | PARTIAL | FAIL
achieved_level      : None | Basic | LLM Calls | Agent | Conversation
target_level        : <from §2f>
detected_convention : otel-genai | traceloop-legacy | mixed | null
missing_fields      : [canonical tag names absent for target level]
metrics_received    : true | false
prompt_text_detected: true | false
diagnosis           : [human-readable list of findings]
timestamp           : <ISO-8601 UTC>
```

- `PASS` → Step 8 below.
- `PARTIAL` / `FAIL` → retry counter starts at 0, max `INSTANA_SKILL_MAX_RETRIES` (default 5). Counter < max → increment, load `iterate.md`, go to Step 7a. Counter = max → bounded failure (template in `iterate.md`).

---

## Step 8 — HAND OFF (PASS)

Print this prefix, then the full evaluation block:

```
✅ Instana GenAI Instrumentation — VERIFIED

Service         : {service_name}
Stack           : {detected_framework} / {detected_providers}
Achieved level  : {achieved_level}
Target level    : {target_level}
Convention      : {detected_convention}
Metrics         : {metrics_received}
Prompt content  : {captured if prompt_text_detected else not captured}
Instana page    : {Instana base URL}/#/genAiObservability/traces?service={service_name}   (omit this line if the base URL is not known — do not ask for it)
```

Then, only if `prompt_text_detected` is `true`, ask (ASK_RULE): "Prompt and completion text is being sent to Instana and may contain sensitive data. Keep capturing it? (keep / disable)".
- `keep` → done.
- `disable` → add `TRACELOOP_TRACE_CONTENT=false` and `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` to the project `.env` through the Step 5 diff and approval loop, and say it takes effect on the next run.

Never tell the developer to edit code or `.env` themselves: generate the diff and ask for approval.

---

## HTTP Error Guidance

| HTTP status / pattern | Variable | Action |
|---|---|---|
| 401 / "Unauthorized" | Instana MCP server API token | Token rejected. Verify it is active in Instana UI → Settings → Access Control → API Tokens, and update the MCP server config. |
| 403 / "Forbidden" | Instana MCP server API token | Enable **Service & Endpoint Map Read** and **Application Read** on the token. |
| Network error / timeout | Instana MCP server URL | Unreachable. Verify the URL, TLS, and connectivity in the MCP server config. |
| 415 Unsupported Media Type | `OTEL_EXPORTER_OTLP_ENDPOINT` | Transport mismatch. `otlp-http-*` → HTTP exporter; `otlp-grpc-*` → gRPC exporter. |

## Optional Control Variables

| Variable | Default | Purpose |
|---|---|---|
| `INSTANA_SKILL_TARGET_LEVEL` | `Agent` | Minimum level for PASS: `Basic`, `LLM Calls`, `Agent`, `Conversation` |
| `INSTANA_SKILL_MAX_RETRIES` | `5` | Maximum verify+iterate cycles (1–10) |
| `INSTANA_SERVICE_NAMESPACE` | — | Disambiguates service name when multiple services share a name |

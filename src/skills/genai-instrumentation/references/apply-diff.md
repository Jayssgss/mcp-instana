# Apply Diff Reference

> **Loaded by Step 5 (APPLY).** Load it once per session — if it is already in context, do not load it again. Do NOT generate or show any diff until it is loaded.

---

## §5a. Generate the diff

Based on `already_instrumented` (from Step 1):

- **`false`** (no OTel present) → generate the full initialisation block below.
- **`true`** (OTel already present) → extend the existing TracerProvider — do NOT add a second one (Principle V). Use the "extend" template below.
- If `using_traceloop` is `true`, `Traceloop.init()` already instruments every supported library: add NO native instrumentors. The only change is `OTEL_RESOURCE_ATTRIBUTES=INSTANA_PLUGIN=genai` (plus the Traceloop env vars) in `.env`.

Use `transport` from Step 2c: substitute `<http|grpc>` in the two exporter import lines with the resolved transport (package names and import modules are in `detect-and-credentials.md` §2c).

```python
# instrumentation/telemetry.py
import os
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.<http|grpc>.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.<http|grpc>.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# One import per entry in recipe.instrumentors (§1b-3) — framework and provider
from <module> import <InstrumentorClass>

def configure_telemetry() -> None:
    service_name = os.environ.get("OTEL_SERVICE_NAME")
    if not service_name:
        raise RuntimeError("OTEL_SERVICE_NAME must be set (see .env)")
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        raise RuntimeError("A TracerProvider already exists - use the extend template, not a new provider")
    resource = Resource.create({
        "service.name": service_name,
        "INSTANA_PLUGIN": "genai",
    })
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
        # reads OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_HEADERS from env
    )
    trace.set_tracer_provider(tracer_provider)
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    <InstrumentorClass>().instrument()  # repeat for each entry in recipe.instrumentors
```

Add a call to `configure_telemetry()` in the application entry point (before any LLM imports or calls).

Also include the non-secret `envToSet` entries from Step 2b (endpoint, `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_EXPORTER_OTLP_INSECURE`, and `OTEL_EXPORTER_OTLP_PROTOCOL` for gRPC) as additions to the project `.env`, skipping keys that already have a real value. For `agentless`, add the line `OTEL_EXPORTER_OTLP_HEADERS=x-instana-key=<set-by-developer>` as a name-only reminder — never a real key. The agent key itself is never written by this skill.

> ⚠️ **Transport mismatch produces `415 Unsupported Media Type`** — `otlp-http-*` hostnames need the HTTP exporter, `otlp-grpc-*` the gRPC exporter.

### Extend template (`already_instrumented` is `true`, plain OTel, no Traceloop)

Add this next to the project's existing `TracerProvider` setup, after it runs. Never call `TracerProvider(...)` or `set_tracer_provider(...)` again: a second provider is silently ignored (`Overriding of current TracerProvider is not allowed`) and a live provider's Resource cannot be changed.

```python
from opentelemetry import trace
from <module> import <InstrumentorClass>   # one per entry in recipe.instrumentors (§1b-3)

<InstrumentorClass>().instrument(tracer_provider=trace.get_tracer_provider())
```

`INSTANA_PLUGIN=genai` must reach the existing provider's Resource. Inspect how the project builds it:
- `Resource.create({...})` or `TracerProvider()` with no `resource` argument → it merges `OTEL_RESOURCE_ATTRIBUTES`, so only add `OTEL_RESOURCE_ATTRIBUTES=INSTANA_PLUGIN=genai` to `.env`.
- `Resource({...})` (direct constructor) or `Resource.get_empty()` → it ignores that variable. Include `"INSTANA_PLUGIN": "genai"` in the project's own resource dict in the diff instead.

### Conversation id (only when `target_level` is `Conversation`)

Add it to the diff yourself; never ask the developer to add it by hand. Find the call that runs the agent or chat in the project source and pass a per-conversation id: the app's own session, user or thread id, or a generated `uuid4()` if it has none.
- **LangGraph:** `config={"configurable": {"thread_id": <id>}}` on `.invoke()` / `.stream()`.
- **LangChain:** `config={"configurable": {"session_id": <id>}}`.
- **Traceloop:** `Traceloop.set_association_properties({"session_id": <id>})`.
- **Plain OTel:** set the `gen_ai.conversation.id` attribute on the active span.

### Traceloop recipe (when `using_traceloop` is `true`)

Install `pip install traceloop-sdk==0.62.3`. Set `TRACELOOP_BASE_URL` and `TRACELOOP_HEADERS` **instead of** `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS`, plus `OTEL_RESOURCE_ATTRIBUTES=INSTANA_PLUGIN=genai`. Use only when Traceloop is already in use or explicitly requested.

⚠️ **Critical ordering rule**: `Traceloop.init()` MUST be called before importing LangGraph, LangChain, OpenAI, or any LLM library. Traceloop monkey-patches at import time.

```python
# Step 1: load env vars FIRST (Traceloop reads them at init time)
from dotenv import load_dotenv
load_dotenv()

# Step 2: init Traceloop BEFORE all other framework imports
import os
from traceloop.sdk import Traceloop
service_name = os.environ.get("OTEL_SERVICE_NAME")
if not service_name:
    raise RuntimeError("OTEL_SERVICE_NAME must be set (see .env)")
Traceloop.init(
    app_name=service_name,                      # becomes service.name in Instana
    endpoint_is_traceloop=False,
    # disable_batch=True  ← uncomment for short-lived scripts
)

# Step 3: framework imports are safe AFTER Traceloop.init()
from langgraph... import ...   # or langchain, openai, etc.
```

---

## §5b. Credential scan

Before presenting the diff, stream the unified diff directly via standard input (no temporary files or folders are used) and run the scan below on it. It flags base64-like strings and Hex strings of 32+ characters and `key=value` assignments of secrets. It examines **added lines only** (`+`, not `+++`), so context lines never trigger it, and it prints line numbers only — never the matched text.

```bash
python3 -c '
import re, sys
TOK = re.compile(r"(?<![A-Za-z0-9+/_.-])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/_.-])")
HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
KV = re.compile(r"(x-instana-key|api[_-]?key|secret|token)\s*[=:]\s*[\x27\"]?[A-Za-z0-9_+/=-]{8,}(?![A-Za-z0-9_+/=.(\[-])", re.I)
def b64(t): return any(re.search(r"\d", m.group()) and re.search(r"[A-Za-z]", m.group()) for m in TOK.finditer(t))
hits = [n for n, l in enumerate(sys.stdin, 1)
        if l.startswith("+") and not l.startswith("+++")
        and (b64(l[1:]) or HEX.search(l[1:]) or KV.search(l[1:]))]
print("CLEAN" if not hits else "FLAGGED lines: " + ", ".join(map(str, hits)))
sys.exit(1 if hits else 0)
' <<'EOF'
<insert unified diff here>
EOF
```

Placeholders such as `<set-by-developer>`, `os.environ[...]` reads are not credentials and must not abort the diff.

If the command prints `FLAGGED`: **abort**. Do not show the diff. Report only the line numbers and:
> "Diff scan failed — a credential pattern was detected. The diff has been suppressed (Principle II)."

---

## §5c. Present and get approval

Show the complete unified diff to the developer and request confirmation:

> "Please review the diff above. Do you want to apply it? (yes / no / modify)"

- **yes** → apply the changes using your file editing tool.
- **no** → ask what they would like to do instead. Do not apply anything.
- **modify** → ask what changes they want, regenerate the diff, re-scan, and re-present.


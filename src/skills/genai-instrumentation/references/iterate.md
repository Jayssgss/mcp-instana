# Iterate Reference (Step 7a)

> **Loaded only when verification returns PARTIAL or FAIL.** Load it once per session; skip if already in context.
> Inputs come from the Phase 7-D evaluation block in `verify-telemetry.md`.

## Step 7a — ITERATE: Diagnose and produce a targeted fix

0. **No traces at all** (`achieved_level = "None"` from Phase 7-A): do NOT generate a code diff. Zero traces means telemetry is not reaching Instana — almost always configuration or traffic. Walk the developer through this checklist and re-run Phase 7-A after each fix:
   - The application was run and made GenAI calls after the change, within the last 10 minutes (the verification window).
   - `OTEL_EXPORTER_OTLP_ENDPOINT` is set, has no `/v1/traces` suffix, and matches the mode resolved in Step 2.
   - `OTEL_EXPORTER_OTLP_HEADERS` carries `x-instana-key=` (agentless only) — name check only, never display the value.
   - `OTEL_RESOURCE_ATTRIBUTES` includes `INSTANA_PLUGIN=genai`.
   - Exporter transport matches the endpoint (`415 Unsupported Media Type` → HTTP Error Guidance in `verify-telemetry.md`).
   - Short-lived script: Traceloop → `Traceloop.init(..., disable_batch=True)`. Pure OTel → call `trace.get_tracer_provider().force_flush()` in a `finally:` before exit.
   - `configure_telemetry()` / `Traceloop.init()` runs before any LLM import.

   Only proceed to step 1 when at least one trace is visible.

1. Read `missing_fields` — the exact canonical tag names absent for the target level.

2. **Remediation Catalog**: Map each missing field to its remediation hint using the target level and detected stack (`detected_framework`, `detected_providers`).

   ### Level: Basic
   - **`INSTANA_PLUGIN=genai` / `gen_ai.operation.name`**:
     - *General Fix*: Add `INSTANA_PLUGIN=genai` to `OTEL_RESOURCE_ATTRIBUTES` environment variable or OTel Resource definition so Instana routes telemetry to the GenAI pipeline. Ensure instrumentor is initialized before any LLM imports.
     - *Stack-Specific*:
       - **Traceloop**: Verify `TRACELOOP_BASE_URL` is configured before calling `Traceloop.init()`.

   ### Level: LLM Calls
   - **`gen_ai.system` / `gen_ai.provider.name`**:
     - *General Fix*: Ensure LLM provider identity is emitted (e.g. `'openai'`, `'anthropic'`, `'watsonx'`). Use framework-specific instrumentor or Traceloop SDK. For manual spans, set `gen_ai.system` as a span attribute.
     - *Stack-Specific*:
       - **OpenAI**: Initialize `opentelemetry-instrumentation-openai` with `OpenAIInstrumentor().instrument()` or `Traceloop.init()`.
       - **Anthropic**: Initialize Anthropic instrumentor or `Traceloop.init()` to capture provider metadata.
       - **watsonx**: Use `opentelemetry-instrumentation-watsonx` with `WatsonxInstrumentor().instrument()` to set `gen_ai.system='watsonx'`.
       - **LangChain**: Ensure `LangchainInstrumentor().instrument()` is called before invoking chains/models.
       - **LangGraph**: Ensure LangGraph native OTel tracing or `Traceloop.init()` is initialized before running the graph.

   - **`gen_ai.request.model`**:
     - *General Fix*: Specify the request model name in LLM initialization or configure the instrumentor to capture request parameters.
     - *Stack-Specific*:
       - **OpenAI**: Pass model parameter (e.g., `model="gpt-4o"`) in OpenAI API calls and verify `OpenAIInstrumentor` is active.
       - **watsonx**: Configure `model_id` parameter in `WatsonxLLM` or `ModelInference` initialization.
       - **LangChain**: Set `model`/`model_name` parameter on `ChatOpenAI`/`ChatAnthropic`/`WatsonxLLM` class instances.
       - **LangGraph**: Ensure model configurations in graph nodes explicitly define the model name.
       - **Traceloop**: Upgrade `traceloop-sdk` to ≥ 0.32.

   - **`gen_ai.response.model`**:
     - *General Fix*: Ensure response model attribute is captured from LLM provider completion payload.
     - *Stack-Specific*:
       - **OpenAI**: Ensure OpenAI completion responses are not mocked or intercepted before OTel instrumentation hooks execute.
       - **watsonx**: Verify `ibm-watsonx-ai` returns the model ID in the response metadata.

   - **`gen_ai.usage.input_tokens`**:
     - *General Fix*: Enable token usage tracking in your LLM client.
     - *Accepted Aliases*: `gen_ai.usage.prompt_tokens`, `llm.usage.prompt_tokens`.
     - *Stack-Specific*:
       - **OpenAI**: OpenAI API returns usage by default for non-streaming calls. For streaming, enable `stream_options={"include_usage": True}`.
       - **Anthropic**: Anthropic returns usage metadata on message responses. Ensure streaming calls capture the `message_start` event.
       - **watsonx**: Ensure `WatsonxLLM` / `ModelInference` returns generated token metrics.
       - **LangChain**: Token counts come from the provider response (`usage_metadata`); `LangchainInstrumentor` has no token option. For streaming `ChatOpenAI` with a custom `base_url`, proxy or client, set `ChatOpenAI(..., stream_usage=True)`.
       - **LangGraph**: Ensure LLM nodes propagate token usage from messages to the graph state.

   - **`gen_ai.usage.output_tokens`**:
     - *General Fix*: Enable output/completion token tracking in your LLM client.
     - *Accepted Aliases*: `gen_ai.usage.completion_tokens`, `llm.usage.completion_tokens`.
     - *Stack-Specific*:
       - **OpenAI**: For streaming completions, set `stream_options={"include_usage": True}` so completion tokens are emitted in the final chunk.
       - **Anthropic**: Ensure `message_delta` usage chunks are aggregated or non-streaming responses are used.
       - **watsonx**: Verify Watsonx response payload includes generated token counts.

   ### Level: Agent
   - **`gen_ai.agent.name`**:
     - *General Fix*: Add agent identity attribute (e.g., `gen_ai.agent.name`). Set on agent-entry span.
     - *Accepted Aliases*: `traceloop.entity.name` on agent spans.
     - *Stack-Specific*:
       - **LangChain**: Provide `name="<agent-name>"` when constructing `AgentExecutor` or custom agent workflows.
       - **LangGraph**: Assign recognizable names to graph/nodes or tag with Traceloop `@agent(name="...")` decorator. Also set `gen_ai.framework=LangGraph` on root span.
       - **CrewAI**: Ensure CrewAI Agent definitions specify the `role` or `name`.
       - **OpenAI Agents**: Ensure OpenAI Assistant or Agent instances specify a `name`.

   - **`gen_ai.tool.name`**:
     - *General Fix*: Emit tool execution spans with `gen_ai.operation.name=execute_tool` and `gen_ai.tool.name=<tool_name>`.
     - *Stack-Specific*:
       - **LangChain**: Ensure tools define `name` attribute or use `langchain_core.tools.tool` (`@tool`) with a descriptive name.
       - **LangGraph**: Tool-calling nodes should invoke standard tool bindings or Traceloop `@task(name="...")` / `@tool(name="...")` decorators. Tools decorated with LangChain `@tool` emit this automatically when `LangchainInstrumentor` is active.
       - **CrewAI**: Ensure `Tool` objects provided to CrewAI agents have descriptive `name` attributes.

   ### Level: Conversation
   - **`gen_ai.conversation.id`**:
     - *General Fix*: Propagate a session or conversation identifier using `gen_ai.conversation.id` or `session_id` in span attributes or context on every turn.
     - *Accepted Aliases*: `session_id`.
     - *Stack-Specific*:
       - **LangChain**: Pass `session_id` / `conversation_id` in `RunnableConfig` configurable dict: `config={"configurable": {"session_id": "..."}}`.
       - **LangGraph**: Set `thread_id` in LangGraph checkpointer config: `config={"configurable": {"thread_id": "..."}}`.
       - **Traceloop**: Call `Traceloop.set_association_properties({"session_id": "<id>"})`.
       - **Pure OTel**: Set `gen_ai.conversation.id` attribute on active span manually.

3. **Remediation Quick Reference Table**:

   | Missing field | Level | General fix | Stack-specific notes |
   |---|---|---|---|
   | `INSTANA_PLUGIN=genai` / `gen_ai.operation.name` | Basic | Set `OTEL_RESOURCE_ATTRIBUTES=INSTANA_PLUGIN=genai`. | Traceloop: check `TRACELOOP_BASE_URL` before `Traceloop.init()`. |
   | `gen_ai.system` / `gen_ai.provider.name` | LLM Calls | Emit provider identity (`openai`, `anthropic`, `watsonx`). | OpenAI: `OpenAIInstrumentor()`; Watsonx: `WatsonxInstrumentor()`; LangChain: `LangchainInstrumentor()`. |
   | `gen_ai.request.model` | LLM Calls | Specify request model in LLM config/calls. | OpenAI: pass `model="..."`; Watsonx: pass `model_id="..."`; LangChain: set `model_name` on chat model. |
   | `gen_ai.response.model` | LLM Calls | Capture response model from completion payload. | OpenAI: ensure responses not mocked; Watsonx: verify `ibm-watsonx-ai` response metadata. |
   | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | LLM Calls | Enable token usage capture. | OpenAI streaming: `stream_options={"include_usage": True}`; LangChain streaming OpenAI-compatible: `ChatOpenAI(..., stream_usage=True)`. |
   | `gen_ai.agent.name` | Agent | Set `gen_ai.agent.name` on agent span. | LangGraph: Traceloop `@agent(name="...")` or node name; CrewAI: agent `role`/`name`; LangChain: `AgentExecutor(name="...")`. |
   | `gen_ai.tool.name` | Agent | Emit `gen_ai.tool.name` on tool span. | LangChain: `langchain_core.tools.tool` (`@tool`); Traceloop: `@tool(name="...")` / `@task(name="...")`; CrewAI: descriptive `Tool.name`. |
   | `gen_ai.conversation.id` | Conversation | Propagate session/thread identifier. | LangGraph: `config={"configurable": {"thread_id": "..."}}`; LangChain: `config={"configurable": {"session_id": "..."}}`; Traceloop: `set_association_properties`. |

4. If `detected_convention` is `traceloop-legacy` or `mixed`, inform the developer (informational only — does not fail verification):
   > "Your spans use legacy Traceloop attribute names. These are accepted as-is. Migrating to canonical OpenTelemetry GenAI semantic conventions (`gen_ai.*`) is recommended for future compatibility."

5. If `prompt_text_detected` is `true`, inform the developer:
   > "Prompt/completion text attributes were detected in your spans. Ensure this is intentional — prompt content may contain sensitive data."

6. Present the top 3 most relevant remediation entries for the current `missing_fields`.

7. Generate a **targeted fix diff** — only the specific missing attributes, not a full re-instrumentation. Apply the credential scan (`apply-diff.md` §5b) and present for developer approval.

8. Developer approves → apply → return to Step 6 (RUN again) → then Phase 7-A (VERIFY again).

---

## Bounded failure (retry counter = max)

Print this, then the full evaluation block:

```
⚠️ Instana GenAI Instrumentation — BOUNDED FAILURE

Service         : {service_name}
Last level      : {achieved_level}
Target level    : {target_level}
Attempts        : {retry_count}
Missing fields  : {missing_fields joined by ", "}

Top remediation steps:
{top 3 entries from the remediation catalog above for the current missing_fields}
```

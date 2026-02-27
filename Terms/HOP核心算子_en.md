# HOP Core Operators

This document is a guide for Claude Code (or any AI programming assistant) on HOP core operators. It aims to help AI understand how to invoke HOP operators and the framework's conventions regarding **error handling**, **concurrency safety**, and **state management**.

> Engine source code: `hoplogic/hop_engine/`
> API detailed documentation: `hoplogic/docs/hop.md` (entry point)

---

## 1. Constants and Enums

> Source code: `hop_engine/config/constants.py`

### `JsonValue`

Type alias defining valid JSON value types in the HOP system: `None | bool | int | float | str | list[Any] | dict[str, Any] | Literal["True", "False", "Uncertain"]`.

### `class HopStatus(Enum)`

Status enumeration for HOP operator execution results, serving as the core state machine for the verification system.

| Enum Value | Meaning | Can feedback continue |
|------------|---------|----------------------|
| `OK` | Verification successful, conclusion correct | — |
| `LACK_OF_INFO` | LLM reasoning layer lacks information, may improve with additional context | Yes |
| `UNCERTAIN` | Cannot determine conclusion (not due to missing information) | Yes |
| `FAIL` | Failure (transmission failure/verification failure/tool execution failure/capability limitation) | No |

> **FAIL vs LACK_OF_INFO boundary**: Pre-pipeline failures (RAG retrieval no results, data source unreachable, etc.) should return `FAIL` - `add_feedback` only affects LLM conversation history and cannot fix pipeline layer issues. `LACK_OF_INFO` is only used for LLM operator self-reported reasoning layer information deficiency.

---

## 2. Three-Layer Architecture

```
User code (Hop.py / examples)
    |
HopSession -- Execution boundary: conversation history, HopState, ExecutionStats, persistence (StateStore)
    |
HopProc     -- Operator abstraction: semantics of hop_get/judge/tool_use, retry, verification (stateless, shareable)
    |
LLM         -- Transport layer: connection reuse, engine adaptation, structured output (stateless, shareable)
```

- **HopSession**: Creates a session for each business execution, holding conversation history, `HopState` (execution state), and `ExecutionStats` (statistics).
- **HopProc**: Core processor defining three operators. Stateless and can be shared by multiple sessions (within the same event loop).
- **LLM**: Transport layer encapsulating `openai.AsyncClient`. Connection reuse, bound to the event loop at creation time.

---

## 3. Core Operators

> Source code: `hop_engine/core/hop_processor.py`

All three operators are **async coroutine** methods that uniformly return `Tuple[HopStatus, JsonValue]`. All operators require a `session` parameter (`HopSession` instance), recommended to be invoked through `HopSession` proxy.

### `hop_get` — Information Retrieval

```python
await session.hop_get(
    task: str,                           # Task description (required)
    context: str = "",                   # Context information
    return_format: JsonValue = None,     # Return value format (dict/tuple/Pydantic/basic type)
    verifier = reverse_verify,           # Verifier, None skips verification
    explanation_description: str = "",   # Custom explanation description
    include_history: bool = True,        # Whether to include previous operators' conversation history
) -> Tuple[HopStatus, JsonValue]
```

- **Purpose**: Extract knowledge from context, retrieve structured information
- **Default verification**: Reverse verification (`reverse_verify`)
- **Decorator**: `@auto_record_status` — automatic statistics recording

### `hop_judge` — Truth Judgment

```python
await session.hop_judge(
    task: str,                           # Judgment condition description (required)
    context: str = "",                   # Context information
    return_format: JsonValue = None,     # Default Literal["True","False","Uncertain"]
    verifier = reverse_verify,           # Verifier
    explanation_description: str = "",   # Custom explanation description
    include_history: bool = True,        # Whether to include previous operators' conversation history
) -> Tuple[HopStatus, JsonValue]
```

- **Purpose**: Perform truth judgment on knowledge
- **Default verification**: Reverse verification (`reverse_verify`)
- **Default return_format**: `Literal["True", "False", "Uncertain"]`

### `hop_tool_use` — Tool Invocation

```python
await session.hop_tool_use(
    task: str,                           # Tool invocation requirement (required)
    context: str = "",                   # Context information
    tool_domain: str = "all",            # Tool domain (limits available tool set)
    verifier = tool_use_verifier,        # Tool verifier
    include_history: bool = True,        # Whether to include previous operators' conversation history
) -> Tuple[HopStatus, JsonValue]
```

- **Purpose**: Let LLM select and execute registered tools
- **Default verification**: Tool verification (`tool_use_verifier`)
- **Process**: LLM selects tool → verifies tool selection legality → actually executes tool → returns tool result
- **Tool domains**: `"all"` (all), `"security"` (security tools), `"rag"` (RAG retrieval), `"mcp"` (MCP external tools, dynamically registered via `init_mcp_tools()`)

---

## 4. HopSession — Execution Session

> Source code: `hop_engine/utils/hop_session.py`

### Creation and Usage

```python
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.state_store import JsonlStateStore

hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,        # Maximum retry attempts for verification failure, must be >= 1
)

store = JsonlStateStore("output.jsonl")

async with hop_proc.session(state_store=store) as s:
    status, result = await s.hop_get(task="Extract summary", context=text)
    if status != HopStatus.OK:
        # Handle failure
        ...
    status, verdict = await s.hop_judge(task="Judge correctness", context=result)
```

### Resources Managed by Session

| Resource | Description |
|----------|-------------|
| `run_history` | Execution-side LLM conversation history (retains task+result summary across operators) |
| `state` (`HopState`) | Execution state: retry count, execution path, step records |
| `stats` (`ExecutionStats`) | Operator/function-level statistics |
| `state_store` | Optional persistence backend |
| `run_id` | Execution batch identifier (auto-generated UUID by default) |

### Cross-Operator Conversation History and Folding Mechanism

By default, after each operator execution within the same session, the complete execution process (prompt, retry feedback, assistant response) is folded into a concise **task+result summary** retained in `run_history`. Subsequent operators' LLM can see previous operators' summaries.

```
operator A execution (with complete prompt + retries)
↓ After execution, folded into task+result summary
operator B execution can see A's task+result
↓ After execution, folded
operator C execution can see A, B's task+result
```

**`include_history` parameter**:

| Value | Behavior |
|-------|----------|
| `True` (default) | LLM sees previous operators' task+result summary + this complete prompt |
| `False` | LLM only sees this operator's own messages, but task+result still counts toward history for subsequent operators |

### Verification Failure Retry Feedback

When verification fails, feedback information is appended to conversation history as a user message in format: `"\nVerification feedback: {verifier_reason} Please try again\n"`. LLM can reference verification feedback and previous assistant responses to correct output during retry. After retry ends, all intermediate rounds (including feedback) are folded, retaining only final task+result summary.

### Context Manager Semantics

- **`__aenter__`**: Resets state and stats, records start time
- **`__aexit__`**: Merges session statistics into `GLOBAL_STATS`; persists function-level summary when `state_store` exists

---

## 5. Exception and Error Handling Conventions

> Detailed documentation: `docs/hop_error_handling.md`

### Core Principle: Pure Return Value Mode

**All operators always return `(HopStatus, result)`, regardless of success or failure.** User code handles failures by checking `status`, no `try/except` needed.

```python
# Correct: check status
status, result = await s.hop_get(task="...", context="...")
if status != HopStatus.OK:
    logger.warning(f"Failed: {status}, {result}")
    return fallback

# Wrong: don't try/except operator calls
try:
    status, result = await s.hop_get(...)  # Won't throw exception
except ValueError:  # Won't trigger
    ...
```

The only exception thrown is `ValueError` when `session=None`, which is a programming error rather than business failure.

### Exception Layering

```
User code                          ← Check status, no try/except needed
    |
@auto_record_status decorator       ← All statuses returned directly; exceptions converted to (FAIL, ...)
    |
HopProc operators                  ← Return (HopStatus, result)
    |
_execute_task                    ← Retry loop, consumes HopStatus
    |
_execute_core                    ← Low-level exceptions wrapped as RuntimeError
    |
LLM.query_llm                   ← Internal retry+backoff, returns (bool, response), no exceptions
    |
openai.AsyncClient               ← Original exceptions (network, rate limit, timeout, etc.)
```

### Four Types of FAIL

FAIL status has four sources, all returning `(HopStatus.FAIL, result)`:

| Failure Type | `error_type` | result characteristics | Meaning |
|--------------|-------------|------------------------|---------|
| Transmission failure | Non-empty (e.g., `"RuntimeError"`) | `[RuntimeError] ...` | LLM unavailable |
| Verification failure | `None` | Reason returned by verifier | LLM available but result unqualified |
| Tool execution failure | `None` | `"Tool call failed: ..."` / `"Tool execution failed: ..."` | `hop_tool_use` tool call error |
| Capability limitation | N/A (user code directly returns) | Business custom (e.g., `"Knowledge base retrieval failed"`) | Pre-pipeline failure, didn't enter LLM operator |

```python
status, result = await s.hop_get(task="...", context="...")
if status == HopStatus.FAIL:
    last = s.state.step_records[-1]
    if last.error_type:
        logger.error(f"Transmission failure: {last.error_type}")
    else:
        logger.warning(f"Verification failure: {result}")
elif status == HopStatus.UNCERTAIN:
    # Degrade to use uncertain result
    process_with_warning(result)
elif status == HopStatus.LACK_OF_INFO:
    logger.info(f"Insufficient information: {result}")
```

### Two-Layer Retry Mechanism

```
Operator retry (hop_retry, default 3)    ← Verification failure triggers, appends feedback to conversation history
  └── Each round internally: LLM retry (max_retry_count)  ← Transmission exception triggers, exponential backoff
```

- **Verification failure** (`FAIL`/`UNCERTAIN` etc. `HopStatus`) → Operator-level retry, LLM references verification feedback to correct
- **Feedback format**: `"\nVerification feedback: {verifier_reason} Please try again\n"`
- **Visible during retry**: Previous operators' summaries (if `include_history=True`) + this round's complete conversation (prompt, previous assistant response, verification feedback)
- **Folding**: After retry ends, all intermediate rounds are folded into task+result summary, subsequent operators only see final result
- **Transmission failure** (LLM all retries exhausted → `RuntimeError`) → Operator-level **no retry**, directly propagates to decorator, returns `(FAIL, ...)`
- **Final round**: `UNCERTAIN`/`LACK_OF_INFO` retains original status, doesn't degrade to `FAIL`

### Persistence and Statistics Error Handling

`state_store.save_step()` and `stats.record_operator()` are both protected by `try/except`. Persistence and statistics are optional observability features, internal errors don't affect `(status, result)` return.

---

## 6. Concurrency Safety Conventions

> Detailed documentation: `docs/hop_concurrency.md`

### Recommended Model: Single-thread asyncio Concurrency

All `HopSession` run within the same event loop, achieving concurrency through `asyncio.gather`. This model doesn't require thread safety considerations.

```python
async def process_one(hop_proc, item):
    async with hop_proc.session() as s:
        status, result = await s.hop_get(task=item["task"], context=item["ctx"])
        return result

results = await asyncio.gather(*[process_one(hop_proc, item) for item in items])
```

### Ownership Boundaries

| Component | Ownership | Cross-thread Shareable | Thread Safety Mechanism |
|-----------|-----------|------------------------|------------------------|
| `HopProc` | per-thread | No | N/A |
| `LLM` | per-HopProc | No | N/A (bound to event loop) |
| `HopSession` | per-session | No | N/A |
| `HopState` | per-session | No | N/A |
| `ExecutionStats` (session level) | per-session | No | `asyncio.Lock` |
| `GLOBAL_STATS` | Module singleton | **Yes** | `threading.Lock` (only `merge_from`) |
| `JsonlStateStore` | Shareable | **Yes** | `threading.Lock` (`_append`) |

### Prohibited Usage Patterns

- **Cross-thread sharing HopProc**: `LLM` internal `openai.AsyncClient` bound to creation event loop, cross-thread usage causes "attached to a different loop" error
- **Cross-thread sharing HopSession**: `HopState`'s `list.append()` has no lock protection, data race in multi-threading
- **Cross-thread direct write to GLOBAL_STATS**: `record_operator`/`record_function` use `asyncio.Lock`, only safe within same event loop

### Multi-thread Correct Usage

Each thread creates independent `HopProc`, can share `JsonlStateStore`. When session exits, automatically merges statistics via `GLOBAL_STATS.merge_from()` (protected by `threading.Lock`).

```python
def worker(items, run_cfg, verify_cfg):
    proc = HopProc(run_model_config=run_cfg, verify_model_config=verify_cfg)
    loop = asyncio.new_event_loop()
    async def run():
        for item in items:
            async with proc.session(state_store=shared_store) as s:
                await s.hop_get(task=item["task"], context=item["ctx"])
        await proc.aclose()
    loop.run_until_complete(run())
    loop.close()
```

### Verifier Internal Concurrency

`forward_cross_verify` and `tool_use_verifier` concurrently call LLM 3 times via `asyncio.gather`. Internally uses `_query_llm_once` helper function, defensively shallow copies params to isolate concurrent calls.

---

## 7. Verifiers

> Source code: `hop_engine/validators/result_validators.py`
> Detailed documentation: `docs/hop_validators.md`

All verification functions are async coroutines with unified signature:

```python
async def verifier(
    task: str,
    context: str,
    model_result: JsonValue,
    ctx: VerifyContext,
) -> HopVerifyResult
```

### Built-in Verifiers

| Verifier | Purpose | Default Used For |
|----------|---------|------------------|
| `reverse_verify` | Reverse verification (independent LLM reverse validates conclusion and context consistency) | `hop_get`, `hop_judge` |
| `forward_cross_verify` | Forward cross verification (concurrently calls LLM 3 times, compares result consistency) | — |
| `tool_use_verifier` | Tool verification (legality + parameters + cross verification) | `hop_tool_use` |
| `format_verifier` | Format verification (detects serialization residue, purely local, no LLM call) | All LLM steps (always as pre-check) |

### Custom Verifiers

```python
async def my_verifier(task, context, model_result, ctx) -> HopVerifyResult:
    if is_valid(model_result):
        return HopVerifyResult(HopStatus.OK, "Verification passed")
    return HopVerifyResult(HopStatus.FAIL, "Verification failure reason")

# Usage
status, result = await s.hop_get(task=..., verifier=my_verifier)

# Skip semantic verification (format_verifier still auto-applies)
status, result = await s.hop_get(task=..., verifier=None)
```

Verifiers internally handle errors, don't throw exceptions upward, instead return `HopVerifyResult(FAIL, reason)`.

> **Format verification always runs first**: `format_verifier` automatically runs as pre-check for all verifications regardless of semantic verifier specification. Execution order: `format_verifier` -> semantic verifier (if any). Format check failure directly triggers retry, doesn't call semantic verifier. `verifier=None` means only run format verification. `format_verifier` recursively scans entire output tree, detects stringified dict/list residue. No LLM call, zero additional overhead.

---

## 8. Decorators

> Source code: `hop_engine/utils/status_recorder.py`
> Detailed documentation: `docs/hop_monitoring.md`

### `@auto_record_status`

Wraps the three operators, automatically performs:

1. Resets retry count, sets current step number and operator name
2. Times and `await`s decorated function
3. Records execution path (`state.add_execution_step`)
4. Creates `HopStepRecord` appended to `state.step_records`
5. If `state_store` exists, persists to external storage
6. Calls `stats.record_operator` to record statistics (try/except protected)
7. Returns `(status, result)` — all statuses returned directly

Exception path: When decorated function throws exception, executes same complete recording flow as normal path, then returns `(HopStatus.FAIL, "[ErrorType] message")`.

### `HopStepRecord`

Structured record of a single operator step:

| Field | Type | Description |
|-------|------|-------------|
| `step` | `int` | Step sequence number |
| `op` | `str` | Operator name |
| `task` | `str` | Task description |
| `result_truncated` | `str` | Result truncated to 100 characters |
| `result_full` | `str` | Complete result |
| `duration` | `float` | Execution duration (seconds) |
| `status` | `Optional[HopStatus]` | Execution status |
| `retry_count` | `int` | Retry count |
| `error_type` | `Optional[str]` | Exception class name for transmission failure, `None` for verification failure and success |

---

## 9. Hop.py Writing Conventions

### Standard Template

```python
import asyncio
from hop_engine.config.model_config import ModelConfig
from hop_engine.processors.hop_processor import HopProc
from hop_engine.config.constants import HopStatus
from hop_engine.utils.state_store import JsonlStateStore

run_config = ModelConfig.from_yaml("system", file_path="settings.yaml")
verify_config = ModelConfig.from_yaml("verify", file_path="settings.yaml")

hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
)

async def process(input_data: dict) -> dict:
    store = JsonlStateStore("output.jsonl")
    async with hop_proc.session(state_store=store) as s:
        # Step 1: Information retrieval
        # After hop_get execution, task+result summary automatically retained in session history
        status, result = await s.hop_get(
            task="Extract key information",
            context=input_data["text"],
        )
        if status != HopStatus.OK:
            s.hop_exit("EXIT_ERR", "Information retrieval failed")
            return {"error": f"{status}: {result}"}

        # Step 2: Judgment
        # hop_judge's LLM can see step 1's task+result summary
        status, verdict = await s.hop_judge(
            task="Judge if conditions are met",
            context=result,
        )
        if status != HopStatus.OK:
            s.hop_exit("EXIT_UNCERTAIN", "Judgment uncertain")
            return {"result": "uncertain", "detail": result}

        # Step 3: Independent judgment (without history)
        # include_history=False: LLM doesn't see previous history, but result still retained
        status, extra = await s.hop_get(
            task="Independent analysis",
            context=input_data["extra"],
            include_history=False,
        )

        s.hop_exit("EXIT_OK", "Normal completion")
        return {"result": verdict}

asyncio.run(process({"text": "..."}))
```

### Key Conventions

1. **Always check status**: After each operator call, check `status != HopStatus.OK` to decide whether to continue, degrade, or exit
2. **Don't try/except operator calls**: Operators don't throw exceptions (except `session=None`), use status checks instead
3. **Use `session.hop_exit()` to record exit points**: Mark exit branches before each `return`, convenient for debugging and tracing
4. **Entry uses `asyncio.run()`**: All LLM I/O must be async/await
5. **Resource release**: For long-running processes, use `await hop_proc.aclose()` to release LLM connections
6. **Concurrent tasks use `asyncio.gather`**: Multiple sessions within same event loop can safely run concurrently
7. **Don't share HopProc or HopSession across threads**

### Fine-grained Status Handling

```python
status, result = await s.hop_get(task="...", context="...")
if status == HopStatus.OK:
    process(result)
elif status == HopStatus.UNCERTAIN:
    process_with_warning(result)       # Degrade to use uncertain result
elif status == HopStatus.LACK_OF_INFO:
    logger.info(f"Insufficient information: {result}")  # Retry after supplementing information
elif status == HopStatus.FAIL:
    last = s.state.step_records[-1]
    if last.error_type:
        logger.error(f"Transmission failure: {last.error_type}")
    else:
        logger.warning(f"Verification failure: {result}")
```

---

## 10. Related Documentation

| Document | Content |
|----------|---------|
| `hoplogic/docs/hop.md` | Three operators API detailed reference (entry point) |
| `hoplogic/docs/hop_session.md` | HopSession session management |
| `hoplogic/docs/hop_processor.md` | HopProc internal methods |
| `hoplogic/docs/hop_validators.md` | Verifier details |
| `hoplogic/docs/hop_llm.md` | LLM invocation layer |
| `hoplogic/docs/hop_monitoring.md` | Statistics and monitoring |
| `hoplogic/docs/hop_state_store.md` | Execution state persistence |
| `hoplogic/docs/hop_error_handling.md` | Exception and error handling conventions |
| `hoplogic/docs/hop_concurrency.md` | Multi-thread concurrency guide |
| `hoplogic/docs/hop_testing.md` | Unit testing instructions |
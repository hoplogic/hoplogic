# Batch Testing Data Format Specification

This document standardizes the input/output JSONL data format for HOP batch testing.

## Input Format

Each test case is one line of JSON:

```jsonl
{"id": 1, "tag": "fabrication", "description": "...", "<input_fields>": "...", "expected_<output_field>": ...}
```

### Field Definitions

| Field | Type | Required | Description |
|------|------|------|------|
| `id` | int | Yes | Unique incremental identifier |
| `tag` | string | Yes | Classification tag (used for grouping statistics) |
| `<input_fields>` | per contract | Yes | All fields from metainfo input contract |
| `description` | string | No | Test case description |
| `expected_<field>` | per contract | No | Expected output value (used for automated comparison) |
| `difficulty` | string | No | "easy" / "medium" / "hard" |

### Verify Task Input Example

```jsonl
{"id": 1, "tag": "fabrication", "description": "Completely fabricated data", "context_window": "Company A's 2023 revenue was 12 billion yuan", "model_output": "Company A's 2023 revenue was 20 billion yuan", "expected_hallucination_detected": true}
{"id": 2, "tag": "clean", "description": "Output faithful to original text", "context_window": "Company B was founded in 2010", "model_output": "Company B was founded in 2010", "expected_hallucination_detected": false}
```

## Output Format

Batch testing results are also in JSONL, but **two producers use different wrapper formats**:

| Producer | Command | Wrapper Format | Example |
|--------|------|-------------|------|
| `batchhoptest` CLI | `/batchhoptest` | flat record + `hop_result` | `{"id":1, "question":"...", "hop_result":"{...}"}` |
| View `_batch_worker` | UI batch testing | `{"input":{...}, "result":"..."}` | `{"input":{"question":"..."}, "result":"{...}"}` |

Both formats coexist in the same `TestCases/` directory. **Consumers must handle both formats**:

- `BaseDataStore._normalize_audit()` — can parse both formats (nested `result` fields are automatically unpacked)
- `BaseService._batch_worker` — input files can be original input or previous batch output, automatically unpacked through `_normalize_input()` (see "Input Normalization" section below)

### Metadata Lines

`_type: meta` lines record profile configuration information, one line per profile:

```jsonl
{"_type": "meta", "profile": "kimi-full", "run_llm": "Kimi-K2-Instruct-0905", "verify_llm": "Kimi-K2-Instruct-0905", "run_params": {"temperature": 0.1, "max_tokens": 4000}, "timestamp": "2026-02-19T10:30:00"}
```

| Field | Type | Description |
|------|------|------|
| `_type` | string | Fixed as "meta" |
| `profile` | string | Profile name |
| `run_llm` | string | Execution LLM model name |
| `verify_llm` | string | Verification LLM model name |
| `run_params` | object | Execution parameters (temperature, max_tokens, etc.) |
| `timestamp` | string | ISO 8601 timestamp |

### Result Lines

Each test result contains original input + HOP execution result:

```jsonl
{"id": 1, "tag": "fabrication", "context_window": "...", "model_output": "...", "hop_result": "{...}", "hop_stats": {"retry_count": 0, "execution_path": [...], "status": "OK"}, "profile": "kimi-full"}
```

| Field | Type | Description |
|------|------|------|
| `hop_result` | string (JSON) | Hop function return value (JSON string) |
| `hop_stats` | object | Execution statistics |
| `hop_stats.retry_count` | int | Retry count |
| `hop_stats.execution_path` | array | Execution path |
| `hop_stats.status` | string | "OK" / "ERROR" |
| `hop_stats.error` | string | Error message (only when status=ERROR) |
| `profile` | string | Profile name |

### View Batch Output Format

View UI's `_batch_worker` wraps each record as:

```jsonl
{"input": {"question": "What is HOP?"}, "result": "{\"answer\": \"...\", \"confidence\": \"High\", ...}"}
{"input": {"question": "fail case"}, "error": "timeout"}
```

| Field | Type | Description |
|------|------|------|
| `input` | object | Original input (unpacked input contract fields) |
| `result` | string (JSON) | Hop function return value (JSON string), present on success |
| `error` | string | Error message, present on failure |

## Input Normalization

`BaseService._normalize_input()` automatically unpacks input records before batch execution, allowing users to choose any JSONL file as batch input (original input file or previous batch output file):

```
Input record → _normalize_input() → Original input → hop_func()
```

Recognition rules:

| Condition | Determination | Action |
|------|------|------|
| `rec["input"]` is dict and `"result"` or `"error"` exists | View batch output | Return `rec["input"]` |
| Other | Original input or batchhoptest format | Return `rec` as-is |

**Idempotency guarantee**: Output also stores unpacked `input_data` (not original `rec`), avoiding nested layers during repeated execution.

## DataStore Compatibility

- `_type: meta` lines are automatically skipped by `BaseDataStore._normalize_audit()`
- `profile` field is automatically propagated to parsed audit records, supporting `get_stats(profile=...)` filtering
- JSON strings nested in `result` fields are automatically unpacked

## Observer Log Schema

`HopletObserver` writes to `TestCases/observer.jsonl`, containing three record types:

| type | Required Fields | Optional Fields | Description |
|------|---------|---------|------|
| `run_start` | `run_id, timestamp, hoplet, input` | -- | Execution start |
| `run_end` | `run_id, timestamp, duration, status` | `result, metadata` | Execution end |
| `step` | `run_id, timestamp, step, op, task, status, duration` | `retry_count, metadata` | Operator step |

**`step` records are optional**: Only generated when `tracer.trace_step()` is called. If Hoplet doesn't do operator-level tracing (e.g., RAGDemo directly calls `rag.retrieve()` + `session.hop_get()` without manual trace_step), observer logs only contain `run_start/run_end` records.

`BaseDataStore.get_perf_summary()` **must check if `op` column exists** before querying operator_stats (DuckDB infers schema from JSONL, no step records means no op column).
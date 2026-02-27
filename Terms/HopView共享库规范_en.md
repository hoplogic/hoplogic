# HopView Shared Library Specification

## Overview

`hop_view` is the View layer shared library for HOP 2.0 Studio, providing configuration-driven generic code to eliminate per-task code duplication. Each task only needs to declare `ViewConfig` + a thin launcher to reuse all functionality.

Package location: `hoplogic/hop_view/`

## Package Structure

```
hoplogic/hop_view/
├── __init__.py            # Package initialization, __version__="0.3.0", __all__ exports
├── config_schema.py       # ViewConfig + FieldAggregation dataclass definitions
├── observer.py            # HopletObserver + _RunTracer (structured execution logs)
├── file_utils.py          # parse_file() generic file parsing
├── hop_loader.py          # ensure_hop() dynamic loading + resolve_task_paths()
├── datastore.py           # BaseDataStore — configuration-driven ibis + DuckDB queries
├── service.py             # BaseService — configuration-driven business logic (with session management)
├── transport.py           # create_fastapi_app() / create_pywebview_app() factory
├── html_builder.py        # build_index_html() — Jinja2 template rendering
├── renderer.py            # Jinja2 renderer — HTML fragment generation (render_* functions)
├── templates/             # Jinja2 template directory
│   ├── base.html          #   Complete page skeleton (HTMX + CSS + Tab structure)
│   ├── fragments/         #   HTML fragment templates (HTMX responses)
│   └── components/        #   Jinja2 macros (reusable components)
├── css_templates/         # Generic CSS templates
│   ├── base.css           #   Design Tokens (Light/Dark) + generic UI styles
│   └── chatflow.css       #   ChatFlow specific styles
├── batch_runner.py        # CLI batch test runner
├── batch_analysis.py      # CLI batch test result analysis
├── diagnosis.py           # LLM-assisted failure diagnosis
├── fix_generator.py       # LLM-assisted fix generation
├── knowledge_extractor.py # LLM-assisted knowledge extraction
└── test/                  # Test suite
```

## ViewConfig Configuration-Driven Design

### FieldAggregation

```python
@dataclass(frozen=True)
class FieldAggregation:
    field_name: str       # "reliability_score"
    field_type: str       # "int" | "float" | "bool" | "string" | "array"
    agg_type: str         # "mean" | "rate" | "distribution" | "non_null_rate"
    display_label: str    # "Average Reliability Score"
    sub_field: str | None # Sub-field name for array fields (e.g., "type")
```

### ViewConfig

```python
@dataclass(frozen=True)
class ViewConfig:
    task_name: str              # "Verify"
    hoplet_name: str            # "verify_model_output"
    description: str            # Task description
    hop_func_name: str          # "verify_hop"
    input_fields: dict[str, str]      # {"context_window": "str", "model_output": "str"}
    output_fields: list[FieldAggregation]
    empty_table_schema: str           # DuckDB DDL column definitions
    sortable_columns: frozenset[str]  # SQL injection whitelist
    audit_key_field: str              # Record validity check field
    window_title: str                 # "Verify Hoplet"
    window_width: int = 1200
    window_height: int = 820

    # Session security limits
    retry_quota: int | None = None    # None = unlimited retries
    max_feedback_rounds: int = 5      # Maximum feedback rounds
```

### Configuration-Driven Behavior

| Config Field | Consumer | Driven Behavior |
|---|---|---|
| `hop_func_name` | `BaseService.run_task()` | `getattr(hop, config.hop_func_name)(session, data)` |
| `input_fields` | `transport.py` | Dynamically creates Pydantic `RunTaskRequest` model |
| `output_fields` | `BaseDataStore.get_stats()` | Generates ibis aggregation expressions by field type |
| `empty_table_schema` | `BaseDataStore.load_results()` | Empty table creation schema (DDL string, internally converted to ibis.Schema) |
| `sortable_columns` | `BaseDataStore.query_results()` | Sortable columns whitelist |
| `audit_key_field` | `BaseDataStore._normalize_audit()` | Record validity determination |
| `window_title` | `transport.py` | pywebview/FastAPI title |
| `retry_quota` | `BaseService.retry_task()` | Maximum retry count (None = unlimited) |
| `max_feedback_rounds` | `BaseService.submit_feedback()` | Maximum feedback rounds |

## Session Management

BaseService always has session management capabilities, naturally diverting based on hop_status. Non-interactive tasks (hop function only returns OK/FAIL) have their sessions immediately closed, behaving like the old version; interactive tasks (returning LACK_OF_INFO/UNCERTAIN) keep sessions alive waiting for feedback.

**No `interactive` field added**. Whether interaction is needed is determined by frontend Zone events (ViewSpec's ChatFlow Zone `handleResponse` renders branches based on `hop_status`). The backend Service always has session management capabilities.

### Security Limits

| Config Field | Type | Default | Description |
|---|---|---|---|
| `retry_quota` | int \| None | None | Maximum retry count (None = unlimited) |
| `max_feedback_rounds` | int | 5 | Maximum feedback rounds |

### Session Lifecycle

- OK/final state → Immediately close session + complete cleanup
- LACK_OF_INFO/UNCERTAIN → Keep session alive, wait for feedback
- FAIL → Close session, retain inputs (supports retry)

### API Endpoints (always registered)

| Endpoint | Method | Description |
|------|------|------|
| `/api/feedback` | POST | Inject feedback and re-execute |
| `/api/retry` | POST | Retry failed task |
| `/api/cancel` | POST | Interrupt executing task |

### Request Models

```python
from hop_view import FeedbackRequest, RetryRequest, CancelRequest

FeedbackRequest(session_id="uuid", feedback="supplementary information")
RetryRequest(session_id="uuid")
CancelRequest(session_id="uuid")
```

## HTML Template Renderer

`renderer.py` provides server-side HTML fragment generation functions, replacing client-side JS rendering. All functions return `str` (HTML fragment), directly returned as `HTMLResponse` by the Transport layer.

`build_index_html()` generates the complete index.html page through the Jinja2 base.html template. CSS reuses css_templates/base.css + chatflow.css (unchanged). JS reduced to ~100 lines (Tab switching + Error Overlay + HTMX event glue).

```python
from hop_view.html_builder import build_index_html

html = build_index_html(
    VIEW_CONFIG,
    custom_css="--badge-xxx-bg: rgba(...);",
    solve_panel_html=SOLVE_HTML,
    tab_list=[("audit", "Execute"), ("batch", "Batch"), ...],
    interactive=True,
)
```

### Template Directory

- `css_templates/base.css` — Design Tokens (Light/Dark) + generic UI styles (~180 lines)
- `css_templates/chatflow.css` — ChatFlow specific styles (~100 lines)
- `templates/base.html` — Complete page skeleton (HTMX + CSS + Tab switching + Error Overlay)
- `templates/fragments/*.html` — HTML fragments returned by HTMX (result_card, stats_panel, etc.)
- `templates/components/*.html` — Jinja2 macros (gauge, badge, stat_card, etc.)

## Template Field Lookup Chain (mandatory)

The `run_result.html` template must support different Hoplet field names for the same semantics through a fallback chain. When adding new Hoplets, if output field names are not in the existing lookup chain, the template must be updated simultaneously.

Current lookup chain (`normalized` is the return value of `normalize_response(result)`):

| Semantics | Lookup Chain | Usage Location |
|------|--------|---------|
| Clarification list | `clarification_questions` → `clarification_needed` → `missing_info` | LACK_OF_INFO/UNCERTAIN cards |
| Summary text | `answer` → `summary` → `verification_summary` → `presentation` → `problem_summary` | All cards |
| Error message | `normalized.error` → `result.error` → `"Task failed"` | FAIL cards |
| Chart | `chart.image_base64` | All cards |

## Path Resolution Constraints (mandatory)

**All thin launchers (app.py / web.py) must support launching from any working directory**. Paths are derived based on `__file__`, `sys.path` explicitly manages `VIEW_DIR` + `HOPLOGIC_DIR`, prohibiting dependency on `os.getcwd()`.

See `Terms/HopletView架构规范.md` "II. Path Resolution Constraints" for details.

## Migration Guide

After migration, each task's `View/` directory structure:

```
Tasks/<TaskName>/View/
├── ViewSpec/              # Zone-per-file UI specification (see Terms/ViewSpec格式规范.md)
│   ├── index.md
│   ├── rendering.md
│   ├── theme.md
│   └── tabs/              # One directory per Tab, one file per Zone
│       ├── audit/         #   Example: Execute Tab
│       │   ├── _tab.md    #     Tab overview + Zone topology + event routing
│       │   ├── InputForm.md   # Zone: Input form
│       │   └── ResultArea.md  # Zone: Result display
│       ├── batch/
│       │   ├── _tab.md
│       │   └── BatchPanel.md
│       ├── history/
│       │   ├── _tab.md
│       │   ├── FileList.md
│       │   └── DetailPane.md
│       ├── stats/
│       │   ├── _tab.md
│       │   └── StatsPanel.md
│       └── perf/
│           ├── _tab.md
│           └── PerfPanel.md
├── config.py              # ~35 lines — ViewConfig declaration
├── app.py                 # ~30 lines — Thin launcher
├── web.py                 # ~30 lines — Thin launcher
├── index.html             # Frontend UI
└── test/                  # Integration test suite
```

### 1. Create config.py

```python
from hop_view.config_schema import ViewConfig, FieldAggregation

VIEW_CONFIG = ViewConfig(
    task_name="Verify",
    hoplet_name="verify_model_output",
    description="Three-stage logic verification audit",
    hop_func_name="verify_hop",
    input_fields={"context_window": "str", "model_output": "str"},
    output_fields=[
        FieldAggregation("reliability_score", "int", "mean", "Average Reliability Score"),
        FieldAggregation("hallucination_detected", "bool", "rate", "Hallucination Detection Rate"),
        FieldAggregation("errors", "array", "distribution", "Error Type Distribution", sub_field="type"),
    ],
    empty_table_schema="reliability_score INTEGER, hallucination_detected BOOLEAN, ...",
    sortable_columns=frozenset({"reliability_score", "hallucination_detected", "profile"}),
    audit_key_field="reliability_score",
    window_title="Verify Hoplet",
)
```

### 2. Replace app.py

Can be launched from any directory, all paths calculated based on `__file__`:

```python
import os, sys
VIEW_DIR = os.path.dirname(os.path.abspath(__file__))
HOPLOGIC_DIR = os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))
if VIEW_DIR not in sys.path:
    sys.path.insert(0, VIEW_DIR)
if HOPLOGIC_DIR not in sys.path:
    sys.path.insert(0, HOPLOGIC_DIR)
from config import VIEW_CONFIG
from hop_view import create_pywebview_app, BaseService, HopletObserver

TASK_DIR = os.path.abspath(os.path.join(VIEW_DIR, ".."))
service = BaseService(VIEW_CONFIG,
    os.path.join(TASK_DIR, "Hoplet"),
    os.path.join(TASK_DIR, "TestCases"),
    observer=HopletObserver(os.path.join(TASK_DIR, "TestCases", "observer.jsonl")))

if __name__ == "__main__":
    create_pywebview_app(VIEW_CONFIG, service, VIEW_DIR)
```

### 3. Replace web.py

```python
import os, sys
VIEW_DIR = os.path.dirname(os.path.abspath(__file__))
HOPLOGIC_DIR = os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))
if VIEW_DIR not in sys.path:
    sys.path.insert(0, VIEW_DIR)
if HOPLOGIC_DIR not in sys.path:
    sys.path.insert(0, HOPLOGIC_DIR)
from config import VIEW_CONFIG
from hop_view import create_fastapi_app, BaseService, HopletObserver

TASK_DIR = os.path.abspath(os.path.join(VIEW_DIR, ".."))
service = BaseService(VIEW_CONFIG,
    os.path.join(TASK_DIR, "Hoplet"),
    os.path.join(TASK_DIR, "TestCases"),
    observer=HopletObserver(os.path.join(TASK_DIR, "TestCases", "observer.jsonl")))
app = create_fastapi_app(VIEW_CONFIG, service, VIEW_DIR)
```

### 4. Delete Old Files

Delete `observer.py`, `datastore.py`, `service.py` (replaced by shared library).

## pywebview Notes

### Debug Mode

`create_pywebview_app()` supports `debug` parameter:

```python
create_pywebview_app(VIEW_CONFIG, service, VIEW_DIR, debug=True)
```

When `debug=None` (default), automatically detects `HOP_VIEW_DEBUG=1` environment variable or `--debug` command line argument. When enabled, right-click in pywebview window to open Chrome DevTools.

### Frontend Constraints

- **Text selectable**: CSS must explicitly declare `user-select: text` (pywebview disables text selection by default)

### Test Constraints

Project `asyncio_mode = auto` (`hoplogic/pytest.ini`). For async fixtures, recommend using `@pytest_asyncio.fixture` (not `@pytest.fixture`).

## Keyword Matching i18n Rules

Any business logic in the Service layer based on string matching (such as confirmation detection `_is_confirmation()`) must follow:

1. **Explicit constants**: Keyword lists declared as class-level or module-level constant tuples (e.g., `_CONFIRM_PREFIXES`), with language coverage noted in comments
2. **Prefix matching**: Use `text.startswith(PREFIXES)` instead of exact matching, allowing users to append explanations (e.g., "confirm, good plan")
3. **Minimum bilingual requirement**: All keyword sets must cover at least Chinese and English
4. **Parameterized testing**: Each keyword constant must have `@pytest.mark.parametrize` tests covering all terms + negative cases

## batch_runner CLI

Replaces `.roo/templates/batch_hop_test_template.py` template copying mechanism:

```bash
python -m hop_view.batch_runner --task Verify --data verify_testcases.jsonl --workers 5
python -m hop_view.batch_runner --task Verify --data verify_testcases.jsonl --profiles kimi-full qwen3
```

## Frontend Debug Log

Frontend runtime errors and state changes are POSTed to the backend via `_hopLog()` JS function, written to JSONL files. These logs enable Claude Code (or other AI assistants) to perform post-mortem analysis of frontend behavior and error patterns.


### API

#### `BaseService.log_frontend(entry: dict) -> None`

Writes a frontend log entry to `TestCases/frontend-debug.jsonl`. Fire-and-forget, exceptions are silent (observability doesn't affect business).

```python
service.log_frontend({
    "ts": "2026-01-15T10:30:00.123Z",
    "level": "error",
    "message": "HTTP 500",
    "context": None,
})
```

#### `POST /api/debug/log`

Accepts `FrontendLogEntry` JSON body, delegates to `BaseService.log_frontend()` for writing. Always registered (accepts error level logs even in non-debug mode).

Request body:
```json
{"ts": "...", "level": "error|state|event|warn", "message": "...", "context": null}
```

Response: `{"ok": true}`

#### `_HOP_DEBUG` Injection

`build_index_html(..., debug=True)` injects `const _HOP_DEBUG = true` in HTML. Debug panel (`#debug-panel`) only renders when `debug=True`.

`_hopLog()` function is always defined (error level logs always POST), debug panel rendering only activates when `_HOP_DEBUG` is true.

#### Debug Flag Propagation

```
create_pywebview_app(debug=None)
  → _resolve_debug() → resolved_debug
  → create_fastapi_app(debug=resolved_debug)
    → build_index_html(debug=resolved_debug)
      → render_base_page(debug=resolved_debug)
        → base.html: const _HOP_DEBUG = true/false
```

### Log Files

Location: `Tasks/<TaskName>/TestCases/frontend-debug.jsonl` (same directory as `observer.jsonl`).

Not automatically cleared on View restart, enabling Claude Code to analyze complete runtime traces post-mortem.

## Version Management

- `hop_view.__component_version__` = `0.3.0` (independent of hop_engine)
- Follows SemVer rules
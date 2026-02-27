# HopView 共享库规范

## 概述

`hop_view` 是 HOP 2.0 Studio 的 View 层共享库，提供配置驱动的通用代码，消除 per-task 代码重复。每个任务只需声明 `ViewConfig` + 薄启动器即可复用全部功能。

包位置：`hoplogic/hop_view/`

## 包结构

```
hoplogic/hop_view/
├── __init__.py            # 包初始化，__version__="0.3.0"，__all__ 导出
├── config_schema.py       # ViewConfig + FieldAggregation dataclass 定义
├── observer.py            # HopletObserver + _RunTracer（结构化执行日志）
├── file_utils.py          # parse_file() 通用文件解析
├── hop_loader.py          # ensure_hop() 动态加载 + resolve_task_paths()
├── datastore.py           # BaseDataStore — 配置驱动的 ibis + DuckDB 查询
├── service.py             # BaseService — 配置驱动的业务逻辑（含 session 管理）
├── transport.py           # create_fastapi_app() / create_pywebview_app() 工厂
├── html_builder.py        # build_index_html() — Jinja2 模板渲染
├── renderer.py            # Jinja2 渲染器 — HTML 片段生成（render_* 函数）
├── templates/             # Jinja2 模板目录
│   ├── base.html          #   完整页面骨架（HTMX + CSS + Tab 结构）
│   ├── fragments/         #   HTML 片段模板（HTMX 返回）
│   └── components/        #   Jinja2 macros（可复用组件）
├── css_templates/         # 通用 CSS 模板
│   ├── base.css           #   Design Tokens (Light/Dark) + 通用 UI 样式
│   └── chatflow.css       #   ChatFlow 特有样式
├── batch_runner.py        # CLI 批量测试运行器
├── batch_analysis.py      # CLI 批量测试结果分析
├── diagnosis.py           # LLM 辅助失败诊断
├── fix_generator.py       # LLM 辅助修复方案生成
├── knowledge_extractor.py # LLM 辅助知识提取
└── test/                  # 测试套件
```

## ViewConfig 配置驱动设计

### FieldAggregation

```python
@dataclass(frozen=True)
class FieldAggregation:
    field_name: str       # "reliability_score"
    field_type: str       # "int" | "float" | "bool" | "string" | "array"
    agg_type: str         # "mean" | "rate" | "distribution" | "non_null_rate"
    display_label: str    # "平均可靠性评分"
    sub_field: str | None # 数组字段的子字段名（如 "type"）
```

### ViewConfig

```python
@dataclass(frozen=True)
class ViewConfig:
    task_name: str              # "Verify"
    hoplet_name: str            # "verify_model_output"
    description: str            # 任务描述
    hop_func_name: str          # "verify_hop"
    input_fields: dict[str, str]      # {"context_window": "str", "model_output": "str"}
    output_fields: list[FieldAggregation]
    empty_table_schema: str           # DuckDB DDL 列定义
    sortable_columns: frozenset[str]  # SQL 注入白名单
    audit_key_field: str              # 记录有效性检查字段
    window_title: str                 # "Verify Hoplet"
    window_width: int = 1200
    window_height: int = 820

    # Session 安全限制
    retry_quota: int | None = None    # None = 无限重试
    max_feedback_rounds: int = 5      # 最大反馈轮次
```

### 配置驱动行为

| Config 字段 | 消费方 | 驱动的行为 |
|---|---|---|
| `hop_func_name` | `BaseService.run_task()` | `getattr(hop, config.hop_func_name)(session, data)` |
| `input_fields` | `transport.py` | 动态创建 Pydantic `RunTaskRequest` 模型 |
| `output_fields` | `BaseDataStore.get_stats()` | 按字段类型生成 ibis 聚合表达式 |
| `empty_table_schema` | `BaseDataStore.load_results()` | 空表创建 schema（DDL 字符串，内部转 ibis.Schema）|
| `sortable_columns` | `BaseDataStore.query_results()` | 排序列白名单 |
| `audit_key_field` | `BaseDataStore._normalize_audit()` | 记录有效性判断 |
| `window_title` | `transport.py` | pywebview/FastAPI 标题 |
| `retry_quota` | `BaseService.retry_task()` | 最大重试次数（None = 无限） |
| `max_feedback_rounds` | `BaseService.submit_feedback()` | 最大反馈轮次 |

## Session 管理

BaseService 始终具备 session 管理能力，按 hop_status 自然分流。非交互任务（hop 函数只返回 OK/FAIL）的 session 立即关闭，行为等同旧版；交互任务（返回 LACK_OF_INFO/UNCERTAIN）的 session 保活等待反馈。

**不加 `interactive` 字段**。交互与否由前端 Zone 事件决定（ViewSpec 的 ChatFlow Zone `handleResponse` 根据 `hop_status` 分支渲染）。后端 Service 始终具备 session 管理能力。

### 安全限制

| Config 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `retry_quota` | int \| None | None | 最大重试次数 (None = 无限) |
| `max_feedback_rounds` | int | 5 | 最大反馈轮次 |

### Session 生命周期

- OK/终态 → 立即关闭 session + 完全清理
- LACK_OF_INFO/UNCERTAIN → 保活 session，等待 feedback
- FAIL → 关闭 session，保留 inputs（支持 retry）

### API 端点（始终注册）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/feedback` | POST | 注入反馈并重新执行 |
| `/api/retry` | POST | 重试失败任务 |
| `/api/cancel` | POST | 中断执行中任务 |

### 请求模型

```python
from hop_view import FeedbackRequest, RetryRequest, CancelRequest

FeedbackRequest(session_id="uuid", feedback="补充信息")
RetryRequest(session_id="uuid")
CancelRequest(session_id="uuid")
```

## HTML 模板渲染器

`renderer.py` 提供服务端 HTML fragment 生成函数，替代客户端 JS 渲染。所有函数返回 `str`（HTML fragment），由 Transport 层直接作为 `HTMLResponse` 返回。

`build_index_html()` 通过 Jinja2 base.html 模板生成完整的 index.html 页面。CSS 复用 css_templates/base.css + chatflow.css（不变）。JS 缩减为 ~100 行（Tab 切换 + Error Overlay + HTMX 事件粘合）。

```python
from hop_view.html_builder import build_index_html

html = build_index_html(
    VIEW_CONFIG,
    custom_css="--badge-xxx-bg: rgba(...);",
    solve_panel_html=SOLVE_HTML,
    tab_list=[("audit", "执行"), ("batch", "批量"), ...],
    interactive=True,
)
```

### 模板目录

- `css_templates/base.css` — Design Tokens (Light/Dark) + 通用 UI 样式（~180 行）
- `css_templates/chatflow.css` — ChatFlow 特有样式（~100 行）
- `templates/base.html` — 完整页面骨架（HTMX + CSS + Tab 切换 + Error Overlay）
- `templates/fragments/*.html` — HTMX 返回的 HTML 片段（result_card、stats_panel 等）
- `templates/components/*.html` — Jinja2 macros（gauge、badge、stat_card 等）

## 模板字段查找链（强制）

`run_result.html` 模板必须通过 fallback 链兼容不同 Hoplet 对同一语义的不同字段名。新增 Hoplet 时，如果输出字段名不在现有查找链中，必须同步更新模板。

当前查找链（`normalized` 为 `normalize_response(result)` 返回值）：

| 语义 | 查找链 | 使用位置 |
|------|--------|---------|
| 澄清列表 | `clarification_questions` → `clarification_needed` → `missing_info` | LACK_OF_INFO/UNCERTAIN 卡片 |
| 摘要文本 | `answer` → `summary` → `verification_summary` → `presentation` → `problem_summary` | 所有卡片 |
| 错误信息 | `normalized.error` → `result.error` → `"Task failed"` | FAIL 卡片 |
| 图表 | `chart.image_base64` | 所有卡片 |

## 路径解析约束（强制）

**所有薄启动器（app.py / web.py）必须支持从任意工作目录启动**。路径基于 `__file__` 推导，`sys.path` 显式管理 `VIEW_DIR` + `HOPLOGIC_DIR`，禁止依赖 `os.getcwd()`。

详见 `Terms/HopletView架构规范.md`「二、路径解析约束」。

## 迁移指南

迁移后每个任务的 `View/` 目录结构：

```
Tasks/<TaskName>/View/
├── ViewSpec/              # Zone-per-file UI 规范（详见 Terms/ViewSpec格式规范.md）
│   ├── index.md
│   ├── rendering.md
│   ├── theme.md
│   └── tabs/              # 每个 Tab 一个目录，每个 Zone 一个文件
│       ├── audit/         #   示例：执行 Tab
│       │   ├── _tab.md    #     Tab 总览 + Zone 拓扑 + 事件路由
│       │   ├── InputForm.md   # Zone: 输入表单
│       │   └── ResultArea.md  # Zone: 结果展示
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
├── config.py              # ~35 行 — ViewConfig 声明
├── app.py                 # ~30 行 — 薄启动器
├── web.py                 # ~30 行 — 薄启动器
├── index.html             # Frontend UI
└── test/                  # 集成测试套件
```

### 1. 创建 config.py

```python
from hop_view.config_schema import ViewConfig, FieldAggregation

VIEW_CONFIG = ViewConfig(
    task_name="Verify",
    hoplet_name="verify_model_output",
    description="三阶段逻辑核验审计",
    hop_func_name="verify_hop",
    input_fields={"context_window": "str", "model_output": "str"},
    output_fields=[
        FieldAggregation("reliability_score", "int", "mean", "平均可靠性评分"),
        FieldAggregation("hallucination_detected", "bool", "rate", "幻觉检出率"),
        FieldAggregation("errors", "array", "distribution", "错误类型分布", sub_field="type"),
    ],
    empty_table_schema="reliability_score INTEGER, hallucination_detected BOOLEAN, ...",
    sortable_columns=frozenset({"reliability_score", "hallucination_detected", "profile"}),
    audit_key_field="reliability_score",
    window_title="Verify Hoplet",
)
```

### 2. 替换 app.py

可从任意目录启动，所有路径基于 `__file__` 计算：

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

### 3. 替换 web.py

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

### 4. 删除旧文件

删除 `observer.py`, `datastore.py`, `service.py`（由共享库替代）。

## pywebview 注意事项

### 调试模式

`create_pywebview_app()` 支持 `debug` 参数：

```python
create_pywebview_app(VIEW_CONFIG, service, VIEW_DIR, debug=True)
```

`debug=None`（默认）时自动检测 `HOP_VIEW_DEBUG=1` 环境变量或 `--debug` 命令行参数。启用后可在 pywebview 窗口右键打开 Chrome DevTools。

### Frontend 约束

- **文本可选**：CSS 需显式声明 `user-select: text`（pywebview 默认禁用文本选中）

### 测试约束

项目 `asyncio_mode = auto`（`hoplogic/pytest.ini`）。async fixture 推荐用 `@pytest_asyncio.fixture`（非 `@pytest.fixture`）。

## 关键词匹配 i18n 规则

Service 层任何基于字符串匹配的业务逻辑（如确认检测 `_is_confirmation()`），必须遵循：

1. **显式常量**：关键词列表声明为类级或模块级常量元组（如 `_CONFIRM_PREFIXES`），注释中标注覆盖语言
2. **前缀匹配**：使用 `text.startswith(PREFIXES)` 而非精确匹配，允许用户附加说明（如"确认，方案不错"）
3. **中英双语最低要求**：所有关键词集至少覆盖中文和英文
4. **参数化测试**：每个关键词常量必须有 `@pytest.mark.parametrize` 测试，覆盖所有词条 + 负面用例

## batch_runner CLI

替代 `.roo/templates/batch_hop_test_template.py` 模板复制机制：

```bash
python -m hop_view.batch_runner --task Verify --data verify_testcases.jsonl --workers 5
python -m hop_view.batch_runner --task Verify --data verify_testcases.jsonl --profiles kimi-full qwen3
```

## Frontend Debug Log

前端运行时错误和状态变更通过 `_hopLog()` JS 函数 POST 到后端，写入 JSONL 文件，使 Claude Code 能够事后分析前端行为。

### API

#### `BaseService.log_frontend(entry: dict) -> None`

写入一条前端日志到 `TestCases/frontend-debug.jsonl`。Fire-and-forget，异常静默（可观测性不影响业务）。

```python
service.log_frontend({
    "ts": "2026-01-15T10:30:00.123Z",
    "level": "error",
    "message": "HTTP 500",
    "context": None,
})
```

#### `POST /api/debug/log`

接受 `FrontendLogEntry` JSON body，委托 `BaseService.log_frontend()` 写入。始终注册（非 debug 模式也接受 error 级别日志）。

请求体：
```json
{"ts": "...", "level": "error|state|event|warn", "message": "...", "context": null}
```

响应：`{"ok": true}`

#### `_HOP_DEBUG` 注入

`build_index_html(..., debug=True)` 在 HTML 中注入 `const _HOP_DEBUG = true`。debug 面板（`#debug-panel`）仅在 `debug=True` 时渲染。

`_hopLog()` 函数始终定义（error 级别日志始终 POST），debug 面板渲染仅在 `_HOP_DEBUG` 为 true 时激活。

#### Debug 标志传播

```
create_pywebview_app(debug=None)
  → _resolve_debug() → resolved_debug
  → create_fastapi_app(debug=resolved_debug)
    → build_index_html(debug=resolved_debug)
      → render_base_page(debug=resolved_debug)
        → base.html: const _HOP_DEBUG = true/false
```

### 日志文件

位置：`Tasks/<TaskName>/TestCases/frontend-debug.jsonl`（与 `observer.jsonl` 同目录）。

不在 View 重启时自动清空，便于 Claude Code 事后分析完整运行时轨迹。

## 版本管理

- `hop_view.__component_version__` = `0.3.0`（独立于 hop_engine）
- 遵循 SemVer 规则

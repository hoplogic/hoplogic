# Hoplet View 架构规范

本文是一份面向 AI 编程助手和开发者的 Hoplet View 层架构规范。定义了从本地桌面到云端 Web Service 的统一 UI 架构，指导 `/code2view` 命令生成标准化的 View 目录结构。

> 参考实现：`Tasks/Verify/View/`（当前 pywebview 单文件实现）
> 引擎接口：`hoplogic/hop_engine/core/state_store.py`、`hop_engine/core/status_recorder.py`

---

## 一、设计动机

### 现状问题

当前 Hoplet View 层（以 `Tasks/Verify/View/` 为例）存在以下问题：

1. **无分层设计** — 业务逻辑、传输适配、数据查询混在 `app.py` 的 `Api` 类中。文件解析（`_parse_file`）、统计聚合（`get_stats`）、批量执行（`_batch_worker`）、pywebview 绑定全部耦合在一起
2. **无 Web Service 支持** — 只有 pywebview 桌面模式，单人本地使用。团队多人在线查看测试结果、触发批量测试无法实现
3. **数据查询低效** — `_parse_file` 手动读 JSONL + Python 循环遍历做统计聚合。数据量增长后（万级 TestCases 记录），内存占用和响应时间线性增长
4. **无结构化日志** — Hoplet 执行过程不可观测（只有最终结果 JSONL）。算子级别的耗时、重试次数、中间状态等性能数据随进程退出丢失
5. **`/code2view` 只生成 2 个文件** — `app.py` + `index.html`，缺乏标准化目录结构和关注点分离

### 目标

- **本地 + 云端双模式**：同一套业务逻辑，通过 Transport 层适配 pywebview（本地桌面）和 FastAPI（Web Service）
- **数据查询加速**：JSONL 仍是 source of truth，DuckDB 作为查询加速层，ibis 提供类型安全的表达式 API
- **结构化可观测**：HopletObserver 记录执行过程日志（JSONL 格式，与 `JsonlStateStore` 兼容），供 DataStore 层查询
- **标准化架构**：`/code2view` 生成 6 个文件（而非 2 个），遵循五层分层设计

---

## 二、架构总览

### SSR 架构

```
┌───────────────────────────────────────────────┐
│  Frontend (index.html)                        │  HTML/CSS/JS，Tab 式 UI
│  ┌─────────────────────────────────────────┐  │
│  │  HTMX (hx-get, hx-post, hx-swap)       │  │  声明式 HTTP 交互
│  └─────────────────────────────────────────┘  │
└───────────────┬───────────────────────────────┘
                │  HTTP (GET/POST)
┌───────────────┴───────────────────────────────┐
│  Transport Layer (unified HTTP)               │
│  ┌─────────────┐  ┌────────────────────────┐  │
│  │ app.py      │  │ web.py                 │  │
│  │ (pywebview  │  │ (FastAPI + uvicorn)    │  │
│  │  + embedded │  │                        │  │
│  │  uvicorn)   │  │                        │  │
│  └──────┬──────┘  └───────────┬────────────┘  │
└─────────┼─────────────────────┼───────────────┘
          │                     │
┌─────────┴─────────────────────┴───────────────┐
│  Renderer (Jinja2 templates)                  │  HTML 片段渲染
│  render_tab() / render_stats() / ...          │
└───────────────┬───────────────────────────────┘
                │ await service.*
┌───────────────┴───────────────────────────────┐
│  Service Layer (service.py)                   │  纯 async，dict in/out
│  组装 DataStore + Observer + HopProc          │
└───────────────┬───────────────────────────────┘
                │
┌───────────────┴───────────────────────────────┐
│  DataStore Layer (datastore.py)               │  DuckDB + ibis 查询
│  JSONL → DuckDB → 统计/筛选/聚合              │
└───────────────────────────────────────────────┘

┌───────────────────────────────────────────────┐
│  HopletObserver (observer.py)                 │  结构化日志（JSONL）
│  trace_run / trace_step 上下文管理器           │
└───────────────────────────────────────────────┘
```

### 目录结构

```
Tasks/<TaskName>/
├── Hoplet/
│   ├── metainfo.md
│   ├── HopSpec.md
│   └── Hop.py
├── TestCases/                    # 测试结果 JSONL（source of truth）
└── View/                         # /code2view 生成
    ├── ViewSpec/                 # UI 规范目录
    │   ├── index.md              #   总览 + Tab 列表 + 交互定制 + 文件路由表 + 文件索引
    │   ├── rendering.md          #   渲染映射
    │   └── theme.md              #   布局主题
    ├── config.py                 # ViewConfig 声明（~35 行）
    ├── app.py                    # Transport: pywebview（内嵌 uvicorn HTTP 服务）
    ├── web.py                    # Transport: FastAPI Web Service（SSR，返回 HTML）
    ├── index.html                # Frontend: UI（HTMX 驱动交互）
    └── test/                     # 测试套件（/code2view 生成）
        ├── pytest.ini            # asyncio_mode = auto
        ├── __init__.py           # 空包标记
        ├── conftest.py           # 共享 fixtures
        ├── test_web.py           # web.py 端点测试
        ├── test_config.py        # config.py 测试
        └── test_service.py       # service.py 测试（共享库 BaseService）
```

### 层间依赖规则

```
index.html  →  app.py / web.py  →  service.py  →  datastore.py
                                                →  observer.py
```

- **Frontend** 通过 HTMX 声明式属性发起 HTTP 请求，接收 HTML 片段响应
- **Transport** 统一使用 HTTP 路径（pywebview 内嵌 uvicorn，FastAPI 直接服务），通过 Renderer 生成 HTML
- **Renderer** 使用 Jinja2 将 Service 返回的 dict 渲染为 HTML 片段
- **Service** 是纯 async 函数，返回 `dict`，不依赖任何 Transport 框架
- **DataStore** 和 **Observer** 是 Service 的依赖，彼此独立

### 路径解析约束（任意目录启动）

**所有 View 启动器（app.py / web.py）必须支持从任意工作目录启动**，不依赖 `os.getcwd()`。具体要求：

1. **所有路径基于 `__file__` 计算**：`VIEW_DIR`、`TASK_DIR`、`HOPLET_DIR`、`TESTCASES_DIR` 等均通过 `os.path.abspath(__file__)` 向上推导，不使用相对路径
2. **显式管理 `sys.path`**：启动器必须将 `VIEW_DIR`（用于 `from config import ...`）和 `HOPLOGIC_DIR`（用于 `from hop_view import ...`）加入 `sys.path`，并做去重检查
3. **HOPLOGIC_DIR 计算方式**：`os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))`（从 `Tasks/<Task>/View/` 向上三级到项目根，再进入 `hoplogic/`）
4. **禁止在启动器中使用 `os.chdir()`**：`chdir` 只在 `ensure_hop()` 内部临时使用并恢复

模板：
```python
VIEW_DIR = os.path.dirname(os.path.abspath(__file__))
HOPLOGIC_DIR = os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))
if VIEW_DIR not in sys.path:
    sys.path.insert(0, VIEW_DIR)
if HOPLOGIC_DIR not in sys.path:
    sys.path.insert(0, HOPLOGIC_DIR)
```

---

## 三、DataStore 层（DuckDB + ibis）

### 设计原则

1. **JSONL 是 source of truth** — 所有测试结果和执行日志持久化为 JSONL 文件（与 `JsonlStateStore` 格式兼容）。DuckDB 不持久化数据库文件，仅在内存中构建查询视图
2. **按需加载** — `load_results()` 从 JSONL 文件加载到 DuckDB 内存表，后续查询走 ibis 表达式 API
3. **无副作用** — DataStore 只读 JSONL，不写入、不修改任何文件

### 核心类：BaseDataStore

```python
"""datastore.py — DuckDB + ibis 查询加速层"""

import ibis

from hop_view.config_schema import ViewConfig

class BaseDataStore:
    """基于 ibis + DuckDB 的 TestCases 查询引擎

    JSONL 是 source of truth，DuckDB 是内存查询加速层，ibis 提供类型安全的表达式 API。
    ViewConfig 驱动统计聚合、排序白名单等行为。
    """

    def __init__(self, config: ViewConfig, testcases_dir: str,
                 observer_log: str | None = None):
        self.config = config
        self.testcases_dir = testcases_dir
        self.observer_log = observer_log
        self.con = ibis.duckdb.connect()

    def load_results(self, force_reload: bool = False) -> int:
        """从 TestCases/ 加载 JSONL 到 DuckDB 内存表"""
        ...

    def get_stats(self, profile: str | None = None) -> dict:
        """聚合统计 — 按 ViewConfig.output_fields 配置驱动

        按字段 agg_type 生成对应 ibis 表达式：
        - mean         → .try_cast("float64").mean().round(1)
        - rate         → .try_cast("bool").fill_null(False).sum() / total
        - distribution → DuckDB SQL (from_json + UNNEST)
        - non_null_rate→ .notnull().sum() / total
        """
        ...

    def get_error_distribution(self) -> list[dict]:
        """错误类型分布"""
        ...

    def get_perf_summary(self) -> dict:
        """性能汇总（从 observer 日志中查询）"""
        ...

    def query_results(self, *, offset: int = 0, limit: int = 50,
                      sort_by: str | None = None, ascending: bool = False,
    ) -> list[dict]:
        """分页查询测试结果"""
        ...

    def close(self) -> None:
        """关闭 DuckDB 连接"""
        self.con.disconnect()
```

### ibis 表达式查询示例

DataStore 使用 ibis 表达式 API 查询 DuckDB（类型安全、无 SQL 拼接）：

```python
# 统计聚合（try_cast 处理 VARCHAR 类型的数值字段）
t = con.table("results")
total = t.count().execute()  # → Python int
avg_score = t["credit_score"].try_cast("float64").mean().round(1).execute()

# 布尔率统计
cnt = t["active"].try_cast("bool").fill_null(False).sum().execute()
rate = round(cnt / total, 4)

# 分页查询（返回 list[dict]，无 pandas）
rows = (
    t.order_by(ibis.desc("score"))
    .limit(50, offset=0)
    .to_pyarrow()
    .to_pylist()
)

# 性能百分位（从 observer 日志表）
obs = con.table("observer_log")
runs = obs.filter(obs.type == "run_end")
run_stats = runs.aggregate(
    total_runs=runs.count(),
    avg_duration=runs.duration.cast("float64").mean(),
    p50=runs.duration.cast("float64").quantile(0.5),
    p95=runs.duration.cast("float64").quantile(0.95),
).to_pyarrow().to_pylist()

# 错误类型分布（DuckDB-specific from_json + UNNEST，保留 raw SQL）
expr = con.sql(
    "SELECT e->>'severity' AS val, COUNT(*) AS cnt "
    "FROM results, UNNEST(from_json(errors, '[\"json\"]')) AS t(e) "
    "WHERE errors IS NOT NULL "
    "GROUP BY val ORDER BY cnt DESC"
)
dist = expr.to_pyarrow().to_pylist()
```

### 与 `_parse_file` 的对比

| 维度 | 现有实现（`_parse_file` + Python 循环） | DataStore（ibis → DuckDB） |
|------|----------------------------------------|---------------------------|
| 数据加载 | 每次请求全量读文件 | 按需加载到内存表，增量刷新 |
| 聚合查询 | Python for 循环逐条累加 | ibis → DuckDB 向量化执行 |
| 万级数据响应 | 秒级（取决于 Python 解释器） | 毫秒级（DuckDB 列式引擎） |
| 百分位统计 | 需手动排序 + 索引 | `runs.duration.quantile(0.95)` 一行 |
| 内存管理 | 全部 JSON 对象常驻 | DuckDB 列式压缩 |

---

## 四、HopletObserver（结构化日志）

### 设计原则

1. **写 JSONL，读交给 DuckDB** — Observer 只负责写入结构化日志到 JSONL 文件，查询统计由 DataStore 层完成
2. **与 `JsonlStateStore` 格式兼容** — 日志记录的 `type`、`run_id`、`timestamp`、`duration` 等字段与 `state_store.py` 中 `JsonlStateStore` 的格式保持一致，可共用同一张 DuckDB 表
3. **轻量级** — 不引入额外依赖（只需 `json` + `threading`），不影响 Hoplet 执行性能

### 日志格式

每条日志是一行 JSON，包含以下字段：

```jsonl
{"type":"run_start","run_id":"abc-123","timestamp":1700000000.0,"input":{...},"hoplet":"verify_model_output"}
{"type":"step","run_id":"abc-123","timestamp":1700000001.2,"step":1,"op":"hop_get","task":"拆解原子事实","status":"OK","duration":3.45,"retry_count":0}
{"type":"step","run_id":"abc-123","timestamp":1700000005.8,"step":2,"op":"hop_get","task":"溯源判定","status":"OK","duration":4.56,"retry_count":1}
{"type":"run_end","run_id":"abc-123","timestamp":1700000020.0,"duration":20.0,"status":"OK","result":{...}}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `str` | `"run_start"` / `"step"` / `"run_end"` — 与 `JsonlStateStore` 的 `"step"` / `"function"` 兼容 |
| `run_id` | `str` | 执行批次标识（与 `HopSession.run_id` 一致） |
| `timestamp` | `float` | Unix 时间戳（`time.time()`） |
| `step` | `int` | 步骤序号（仅 `type=="step"` 时） |
| `op` | `str` | 算子名称（仅 `type=="step"` 时） |
| `task` | `str` | 任务描述（仅 `type=="step"` 时） |
| `status` | `str` | `"OK"` / `"FAIL"` / `"UNCERTAIN"` / `"LACK_OF_INFO"` |
| `duration` | `float` | 耗时秒数 |
| `retry_count` | `int` | 重试次数（仅 `type=="step"` 时） |
| `input` | `dict` | 输入数据（仅 `type=="run_start"` 时） |
| `result` | `dict` | 最终结果（仅 `type=="run_end"` 时） |
| `hoplet` | `str` | Hoplet 名称（仅 `type=="run_start"` 时） |
| `metadata` | `dict` | 可选扩展字段 |

### 核心类：HopletObserver

```python
"""observer.py — 轻量结构化日志"""

import json
import threading
import time
from contextlib import contextmanager

class HopletObserver:
    """Hoplet 执行过程的结构化日志记录器

    写 JSONL 文件，读由 DataStore（DuckDB）完成。
    线程安全（threading.Lock 保护文件写入）。
    """

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._lock = threading.Lock()

    def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)

    @contextmanager
    def trace_run(self, run_id: str, hoplet: str, input_data: dict):
        """记录一次完整的 Hoplet 执行

        Usage:
            with observer.trace_run(run_id, "verify", input_data) as tracer:
                tracer.trace_step(1, "hop_get", "拆解原子事实", "OK", 3.45, 0)
                ...
        """
        self._append({
            "type": "run_start",
            "run_id": run_id,
            "timestamp": time.time(),
            "hoplet": hoplet,
            "input": input_data,
        })
        start = time.time()
        tracer = _RunTracer(self, run_id)
        try:
            yield tracer
        except Exception as e:
            self._append({
                "type": "run_end",
                "run_id": run_id,
                "timestamp": time.time(),
                "duration": round(time.time() - start, 4),
                "status": "FAIL",
                "metadata": {"error": str(e)},
            })
            raise
        else:
            self._append({
                "type": "run_end",
                "run_id": run_id,
                "timestamp": time.time(),
                "duration": round(time.time() - start, 4),
                "status": tracer.last_status or "OK",
                "result": tracer.last_result,
            })


class _RunTracer:
    """trace_run 上下文内的步骤记录器"""

    def __init__(self, observer: HopletObserver, run_id: str):
        self._observer = observer
        self._run_id = run_id
        self.last_status: str | None = None
        self.last_result: dict | None = None

    def trace_step(
        self, step: int, op: str, task: str,
        status: str, duration: float, retry_count: int = 0,
        metadata: dict | None = None,
    ) -> None:
        record = {
            "type": "step",
            "run_id": self._run_id,
            "timestamp": time.time(),
            "step": step,
            "op": op,
            "task": task,
            "status": status,
            "duration": round(duration, 4),
            "retry_count": retry_count,
        }
        if metadata:
            record["metadata"] = metadata
        self._observer._append(record)
        self.last_status = status

    def set_result(self, result: dict) -> None:
        self.last_result = result
```

### 与 `JsonlStateStore` 的关系

| 维度 | `JsonlStateStore` | `HopletObserver` |
|------|-------------------|------------------|
| 写入时机 | 引擎内部（`auto_record_status` 装饰器自动调用） | View 层（`service.py` 在执行 Hoplet 前后显式调用） |
| 记录粒度 | 算子级（step）+ 函数级（function） | 运行级（run_start/run_end）+ 算子级（step） |
| 关注点 | 引擎可观测性（重试、异常链） | UI 可观测性（输入/输出、执行轨迹） |
| 字段兼容 | `type`、`run_id`、`timestamp`、`step`、`op`、`duration`、`status` | 相同字段名 + 额外 `input`、`result`、`hoplet` |
| 查询方式 | 外部工具读取 | DataStore（DuckDB）查询 |

两者写入不同的 JSONL 文件，但 DataStore 可将两者同时加载到 DuckDB 做联合查询。如果 `HopSession` 已配置 `state_store`，Observer 的 step 级日志可省略（避免重复），只记录 `run_start` 和 `run_end`。

---

## 五、Service 层

### 设计原则

1. **纯 async + dict in/out** — 所有方法都是 async 函数，接收 dict 参数，返回 dict 结果。不依赖任何 Transport 框架（pywebview / FastAPI）
2. **组装层** — 组装 DataStore、Observer、HopProc，协调执行流程
3. **无状态方法** — 每次调用独立（批量测试的进度状态通过 `_batch` 字典管理，仅限单进程）

### 核心类：HopletService

```python
"""service.py — 纯业务逻辑，Transport 无关"""

import asyncio
from dataclasses import dataclass, field

@dataclass
class BatchProgress:
    running: bool = False
    completed: int = 0
    total: int = 0
    errors: int = 0
    output_file: str = ""

class HopletService:
    """Hoplet View 的业务逻辑层

    纯 async 方法，dict in/out。
    Transport 层（app.py / web.py）调用本类方法并序列化为 JSON。
    """

    def __init__(
        self,
        hoplet_dir: str,
        testcases_dir: str,
        observer: HopletObserver | None = None,
    ):
        self.hoplet_dir = hoplet_dir
        self.testcases_dir = testcases_dir
        self.datastore = HopletDataStore(testcases_dir)
        self.observer = observer
        self._hop_module = None
        self._batch = BatchProgress()

    # === 单次执行 ===

    async def run_task(self, input_data: dict) -> dict:
        """执行单个 Hoplet 任务

        Args:
            input_data: Hoplet 输入（按 metainfo 输入契约）

        Returns:
            Hoplet 输出（按 metainfo 输出契约）或 {"error": str}
        """
        ...

    # === 批量测试 ===

    async def list_test_files(self) -> list[dict]:
        """列出 TestCases/ 下可用测试文件

        Returns:
            [{"name": str, "size": int, "records": int}, ...]
        """
        ...

    async def start_batch(self, filename: str, workers: int = 5) -> dict:
        """启动批量测试（非阻塞）

        Returns:
            {"status": "started", "total": int} 或 {"error": str}
        """
        ...

    async def get_batch_progress(self) -> dict:
        """查询批量测试进度

        Returns:
            {"running": bool, "completed": int, "total": int,
             "errors": int, "output_file": str}
        """
        ...

    # === 数据查询 ===

    async def list_results(self) -> list[dict]:
        """扫描 TestCases/ 文件列表

        Returns:
            [{"name": str, "size": int, "mtime": float}, ...]
        """
        ...

    async def load_result(self, filename: str) -> list[dict]:
        """加载单个结果文件内容

        Returns:
            记录列表 或 {"error": str}
        """
        ...

    async def get_stats(self) -> dict:
        """聚合统计（委托 DataStore）

        Returns:
            {"total": int, "avg_score": float, ...}
        """
        self.datastore.load_results()
        return self.datastore.get_stats()

    async def get_perf_summary(self) -> dict:
        """性能汇总（委托 DataStore 查询 observer 日志）

        Returns:
            {"avg_duration": float, "p50": float, "p95": float, ...}
        """
        self.datastore.load_results()
        return self.datastore.get_perf_summary()
```

### 与现有 `Api` 类的对比

| 维度 | 现有 `Api`（`app.py`） | `HopletService` |
|------|----------------------|-----------------|
| 方法签名 | 返回 `str`（JSON 字符串） | 返回 `dict`（序列化交给 Transport） |
| 同步/异步 | 同步（`asyncio.run()` 桥接） | 纯 async |
| 数据查询 | 手动 `_parse_file` + Python 循环 | 委托 `HopletDataStore`（DuckDB） |
| 可观测性 | 无 | 通过 `HopletObserver` 记录执行日志 |
| Transport 耦合 | 直接被 pywebview 绑定 | 无框架依赖，可被任意 Transport 调用 |

---

## 六、Transport 层 — 统一 HTTP

SSR 架构下，pywebview 和 FastAPI 共享同一 HTTP 路径。pywebview 通过内嵌 uvicorn HTTP 服务器访问 FastAPI 端点，前端统一使用 HTMX 发起请求、接收 HTML 片段响应。

### pywebview 模式（app.py）

pywebview 不再使用 JS API bridge（`window.pywebview.api.*`），而是内嵌 uvicorn HTTP 服务器，前端通过 `http://localhost:{port}` 访问与 FastAPI 相同的端点。

```python
"""app.py — pywebview 桌面模式（内嵌 uvicorn HTTP 服务）"""

import os, sys, threading
import uvicorn
import webview

VIEW_DIR = os.path.dirname(os.path.abspath(__file__))
HOPLOGIC_DIR = os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))
if VIEW_DIR not in sys.path:
    sys.path.insert(0, VIEW_DIR)
if HOPLOGIC_DIR not in sys.path:
    sys.path.insert(0, HOPLOGIC_DIR)

from config import VIEW_CONFIG
from hop_view import create_pywebview_app, BaseService

service = BaseService(VIEW_CONFIG, hoplet_dir=..., testcases_dir=...)
create_pywebview_app(VIEW_CONFIG, service, VIEW_DIR)
```

`create_pywebview_app()` 内部流程：

1. 调用 `create_fastapi_app()` 构建 FastAPI 应用（与 `web.py` 共享同一套端点 + Jinja2 渲染）
2. 启动 `uvicorn.Server` 在后台线程中监听 `127.0.0.1:{free_port}`
3. 创建 pywebview 窗口，`url` 指向 `http://127.0.0.1:{port}`
4. 窗口关闭时停止 uvicorn 服务器

```python
# create_pywebview_app 的核心实现（hop_view/transport.py）
def create_pywebview_app(config, service, view_dir, debug=None):
    app = create_fastapi_app(config, service, view_dir)
    uv_config = uvicorn.Config(app, host="127.0.0.1", port=0)
    server = uvicorn.Server(uv_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # ... wait for server ready, get actual port ...
    window = webview.create_window(
        config.task_name, url=f"http://127.0.0.1:{port}",
        width=1200, height=820, min_size=(900, 600),
    )
    webview.start(debug=_resolve_debug(debug))
    server.should_exit = True
```

**特点**：
- 本地单人使用，通过 localhost HTTP 通信
- pywebview 窗口管理生命周期，uvicorn 在后台线程运行
- 与 FastAPI 模式共享完全相同的端点和 Jinja2 渲染逻辑

#### 调试模式

`HOP_VIEW_DEBUG=1` 或 `--debug` 启用 Chrome DevTools：

```bash
HOP_VIEW_DEBUG=1 uv run --no-sync python Tasks/<TaskName>/View/app.py
```

### FastAPI 模式（web.py）— SSR 端点

FastAPI 端点返回 `HTMLResponse`（Jinja2 渲染的 HTML 片段），HTMX 直接将响应插入 DOM。

```python
"""web.py — FastAPI SSR Transport"""

import os, sys
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

VIEW_DIR = os.path.dirname(os.path.abspath(__file__))
HOPLOGIC_DIR = os.path.abspath(os.path.join(VIEW_DIR, "..", "..", "..", "hoplogic"))
if VIEW_DIR not in sys.path:
    sys.path.insert(0, VIEW_DIR)
if HOPLOGIC_DIR not in sys.path:
    sys.path.insert(0, HOPLOGIC_DIR)

from config import VIEW_CONFIG
from hop_view import create_fastapi_app, BaseService

service = BaseService(VIEW_CONFIG, hoplet_dir=..., testcases_dir=...)
app = create_fastapi_app(VIEW_CONFIG, service, VIEW_DIR)
```

`create_fastapi_app()` 内部注册的端点示例：

```python
# hop_view/transport.py 中的 SSR 端点（由 create_fastapi_app 注册）

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 — 返回完整 index.html"""
    return templates.TemplateResponse("index.html", {"request": request, "config": config})

@app.get("/tab/stats", response_class=HTMLResponse)
async def render_stats(request: Request):
    """统计 Tab — 返回 HTML 片段"""
    data = await service.get_stats()
    return render_stats_fragment(data, config)

@app.post("/tab/run", response_class=HTMLResponse)
async def render_run_result(request: Request):
    """执行结果 — 返回 HTML 片段"""
    form = await request.form()
    result = await service.run_task(dict(form))
    return render_result_fragment(result, config)

@app.get("/tab/history", response_class=HTMLResponse)
async def render_history(request: Request):
    """历史 Tab — 返回 HTML 片段"""
    records = await service.list_results()
    return render_history_fragment(records, config)
```

**特点**：
- 端点返回 `HTMLResponse`（HTML 片段），HTMX 通过 `hx-swap` 插入 DOM
- Jinja2 模板在服务端渲染，前端无需 JSON 解析和 DOM 构建逻辑
- `Depends()` 依赖注入：便于扩展认证、限流等中间件
- `lifespan` 管理共享资源（DuckDB 连接、Observer 文件句柄）

---

## 七、Frontend — HTMX 驱动

### HTMX 交互模型

SSR 架构下，前端不再需要 JS API 适配器。交互通过 HTMX 声明式属性直接驱动 HTTP 请求，服务端返回 HTML 片段，HTMX 自动将响应插入目标 DOM 节点。

前端 JS 代码量从 ~300 行（JS API Adapter + JSON→DOM 渲染）缩减到 ~100 行（Tab 切换、错误叠层、表单粘合）。

```html
<!-- Tab 切换 — HTMX 声明式 -->
<nav>
  <button hx-get="/tab/stats" hx-target="#tab-content" hx-swap="innerHTML"
          class="tab-btn active">统计</button>
  <button hx-get="/tab/history" hx-target="#tab-content" hx-swap="innerHTML"
          class="tab-btn">历史</button>
  <button hx-get="/tab/batch" hx-target="#tab-content" hx-swap="innerHTML"
          class="tab-btn">批量</button>
  <button hx-get="/tab/perf" hx-target="#tab-content" hx-swap="innerHTML"
          class="tab-btn">性能</button>
</nav>
<div id="tab-content">
  <!-- HTMX 将服务端返回的 HTML 片段插入此处 -->
</div>

<!-- 执行表单 — HTMX POST -->
<form hx-post="/tab/run" hx-target="#result-area" hx-swap="innerHTML"
      hx-indicator="#loading">
  <textarea name="context_window" placeholder="上下文窗口"></textarea>
  <textarea name="model_output" placeholder="模型输出"></textarea>
  <button type="submit">执行</button>
  <span id="loading" class="htmx-indicator">执行中...</span>
</form>
<div id="result-area"></div>

<!-- 批量测试进度轮询 — HTMX 自动触发 -->
<div hx-get="/tab/batch/progress" hx-trigger="every 2s [batch_running]"
     hx-target="#batch-progress" hx-swap="innerHTML">
</div>
```

### 前端 JS 职责（~100 行）

SSR 后前端 JS 仅负责三类逻辑：

1. **Tab 切换高亮**：监听 `htmx:afterOnLoad` 事件，切换 `active` CSS 类
2. **错误叠层**：全局错误捕获 + appendError()
3. **表单粘合**：少量逻辑控制（如批量测试启动/停止切换）

```javascript
// Tab 切换高亮（~15 行）
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// 错误叠层（~30 行）
function appendError(msg, file, line) {
  const overlay = document.getElementById('error-overlay');
  const div = document.createElement('div');
  div.textContent = `${msg} (${file}:${line})`;
  overlay.appendChild(div);
  overlay.style.display = 'block';
}
window.addEventListener("error", (e) => appendError(e.message, e.filename, e.lineno));
window.addEventListener("unhandledrejection", (e) => appendError(String(e.reason)));

// HTMX 错误事件（~10 行）
document.addEventListener('htmx:responseError', (e) => {
  appendError('HTTP ' + e.detail.xhr.status + ': ' + e.detail.xhr.statusText);
});
```

### Frontend 约束

#### 文本可选中（全局默认策略）

pywebview 默认禁用页面文本选中。**必须使用全局 `*` 选择器设为可选中，交互控件 opt-out**。

**禁止**逐个元素白名单声明 `user-select: text`（新增元素必然遗漏）。

```css
/* 正确：全局默认可选中，交互控件 opt-out */
* { -webkit-user-select: text; user-select: text; }
button, input, select, .btn { -webkit-user-select: none; user-select: none; }
textarea { -webkit-user-select: text; user-select: text; }
```

```css
/* 错误：白名单逐个声明，新增元素必然遗漏 */
body, textarea, .result-card, .json-block, .err-table td { user-select: text; }
```

**测试保障**：`test_web.py::TestIndexHtmlConstraints` 包含两条静态检查：
1. `test_global_user_select_text` — 必须在 `*` 选择器上声明
2. `test_no_per_element_user_select_text` — 禁止逐元素声明（`*` 和 `textarea` 除外）

#### 错误叠层（Error Overlay）

pywebview 环境下 JS 错误不可见（无控制台）。index.html 必须内嵌错误叠层，捕获所有未处理异常并在 UI 底部显示：

```javascript
// 全局错误捕获
window.addEventListener("error", (e) => appendError(e.message, e.filename, e.lineno));
window.addEventListener("unhandledrejection", (e) => appendError(e.reason));

// HTMX 错误也应捕获
document.addEventListener("htmx:responseError", (e) => appendError("HTTP " + e.detail.xhr.status));
```

错误叠层显示在页面底部，红色边框，包含错误消息和堆栈信息。用户无需打开 DevTools 即可看到错误。

> **ChatFlow 组件详细设计**：交互式 Hoplet 的 chat-flow 布局（对话流、消息卡片、状态机、Session 管理）详见 [Terms/ChatFlow组件规范.md](ChatFlow组件规范.md)。

### 五个 Tab

| Tab | 名称 | 功能 | SSR 端点 |
|-----|------|------|----------|
| 1 | 执行 | 输入数据 + 执行 Hoplet + 结果渲染 | `POST /tab/run` |
| 2 | 批量 | 文件选择 + 并发配置 + 进度条 | `POST /tab/batch/start` / `GET /tab/batch/progress` |
| 3 | 历史 | 左侧文件列表 + 右侧记录详情 | `GET /tab/history` / `GET /tab/history/{name}` |
| 4 | 统计 | 总数卡片 + 指标均值 + 分布条形图 | `GET /tab/stats` |
| 5 | 性能 | 平均耗时 + 百分位 + 算子级统计 | `GET /tab/perf` |

前 4 个 Tab 与现有 Verify/View 一致（执行审计、批量测试、历史结果、统计概览）。第 5 个 Tab（性能监控）是新增功能，展示 HopletObserver 记录的执行性能数据。

### 性能监控 Tab 内容

```
┌──────────────────────────────────────────────┐
│  性能监控                                      │
│                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │  3.2s   │ │  2.8s   │ │  8.1s   │       │
│  │ 平均耗时 │ │  P50    │ │  P95    │       │
│  └─────────┘ └─────────┘ └─────────┘       │
│                                              │
│  算子级统计                                    │
│  ┌─────────┬──────┬──────┬──────┬──────┐    │
│  │ 算子     │ 调用 │ 成功率│ 均耗时│ 重试 │    │
│  ├─────────┼──────┼──────┼──────┼──────┤    │
│  │ hop_get │ 156  │ 95%  │ 2.1s │ 0.3  │    │
│  │ hop_judge│ 42  │ 90%  │ 3.4s │ 0.5  │    │
│  └─────────┴──────┴──────┴──────┴──────┘    │
└──────────────────────────────────────────────┘
```

---

## 八、多人服务扩展

当通过 FastAPI（`web.py`）提供 Web Service 时，需要注意以下并发安全事项。

### HopProc 全局单例 + 每请求独立 Session

`HopProc` 是无状态的算子抽象（持有 LLM 客户端和模型配置），可全局单例共享。每个 HTTP 请求创建独立的 `HopSession`：

```python
# web.py 中的执行逻辑
async def run_task(req, service):
    hop_proc = service.hop_proc  # 全局单例
    async with hop_proc.session() as s:
        # 每个请求独立的 session（独立对话历史、HopState、ExecutionStats）
        result = await hoplet_main(s, req.model_dump())
    return result
```

这遵循 HOP 引擎的并发规则：**同一 session 禁止并发算子调用，需要并发时创建独立 session**。

### GLOBAL_STATS 线程安全

`GLOBAL_STATS`（`ExecutionStats`）的 `merge_from()` 方法已使用 `threading.Lock` 保护，支持多个 `HopSession.__aexit__` 并发合并。Web Service 场景下无需额外处理。

### DuckDB 连接管理

ibis DuckDB 后端的内存连接不是线程安全的。两种方案：

1. **单连接 + 读写锁**：所有查询串行化（适合读多写少场景）
2. **连接池**：每个请求获取独立连接（适合高并发场景）

推荐方案 1（Hoplet View 的查询并发度通常不高）：

```python
class HopletDataStore:
    def __init__(self, testcases_dir: str):
        self.con = ibis.duckdb.connect()
        self._lock = threading.Lock()

    def get_stats(self) -> dict:
        with self._lock:
            t = self.con.table("results")
            total = t.count().execute()
            ...
```

### 认证鉴权 Depends() 示例

FastAPI 的 `Depends()` 机制可灵活扩展认证、限流等中间件：

```python
from fastapi import Depends, Header, HTTPException

async def verify_token(authorization: str = Header(...)):
    """简单的 Bearer Token 认证"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization[7:]
    # 验证 token...
    return token

@app.post("/api/run")
async def run_task(
    req: RunTaskRequest,
    service: HopletService = Depends(get_service),
    token: str = Depends(verify_token),  # 添加认证
):
    return await service.run_task(req.model_dump())
```

---

## 九、ViewSpec — UI 规范层

### 概述

ViewSpec 是 View 层的声明式规范目录（`View/ViewSpec/`），将 UI 定制逻辑从 `/code2view` 命令模板中剥离为独立、可审计、可 diff 的 Markdown 文件集。

ViewSpec 承担双重角色——对于每个任务独立生成代码的 Zone（**generated**），ViewSpec 是**生成规格**；对于共享库中已固化代码的 Zone（**shared**），ViewSpec 是**接口契约**（记录行为 + 声明参数化接口）。同一个 ViewSpec 目录内可混合两种角色。随着代码成熟度提升，Zone 可从 generated 渐进固化为 shared。

详细格式规范见 `Terms/ViewSpec格式规范.md`（§2.1 Zone 的实现来源）。

### 目录结构

```
View/ViewSpec/
├── index.md              # 总览：Tab 列表 + Zone 索引 + API 适配 + 通用行为 + 原语定义 + 文件路由表
├── rendering.md          # 渲染映射：输入/输出字段 + 复合组件 + 结果归一化 + 统计聚合
├── theme.md              # 布局主题：Design Tokens + 布局尺寸 + CSS 类清单 + 动画
└── tabs/                 # 交互流：每个 Tab 一个目录，每个 Zone 一个文件
    ├── solve/            #   执行 Tab（示例：chat-flow 布局）
    │   ├── _tab.md       #     Tab 总览：布局 + Zone 拓扑 + 事件路由表
    │   ├── InputArea.md  #     Zone: 输入区
    │   ├── ChatFlow.md   #     Zone: 消息流
    │   └── ChatInputBar.md #   Zone: 反馈栏
    ├── batch/            #   批量 Tab
    │   ├── _tab.md
    │   └── BatchPanel.md
    └── ...
```

### 核心概念：Zone

Zone 是 ViewSpec 的核心结构单元，对应界面上一个独立的交互分区。每个 Zone 拥有自己的元素、状态变量、事件处理器。Zone 之间通过消息事件通信（`emit` + 路由表），禁止直接操作其他 Zone 内部状态。

### 布局模式

每个 Tab 声明布局模式：`form + result`（表单提交→结果展示）、`chat-flow`（输入 + 消息流 + 反馈栏）、`sidebar + detail`（列表 + 详情）等。布局模式决定 Zone 的组合方式。

### 与 metainfo 的关系

```
metainfo.md          ← 数据契约（输入/输出字段类型）
    ↓ 推导
ViewSpec/            ← UI 规范目录（渲染/交互/主题）
    ↓ 生成
View/ files          ← 可执行代码
```

ViewSpec 引用 metainfo 的输入/输出契约字段，但增加渲染关注点（Widget 类型、阈值、颜色规则、聚合方式）。metainfo 只说"reliability_score 是 int"，ViewSpec 说"用 gauge-circle 渲染，>=70 绿色，>=40 橙色，<40 红色"。

### 文件路由表

当 View 使用 `hop_view` 共享库时，运行时代码分散在共享模板（`base.html`、`chatflow.css`、`run_result.html`）、共享逻辑（`transport.py`）和任务级文件（`config.py`、`app.py`）中。`index.md` 中推荐包含**文件路由表**——「改什么 → 改哪个文件」的映射——防止误改快照文件 `index.html` 或其他非目标文件。格式规范见 `Terms/ViewSpec格式规范.md` §1.7。

### 生成流水线

当 `View/ViewSpec/index.md` 存在时，`/code2view` 优先读取 ViewSpec 目录作为 UI 定制规范；不存在时回退到从 metainfo 直接推断（兼容旧行为）。

---

## 十、与 `/code2view` 命令的衔接

### 生成文件（使用 hop_view 共享库）

`/code2view` 命令生成 3 个文件（原 observer.py、datastore.py、service.py 由共享库替代）：

| 文件 | 性质 | 生成策略 |
|------|------|----------|
| `config.py` | ViewConfig 声明 | **半定制**：从 metainfo 输入/输出契约生成 ViewConfig + FieldAggregation |
| `app.py` | Transport（pywebview） | **模板化**：薄启动器，~30 行 |
| `web.py` | Transport（FastAPI） | **模板化**：薄启动器，~30 行 |
| `index.html` | Frontend | **定制化**：输入字段、结果渲染、统计指标按 metainfo 输入/输出契约生成 |

> 注：旧版 `/code2view` 生成 6 个文件（含 observer.py、datastore.py、service.py）。使用 `hop_view` 共享库后，这些通用模块由 `BaseDataStore`、`BaseService`、`HopletObserver` 替代。

### 模板化 vs 定制化

**模板化文件**（`observer.py`）：所有 Hoplet 任务共用相同代码，`/code2view` 直接拷贝模板。

**半定制文件**（`service.py`、`datastore.py`）：结构固定，但部分方法需要按任务定制：
- `service.py` 的 `run_task` 方法需要 import 对应的 `Hop.py` 并调用其主函数
- `datastore.py` 的 `get_stats` 方法按输出契约字段类型生成不同的聚合逻辑

**定制化文件**（`index.html`、`app.py`、`web.py`）：
- `index.html` 的输入表单、结果渲染、统计卡片根据 metainfo 输入/输出契约生成
- `app.py` 的 `run_task` 参数列表按输入契约生成
- `web.py` 的 Pydantic 请求模型按输入契约生成

### 统计逻辑定制规则

`datastore.py` 的 `get_stats` 方法按 ViewConfig 的 `output_fields` 配置（`FieldAggregation`）驱动 ibis 表达式生成：

| agg_type | ibis 表达式 | 示例 |
|----------|------------|------|
| `mean` | `t[field].try_cast("float64").mean()` | `credit_score` → `avg_credit_score` |
| `rate` | `t[field].try_cast("bool").fill_null(False).sum() / total` | `hallucination_detected` → `hallucination_detected_rate` |
| `distribution` | DuckDB SQL: `UNNEST(from_json(field, ...)) GROUP BY sub_field` | `errors[].severity` → `errors_distribution` |
| `non_null_rate` | `t[field].notnull().sum() / total` | `summary` → `summary_non_null_rate` |

---

## 十一、依赖与启动

### 依赖

所有依赖已在 `pyproject.toml` 中声明：

| 包 | 用途 | `pyproject.toml` 中的声明 |
|----|------|--------------------------|
| `pywebview>=6.1` | 本地桌面 UI | 已有 |
| `ibis-framework[duckdb]>=10.0.0` | 查询加速引擎（ibis 表达式 API + DuckDB 后端） | 已有 |
| `pydantic>=2.12.5` | FastAPI 请求/响应模型 | 已有 |

FastAPI 及其 ASGI 服务器需要额外安装：

```bash
uv add fastapi uvicorn[standard]
```

### 启动命令

所有启动器支持从任意工作目录执行（路径基于 `__file__` 解析，见「二、路径解析约束」）：

```bash
# pywebview 桌面模式（本地单人）— 从任意目录
uv run --no-sync python Tasks/<TaskName>/View/app.py

# pywebview 调试模式（启用 DevTools）
HOP_VIEW_DEBUG=1 uv run --no-sync python Tasks/<TaskName>/View/app.py

# FastAPI Web Service（多人在线）— 从任意目录
uv run --no-sync uvicorn web:app --host 0.0.0.0 --port 8000 --app-dir Tasks/<TaskName>/View

# FastAPI 开发模式（自动重载）
uv run --no-sync uvicorn web:app --reload --port 8000 --app-dir Tasks/<TaskName>/View
```

FastAPI 启动后，访问 `http://localhost:8000` 查看 UI，访问 `http://localhost:8000/docs` 查看自动生成的 API 文档。

---

## 十二、hop_view 共享库

### 概述

`hoplogic/hop_view/` 是 View 层的共享库，提取了各任务 View 代码中 ~80% 的通用逻辑。每个任务只需声明 `ViewConfig` + 薄启动器即可复用全部功能。

详细 API 参考：`hoplogic/docs/hop_view.md`
配置规范：`Terms/HopView共享库规范.md`

### 共享库包结构

```
hoplogic/hop_view/
├── __init__.py            # 包初始化，__version__="0.3.0"，__all__ 导出
├── config_schema.py       # ViewConfig + FieldAggregation dataclass 定义
├── observer.py            # HopletObserver + _RunTracer（结构化执行日志）
├── file_utils.py          # parse_file() 通用文件解析
├── hop_loader.py          # ensure_hop() 动态加载 + resolve_task_paths()
├── datastore.py           # BaseDataStore — 配置驱动的 DuckDB 查询
├── service.py             # BaseService — 配置驱动的业务逻辑
├── transport.py           # create_fastapi_app() / create_pywebview_app() 工厂
├── renderer.py            # Jinja2 渲染器 — HTML 片段生成（render_*_fragment）
├── templates/             # Jinja2 模板目录（Tab 片段、结果卡片、统计面板等）
├── batch_runner.py        # CLI 批量测试运行器
└── test/                  # 测试套件（172 个用例）
```

### 迁移后的任务目录结构

使用共享库后，每个任务的 `View/` 目录大幅简化：

```
Tasks/<TaskName>/View/
├── ViewSpec/          # 不变
├── config.py          # ~35 行 — ViewConfig 声明
├── app.py             # ~30 行 — 薄启动器
├── web.py             # ~30 行 — 薄启动器
└── index.html         # 保持不变
```

旧版 6 个 Python 文件（observer.py、datastore.py、service.py、app.py、web.py + test/）总计 ~3991 行，迁移后仅需 ~100 行任务特定代码 + index.html。

### 使用方式

**config.py**:
```python
from hop_view.config_schema import ViewConfig, FieldAggregation
VIEW_CONFIG = ViewConfig(task_name="Verify", hop_func_name="verify_hop", ...)
```

**app.py** (薄启动器，支持任意目录启动):
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
service = BaseService(VIEW_CONFIG, hoplet_dir, testcases_dir, observer=...)
create_pywebview_app(VIEW_CONFIG, service, VIEW_DIR)
```

**web.py** (薄启动器，支持任意目录启动):
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
service = BaseService(VIEW_CONFIG, hoplet_dir, testcases_dir, observer=...)
app = create_fastapi_app(VIEW_CONFIG, service, VIEW_DIR)
```

### 与 per-task 代码的关系

| 模块 | 旧版（per-task 生成） | 新版（共享库） |
|------|---------------------|--------------|
| observer.py | 每任务一份（110 行） | `hop_view.observer`（共享） |
| datastore.py | 每任务一份（468 行） | `hop_view.datastore.BaseDataStore`（配置驱动） |
| service.py | 每任务一份（289 行） | `hop_view.service.BaseService`（配置驱动） |
| web.py | 每任务一份（161 行） | `hop_view.transport.create_fastapi_app()`（工厂） |
| app.py | 每任务一份（117 行） | `hop_view.transport.create_pywebview_app()`（工厂） |
| test/ | 每任务一份（~2000 行） | `hop_view/test/`（172 个用例，共享） |

---

## 十三、测试

### 测试范围

`/code2view` 生成的测试套件覆盖 4 个 Python 后端模块，不测 `app.py`（pywebview 需 GUI 环境）和 `index.html`（前端 JS）。

| 测试文件 | 被测模块 | 性质 | 约测试数 |
|----------|----------|------|----------|
| `test_observer.py` | `observer.py` | 模板化 | ~15 |
| `test_datastore.py` | `datastore.py` | 半定制 | ~20 |
| `test_service.py` | `service.py` | 半定制 | ~20 |
| `test_web.py` | `web.py` | 定制 | ~15 |

### pytest asyncio_mode = auto 约束

项目 `asyncio_mode = auto`（`hoplogic/pytest.ini`），async 测试函数自动识别，无需 `@pytest.mark.asyncio`。async fixture 推荐用 `@pytest_asyncio.fixture` 装饰（而非 `@pytest.fixture`）。

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client — 必须用 @pytest_asyncio.fixture"""
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
```

### 测试分层

```
纯逻辑     test_observer.py     HopletObserver、_RunTracer（文件 I/O + 线程安全）
纯逻辑     test_datastore.py    HopletDataStore（DuckDB 查询 + 聚合统计）
Mock I/O   test_service.py      HopletService（mock _ensure_hop + Hop 模块）
Mock HTTP  test_web.py          FastAPI 端点（httpx.AsyncClient + ASGITransport）
```

### 共享 Fixtures（conftest.py）

| Fixture | 作用 |
|---------|------|
| `sample_audit_records()` | 返回符合输出契约的 dict 列表 |
| `tmp_testcases(tmp_path)` | 创建临时 TestCases 目录 + sample JSONL |
| `tmp_observer_log(tmp_path)` | 创建临时 observer.jsonl（run_start/step/run_end） |

Fixtures 中的 sample 数据按任务输出契约定制。

### Mock 策略

| 被 Mock 对象 | Mock 方式 | 用途 |
|-------------|-----------|------|
| `_hop_module` / `_hop_load_error` | 直接设置模块级变量 | 避免真实 import Hop.py |
| `hop.verify_hop` | `AsyncMock(return_value=...)` | 模拟 Hop 主函数 |
| `hop.hop_proc.session()` | `AsyncMock` 上下文管理器 | 模拟 HopSession |
| `hop.GLOBAL_STATS` | `MagicMock()` | 模拟全局统计 |
| `app.state.service` | 注入 `MagicMock` | Web 端点测试不依赖真实 Service |

每个测试通过 `autouse` fixture 在测试前重置 `_hop_module` 和 `_hop_load_error`。

### 运行命令

```bash
# 运行全部测试
cd Tasks/<TaskName>/View && uv run --no-sync pytest test/ -v

# 运行单个测试文件
cd Tasks/<TaskName>/View && uv run --no-sync pytest test/test_observer.py -v

# 覆盖率报告
cd Tasks/<TaskName>/View && uv run --no-sync pytest test/ -v --cov=. --cov-report=term-missing
```

### 覆盖率要求

4 个被测模块（observer.py、datastore.py、service.py、web.py）各 **>= 99%**。`app.py` 和 `index.html` 排除在覆盖率统计之外。

# HOP核心算子

本文是一份面向Claude Code（或任何AI编程助手）的HOP核心算子说明。这份说明旨在让AI理解HOP算子如何调用，以及框架在**错误处理**、**并发安全**和**状态管理**方面的规范约定。

> 引擎源码：`hoplogic/hop_engine/`
> API 详细文档：`hoplogic/docs/hop.md`（入口）

---

## 1. 常量与枚举

> 源码：`hop_engine/config/constants.py`

### `JsonValue`

类型别名，定义了 HOP 系统中 JSON 值的合法类型：`None | bool | int | float | str | list[Any] | dict[str, Any] | Literal["True", "False", "Uncertain"]`。

### `class HopStatus(Enum)`

HOP 算子执行结果的状态枚举，是整个核验体系的核心状态机。

| 枚举值 | 含义 | 可 feedback 续解 |
|--------|------|-----------------|
| `OK` | 核验成功，结论正确 | — |
| `LACK_OF_INFO` | LLM 推理层信息不足，补充上下文后可能改善 | 是 |
| `UNCERTAIN` | 无法确定结论（非信息缺失原因） | 是 |
| `FAIL` | 失败（传输失败/核验失败/工具执行失败/能力不足） | 否 |

> **FAIL vs LACK_OF_INFO 边界**：前置管线失败（RAG 检索无结果、数据源不可达等）应返回 `FAIL`——`add_feedback` 只影响 LLM 对话历史，无法修复管线层问题。`LACK_OF_INFO` 仅用于 LLM 算子自报告的推理层信息缺失。

---

## 2. 三层架构

```
用户代码 (Hop.py / examples)
    |
HopSession  -- 执行边界：对话历史、HopState、ExecutionStats、持久化(StateStore)
    |
HopProc     -- 算子抽象：hop_get/judge/tool_use 的语义、重试、核验（无状态、可共享）
    |
LLM         -- 传输层：连接复用、引擎适配、结构化输出（无状态、可共享）
```

- **HopSession**：每次业务执行创建一个 session，持有对话历史、`HopState`（执行状态）和 `ExecutionStats`（统计）。
- **HopProc**：核心处理器，定义三个算子。无状态，可被多个 session 共享（同一事件循环内）。
- **LLM**：传输层，封装 `openai.AsyncClient`。连接复用，绑定到创建时的事件循环。

---

## 3. 核心算子

> 源码：`hop_engine/core/hop_processor.py`

三个算子均为 **async 协程**方法，统一返回 `Tuple[HopStatus, JsonValue]`。所有算子要求 `session` 参数（`HopSession` 实例），推荐通过 `HopSession` 代理调用。

### `hop_get` — 信息获取

```python
await session.hop_get(
    task: str,                           # 任务描述（必填）
    context: str = "",                   # 上下文信息
    return_format: JsonValue = None,     # 返回值格式（dict/tuple/Pydantic/基础类型）
    verifier = reverse_verify,           # 核验器，None 跳过核验
    explanation_description: str = "",   # 自定义 explanation 描述
    include_history: bool = True,        # 是否包含前序算子的对话历史
) -> Tuple[HopStatus, JsonValue]
```

- **用途**：从上下文中抽取知识、提取结构化信息
- **默认核验**：逆向核验（`reverse_verify`）
- **装饰器**：`@auto_record_status` — 自动记录统计

### `hop_judge` — 真伪研判

```python
await session.hop_judge(
    task: str,                           # 判断条件描述（必填）
    context: str = "",                   # 上下文信息
    return_format: JsonValue = None,     # 默认 Literal["True","False","Uncertain"]
    verifier = reverse_verify,           # 核验器
    explanation_description: str = "",   # 自定义 explanation 描述
    include_history: bool = True,        # 是否包含前序算子的对话历史
) -> Tuple[HopStatus, JsonValue]
```

- **用途**：对知识进行真伪判断
- **默认核验**：逆向核验（`reverse_verify`）
- **默认 return_format**：`Literal["True", "False", "Uncertain"]`

### `hop_tool_use` — 工具调用

```python
await session.hop_tool_use(
    task: str,                           # 工具调用需求（必填）
    context: str = "",                   # 上下文信息
    tool_domain: str = "all",            # 工具域（限定可用工具集合）
    verifier = tool_use_verifier,        # 工具核验器
    include_history: bool = True,        # 是否包含前序算子的对话历史
) -> Tuple[HopStatus, JsonValue]
```

- **用途**：让 LLM 选择并执行注册工具
- **默认核验**：工具核验（`tool_use_verifier`）
- **流程**：LLM 选择工具 → 核验工具选取合法性 → 实际执行工具 → 返回工具结果
- **工具域**：`"all"`（全部）、`"security"`（安全工具）、`"rag"`（RAG 检索）、`"mcp"`（MCP 外部工具，通过 `init_mcp_tools()` 动态注册）

---

## 4. HopSession — 执行会话

> 源码：`hop_engine/utils/hop_session.py`

### 创建与使用

```python
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.state_store import JsonlStateStore

hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,        # 核验失败最大重试次数，必须 >= 1
)

store = JsonlStateStore("output.jsonl")

async with hop_proc.session(state_store=store) as s:
    status, result = await s.hop_get(task="提取摘要", context=text)
    if status != HopStatus.OK:
        # 处理失败
        ...
    status, verdict = await s.hop_judge(task="判断正确性", context=result)
```

### session 管理的资源

| 资源 | 说明 |
|------|------|
| `run_history` | 执行侧 LLM 对话历史（跨算子保留 task+result 摘要） |
| `state` (`HopState`) | 执行状态：重试计数、执行路径、步骤记录 |
| `stats` (`ExecutionStats`) | 算子/函数级统计 |
| `state_store` | 可选的持久化后端 |
| `run_id` | 执行批次标识（默认自动生成 UUID） |

### 跨算子对话历史与折叠机制

默认情况下，同一 session 内每个算子执行完毕后，完整的执行过程（prompt、重试反馈、assistant 回复）被折叠为简洁的 **task+result 摘要**，保留在 `run_history` 中。后续算子的 LLM 可以看到前序算子的摘要。

```
operator A 执行（含完整 prompt + retries）
↓ 执行完毕后折叠为 task+result 摘要
operator B 执行时能看到 A 的 task+result
↓ 执行完毕后折叠
operator C 执行时能看到 A、B 的 task+result
```

**`include_history` 参数**：

| 值 | 行为 |
|------|------|
| `True`（默认） | LLM 看到前序算子的 task+result 摘要 + 本次完整 prompt |
| `False` | LLM 仅看到本算子自身的 messages，但 task+result 仍计入历史供后续算子使用 |

### 核验失败重试反馈

核验失败时，反馈信息以 user 消息追加到对话历史中，格式为：`"\n核验反馈信息：{verifier_reason} 请重新再执行一下哈\n"`。LLM 在重试时可以参考核验反馈和之前的 assistant 回答来修正输出。重试结束后，所有中间轮次（包括反馈）被折叠，只保留最终 task+result 摘要。

### 上下文管理器语义

- **`__aenter__`**：重置 state 和 stats，记录开始时间
- **`__aexit__`**：将 session 统计合并到 `GLOBAL_STATS`；有 `state_store` 时持久化函数级摘要

---

## 5. 异常与错误处理规范

> 详细文档：`docs/hop_error_handling.md`

### 核心原则：纯返回值模式

**所有算子始终返回 `(HopStatus, result)`，不论成功或失败。** 用户代码通过检查 `status` 处理失败，不需要 `try/except`。

```python
# 正确：检查 status
status, result = await s.hop_get(task="...", context="...")
if status != HopStatus.OK:
    logger.warning(f"失败: {status}, {result}")
    return fallback

# 错误：不要 try/except 算子调用
try:
    status, result = await s.hop_get(...)  # 不会抛异常
except ValueError:  # 不会触发
    ...
```

唯一会抛出的异常是 `session=None` 时的 `ValueError`，这是编程错误而非业务失败。

### 异常分层

```
用户代码                          ← 检查 status，不需要 try/except
    |
@auto_record_status 装饰器       ← 所有 status 直接返回；异常转为 (FAIL, ...)
    |
HopProc 算子                     ← 返回 (HopStatus, result)
    |
_execute_task                    ← 重试循环，消费 HopStatus
    |
_execute_core                    ← 底层异常包装为 RuntimeError
    |
LLM.query_llm                   ← 内部重试+退避，返回 (bool, response)，不抛异常
    |
openai.AsyncClient               ← 原始异常（网络、限流、超时等）
```

### 四类 FAIL

FAIL 状态有四种来源，均返回 `(HopStatus.FAIL, result)`：

| 失败类型 | `error_type` | result 特征 | 含义 |
|----------|-------------|-------------|------|
| 传输失败 | 非空（如 `"RuntimeError"`） | `[RuntimeError] ...` | LLM 不可用 |
| 核验失败 | `None` | 核验器返回的 reason | LLM 可用但结果不合格 |
| 工具执行失败 | `None` | `"工具调用失败: ..."` / `"工具执行失败: ..."` | `hop_tool_use` 工具调用出错 |
| 能力不足 | N/A（用户代码直接返回） | 业务自定义（如 `"知识库检索失败"`) | 前置管线失败，未进入 LLM 算子 |

```python
status, result = await s.hop_get(task="...", context="...")
if status == HopStatus.FAIL:
    last = s.state.step_records[-1]
    if last.error_type:
        logger.error(f"传输失败: {last.error_type}")
    else:
        logger.warning(f"核验失败: {result}")
elif status == HopStatus.UNCERTAIN:
    # 降级使用不确定的结果
    process_with_warning(result)
elif status == HopStatus.LACK_OF_INFO:
    logger.info(f"信息不足: {result}")
```

### 两层重试机制

```
算子重试（hop_retry, 默认 3）    ← 核验失败触发，追加反馈到对话历史
  └── 每轮内部：LLM 重试（max_retry_count）  ← 传输异常触发，指数退避
```

- **核验失败**（`FAIL`/`UNCERTAIN` 等 `HopStatus`）→ 算子层重试，LLM 参考核验反馈修正
- **反馈格式**：`"\n核验反馈信息：{verifier_reason} 请重新再执行一下哈\n"`
- **重试时 LLM 可见**：前序算子摘要（如 `include_history=True`）+ 本轮完整对话（prompt、之前的 assistant 回答、核验反馈）
- **折叠**：重试结束后，所有中间轮次被折叠为 task+result 摘要，后续算子只看到最终结果
- **传输失败**（LLM 全部重试耗尽 → `RuntimeError`）→ 算子层**不重试**，直接传播到装饰器，返回 `(FAIL, ...)`
- **最后一轮**：`UNCERTAIN`/`LACK_OF_INFO` 保留原状态返回，不降级为 `FAIL`

### 持久化与统计的错误处理

`state_store.save_step()` 和 `stats.record_operator()` 都被 `try/except` 保护。持久化和统计是可选的观测性功能，内部错误不影响 `(status, result)` 的返回。

---

## 6. 并发安全规范

> 详细文档：`docs/hop_concurrency.md`

### 推荐模型：单线程 asyncio 并发

所有 `HopSession` 在同一事件循环内运行，通过 `asyncio.gather` 实现并发。此模型下无需考虑线程安全。

```python
async def process_one(hop_proc, item):
    async with hop_proc.session() as s:
        status, result = await s.hop_get(task=item["task"], context=item["ctx"])
        return result

results = await asyncio.gather(*[process_one(hop_proc, item) for item in items])
```

### 所有权边界

| 组件 | 所有权 | 可跨线程共享 | 线程安全机制 |
|------|--------|-------------|-------------|
| `HopProc` | per-thread | 不可 | N/A |
| `LLM` | per-HopProc | 不可 | N/A（绑定事件循环） |
| `HopSession` | per-session | 不可 | N/A |
| `HopState` | per-session | 不可 | N/A |
| `ExecutionStats`（session 级） | per-session | 不可 | `asyncio.Lock` |
| `GLOBAL_STATS` | 模块单例 | **可** | `threading.Lock`（仅 `merge_from`） |
| `JsonlStateStore` | 可共享 | **可** | `threading.Lock`（`_append`） |

### 禁止的使用方式

- **跨线程共享 HopProc**：`LLM` 内部 `openai.AsyncClient` 绑定到创建时的事件循环，跨线程使用导致 "attached to a different loop" 错误
- **跨线程共享 HopSession**：`HopState` 的 `list.append()` 无锁保护，多线程下存在数据竞争
- **跨线程直接向 GLOBAL_STATS 写入**：`record_operator`/`record_function` 使用 `asyncio.Lock`，仅同一事件循环内安全

### 多线程正确用法

每个线程创建独立的 `HopProc`，可共享 `JsonlStateStore`。session 退出时通过 `GLOBAL_STATS.merge_from()` 自动合并统计（`threading.Lock` 保护）。

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

### 核验器内部并发

`forward_cross_verify` 和 `tool_use_verifier` 通过 `asyncio.gather` 并发调用 3 次 LLM。内部使用 `_query_llm_once` 辅助函数，对 params 进行防御性浅拷贝以隔离并发调用。

---

## 7. 核验器

> 源码：`hop_engine/validators/result_validators.py`
> 详细文档：`docs/hop_validators.md`

所有核验函数均为 async 协程，统一签名：

```python
async def verifier(
    task: str,
    context: str,
    model_result: JsonValue,
    ctx: VerifyContext,
) -> HopVerifyResult
```

### 内置核验器

| 核验器 | 用途 | 默认用于 |
|--------|------|----------|
| `reverse_verify` | 逆向核验（独立 LLM 反向验证结论与上下文一致性） | `hop_get`, `hop_judge` |
| `forward_cross_verify` | 正向交叉核验（并发 3 次 LLM，比对结果一致性） | — |
| `tool_use_verifier` | 工具核验（合法性 + 参数 + 交叉核验） | `hop_tool_use` |
| `format_verifier` | 格式核验（检测序列化残留，纯本地，不调 LLM） | 所有 LLM 步骤（始终作为前置检查） |

### 自定义核验器

```python
async def my_verifier(task, context, model_result, ctx) -> HopVerifyResult:
    if is_valid(model_result):
        return HopVerifyResult(HopStatus.OK, "验证通过")
    return HopVerifyResult(HopStatus.FAIL, "验证失败原因")

# 使用
status, result = await s.hop_get(task=..., verifier=my_verifier)

# 跳过语义核验（format_verifier 仍自动生效）
status, result = await s.hop_get(task=..., verifier=None)
```

核验器内部自行处理错误，不向上抛异常，而是返回 `HopVerifyResult(FAIL, reason)`。

> **格式核验始终先行**：`format_verifier` 作为所有核验的前置检查自动运行，无论是否指定了语义核验器。执行顺序：`format_verifier` -> 语义核验器（如有）。格式检查失败直接触发重试，不调用语义核验器。`verifier=None` 表示仅运行格式核验。`format_verifier` 递归扫描整棵输出树，检测字符串化的 dict/list 残留。不调用 LLM，零额外开销。

---

## 8. 装饰器

> 源码：`hop_engine/utils/status_recorder.py`
> 详细文档：`docs/hop_monitoring.md`

### `@auto_record_status`

包裹在三个算子上，自动执行：

1. 重置重试计数，设置当前步骤号和算子名
2. 计时并 `await` 被装饰函数
3. 记录执行路径（`state.add_execution_step`）
4. 创建 `HopStepRecord` 追加到 `state.step_records`
5. 如有 `state_store`，持久化到外部存储
6. 调用 `stats.record_operator` 记录统计（try/except 保护）
7. 返回 `(status, result)` — 所有 status 都直接返回

异常路径：被装饰函数抛异常时，执行与正常路径相同的完整记录流程，然后返回 `(HopStatus.FAIL, "[ErrorType] message")`。

### `HopStepRecord`

单个算子步骤的结构化记录：

| 字段 | 类型 | 说明 |
|------|------|------|
| `step` | `int` | 步骤序号 |
| `op` | `str` | 算子名 |
| `task` | `str` | 任务描述 |
| `result_truncated` | `str` | 截断到 100 字符的结果 |
| `result_full` | `str` | 完整结果 |
| `duration` | `float` | 执行耗时（秒） |
| `status` | `Optional[HopStatus]` | 执行状态 |
| `retry_count` | `int` | 重试次数 |
| `error_type` | `Optional[str]` | 传输失败时为异常类名，核验失败和成功时为 `None` |

---

## 9. 编写 Hop.py 的规范约定

### 标准模板

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
        # 步骤 1：信息获取
        # hop_get 执行后，task+result 摘要自动保留在 session 历史中
        status, result = await s.hop_get(
            task="提取关键信息",
            context=input_data["text"],
        )
        if status != HopStatus.OK:
            s.hop_exit("EXIT_ERR", "信息获取失败")
            return {"error": f"{status}: {result}"}

        # 步骤 2：研判
        # hop_judge 的 LLM 能看到步骤 1 的 task+result 摘要
        status, verdict = await s.hop_judge(
            task="判断是否符合条件",
            context=result,
        )
        if status != HopStatus.OK:
            s.hop_exit("EXIT_UNCERTAIN", "研判不确定")
            return {"result": "uncertain", "detail": result}

        # 步骤 3：独立判断（不带历史）
        # include_history=False: LLM 不看到前序历史，但结果仍保留
        status, extra = await s.hop_get(
            task="独立分析",
            context=input_data["extra"],
            include_history=False,
        )

        s.hop_exit("EXIT_OK", "正常完成")
        return {"result": verdict}

asyncio.run(process({"text": "..."}))
```

### 规范要点

1. **始终检查 status**：每个算子调用后检查 `status != HopStatus.OK`，决定是否继续、降级或退出
2. **不要 try/except 算子调用**：算子不抛异常（除 `session=None`），用 status 检查代替
3. **使用 `session.hop_exit()` 记录退出点**：在每个 `return` 前标记退出分支，方便调试和回溯
4. **入口用 `asyncio.run()`**：所有 LLM I/O 必须 async/await
5. **资源释放**：长期运行时用 `await hop_proc.aclose()` 释放 LLM 连接
6. **并发任务用 `asyncio.gather`**：同一事件循环内的多个 session 可安全并发
7. **不跨线程共享 HopProc 或 HopSession**

### 细粒度状态处理

```python
status, result = await s.hop_get(task="...", context="...")
if status == HopStatus.OK:
    process(result)
elif status == HopStatus.UNCERTAIN:
    process_with_warning(result)       # 降级使用不确定的结果
elif status == HopStatus.LACK_OF_INFO:
    logger.info(f"信息不足: {result}")  # 补充信息后重试
elif status == HopStatus.FAIL:
    last = s.state.step_records[-1]
    if last.error_type:
        logger.error(f"传输失败: {last.error_type}")
    else:
        logger.warning(f"核验失败: {result}")
```

---

## 10. 相关文档

| 文档 | 内容 |
|------|------|
| `hoplogic/docs/hop.md` | 三大算子 API 详细参考（入口） |
| `hoplogic/docs/hop_session.md` | HopSession 会话管理 |
| `hoplogic/docs/hop_processor.md` | HopProc 内部方法 |
| `hoplogic/docs/hop_validators.md` | 核验器详解 |
| `hoplogic/docs/hop_llm.md` | LLM 调用层 |
| `hoplogic/docs/hop_monitoring.md` | 统计与监控 |
| `hoplogic/docs/hop_state_store.md` | 执行状态持久化 |
| `hoplogic/docs/hop_error_handling.md` | 异常与错误处理规范 |
| `hoplogic/docs/hop_concurrency.md` | 多线程并发指南 |
| `hoplogic/docs/hop_testing.md` | 单元测试说明 |

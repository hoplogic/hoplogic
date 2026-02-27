# HOP vs Burr：两种 LLM 应用框架的设计路线

## 引言

[Apache Burr](https://burr.apache.org/) 是一个通用的状态机应用框架，用于构建决策型应用（Agent、对话系统、模拟等）。HOP（High-Order Program）是面向大模型的可信智能体编程范式——可控、可靠、可持续进化，通过结构化程序骨架约束 LLM 智能、核验闭环消除幻觉、渐进固化实现持续进化。两者都面向 LLM 应用开发，但从根本上回答了不同的问题：

- **Burr**：应用的状态在哪？下一步做什么？
- **HOP**：LLM 说的对不对？怎么保证对？

本文通过系统对比，阐述 HOP 的核心设计理念。

---

## 1. HOP 的三个核心理念

### 1.1 Python 就是最好的控制流

HOP 的第一个设计选择是**不引入控制流抽象**。

Burr 要求开发者将业务逻辑建模为显式状态机——定义 Action 节点、声明 Transition 条件、配置 Guard 表达式。框架接管控制流的调度：

```python
# Burr：框架驱动控制流
builder = ApplicationBuilder()
builder.with_actions(
    extract=extract_action,
    judge=judge_action,
    supplement=supplement_action,
)
builder.with_transitions(
    ("extract", "judge", default),
    ("judge", "supplement", when(status="UNCERTAIN")),
    ("judge", "done", when(status="OK")),
    ("supplement", "judge", default),
)
app = builder.build()
app.run(...)
```

HOP 认为 Python 本身的 `if`/`for`/`while`/`await`/`try` 就是最好的控制流。所有业务逻辑用标准 Python 表达，框架只管 LLM 调用的可靠性：

```python
# HOP：Python 就是控制流
async with hop_proc.session() as s:
    status, facts = await s.hop_get(task="提取事实", context=doc)
    if status != HopStatus.OK:
        return {"error": "提取失败"}

    for fact in facts:
        status, verdict = await s.hop_judge(task="核实", context=fact)
        if status == HopStatus.UNCERTAIN:
            status, verdict = await s.hop_get(task="补充查证", context=fact)
        results.append({"fact": fact, "valid": verdict})
```

这不是"简化"——这是一个有意识的架构决策。原因有三：

**表达力**。任何 `if/else` 嵌套、循环中的 `break`/`continue`、异常处理、提前返回，都是 Python 原生语法，不需要适配到框架的转移条件 DSL。状态机 DSL 的表达力永远是 Python 的子集。

**可调试性**。断点直接打在业务逻辑上，调用栈就是执行流程。不存在"图定义"和"实际执行"分离的问题——代码就是流程，流程就是代码。

**LLM 可生成性**。HOP 程序（Hop.py）本身就是大模型通过 `/spec2code` 自动生成的产物。Python 是大模型训练数据中占比最高的语言，生成和修改 Python 控制流是 LLM 最强的能力。如果控制流是框架特有的 DSL，大模型需要额外学习 API 语法、理解图拓扑与运行时行为的映射关系，生成质量会显著下降。

### 1.2 框架管可靠性，不管业务逻辑

HOP 的第二个设计选择是将**框架能力聚焦在 LLM 可靠性**上。

Burr 作为通用状态机框架，提供的是编排能力：状态转移、持久化、可视化、hooks。但它不关心 LLM 的输出是否正确——这完全是用户 Action 的责任。如果要在 Burr 中实现核验，每个 Action 都需要重复编写：

```python
# Burr 中实现核验：每个 Action 都要自己写
@action(reads=["context"], writes=["result"])
def extract_with_verify(state):
    for attempt in range(3):
        result = call_llm(state["context"])
        # 手写核验逻辑
        verify_result = call_another_llm(f"验证：{result}")
        parsed = json.loads(verify_result)
        if parsed["status"] == "OK":
            return state.update(result=result)
        # 手写重试反馈
        feedback = parsed["reason"]
    return state.update(result=None, error="全部重试失败")
```

HOP 将核验闭环内化为框架能力。一次 `hop_get` 调用自动完成：

1. Prompt 构建（含安全令牌过滤）
2. LLM 执行（含传输层重试 + 指数退避）
3. 结构化输出解析
4. 核验（逆向核验 / 正向交叉核验 / 工具核验 / 场景核验）
5. 核验失败时将 reason 作为反馈注入对话历史，触发 LLM 重试
6. 4 种语义状态返回（OK / FAIL / UNCERTAIN / LACK_OF_INFO）
7. 全链路统计记录（success_rate、retry_count、execution_time）

用户代码只需要关心"做什么"，不需要关心"怎么确保对"：

```python
# HOP：一行调用 = 执行 + 核验 + 重试 + 统计
status, result = await s.hop_get(task="提取事实", context=doc)
```

### 1.3 HOP 程序是给大模型执行的

HOP 的完整名称是 High-Order Program——高阶程序。它不是普通的脚本，而是融合了精确程序逻辑、领域知识定义和多层核验机制的工程化资产。HOP 的定位是**大模型时代的 SOP（标准作业程序）的机器可执行版本**。

这意味着 HOP 程序的生命周期是：

```
领域专家编写 SOP → AI 转换为 HopSpec → AI 生成伪代码 → AI 生成 Hop.py → 引擎执行
```

整个流水线中，控制流由 AI 生成、由引擎执行、由 AI 迭代修改。Python 作为控制流语言，同时服务于三个角色：

- **领域专家**能通过伪代码审阅理解流程
- **AI 编程助手**能高质量地生成和修改代码
- **Python 运行时**直接执行，无需额外的图编译或解释层

Burr 的状态机模型在这个链路中会引入摩擦——SOP 到状态图的映射不直观，AI 生成图定义的可靠性低于生成 Python 函数，领域专家更难审阅声明式的转移条件。

---

## 2. 系统对比

### 2.1 设计哲学

| | HOP | Burr |
|--|-----|------|
| 核心问题 | LLM 输出的可靠性 | 应用的状态编排 |
| 控制流 | Python 原生 | 框架声明式状态机 |
| 框架职责 | 核验闭环 + 可靠性统计 | 状态转移 + 持久化 + 可视化 |
| 目标用户 | LLM 任务开发者（含 AI 代码生成） | 通用应用开发者 |

### 2.2 核心能力

| 能力 | HOP | Burr |
|------|-----|------|
| LLM 核验闭环 | 内置 5 类核验器 | 无 |
| 核验驱动重试（带反馈） | 内置 | 无 |
| 语义状态（OK/FAIL/UNCERTAIN/LACK_OF_INFO） | 内置 | 无 |
| 跨算子对话历史（checkpoint+finally 折叠） | 内置 | 无（用户自管） |
| 可靠性统计（success_rate, retry, timing） | 内置 | 无 |
| 任意节点暂停/恢复 | 不支持 | 支持 |
| 可视化追踪 UI | 无 | 内置 Web UI |
| 非 LLM 场景 | 不适用 | 适用 |

### 2.3 编程模型

| | HOP | Burr |
|--|-----|------|
| 代码风格 | 命令式 `await s.hop_get(...)` | 声明式 Action + Transition |
| 一个算子调用包含 | 执行+解析+核验+重试+统计 | 用户自定义（框架只调度） |
| 修改流程 | 改一行 Python | 改 Action + Transition + Guard |
| LLM 生成友好度 | 高（标准 Python） | 低（需学框架 API） |
| IDE 支持 | 完整（跳转、类型检查、断点） | 图定义与运行时分离 |

### 2.4 架构分层

**HOP 三层架构**：

```
用户代码 (Hop.py)          ← Python 控制流，AI 可生成
    |
HopSession                 ← 会话边界：对话历史、状态、统计、持久化
    |
HopProc                    ← 算子：执行 + 核验 + 重试闭环（无状态，可共享）
    |
LLM                        ← 传输层：连接复用、引擎适配、结构化输出
```

**Burr 架构**：

```
用户代码                    ← 构建 Application
    |
Application                ← 状态机运行时：调度、持久化、hooks
    |
Action + Transition        ← 节点 + 转移条件（用户定义全部逻辑）
    |
State                      ← 不可变状态容器
```

关键区别：HOP 的中间层（HopProc）内置了核验闭环语义，用户调用算子即获得可靠性保证。Burr 的中间层（Application）只做调度，可靠性完全由 Action 自行负责。

### 2.5 并发模型

| | HOP | Burr |
|--|-----|------|
| 推荐方式 | 单线程 asyncio + gather 多 session | 单 app 单线程；多 app 多线程 |
| 并行模式 | 多 session 共享 HopProc | MapStates / MapActions（map-reduce） |
| 线程安全 | 锁保护共享资源（GLOBAL_STATS, StateStore） | 不可变 State 天然安全 |

### 2.6 异常处理

| | HOP | Burr |
|--|-----|------|
| 错误模型 | 纯返回值 `(HopStatus, result)`，永不向用户抛异常 | Python 标准异常传播 |
| 传输/核验失败区分 | `error_type` 字段区分 | 无内置区分 |
| 故障隔离 | 持久化/统计失败静默吞掉，不影响业务 | 取决于 hook 实现 |

### 2.7 持久化与可观测性

| | HOP | Burr |
|--|-----|------|
| 持久化模型 | StateStore Protocol + JSONL 追加写 | BaseStatePersister（PostgreSQL/Redis/SQLite 等） |
| 恢复粒度 | 算子级 step 记录 | 状态机节点级快照（可回退到任意历史节点） |
| 监控 | ExecutionStats API + JSONL | 内置 Web UI + OpenTelemetry |
| 状态可变性 | 可变 dataclass | 不可变（函数式更新） |

Burr 在持久化和可观测性方面更成熟。不可变 State 使得任意时间点的快照和回退成为可能，内置 UI 开箱即用。HOP 的持久化更轻量，面向批量处理场景。

---

## 3. 适用场景

| 场景 | 推荐 | 原因 |
|------|------|------|
| 专业领域高可靠 LLM 任务（金融/医疗/安全） | HOP | 内置核验闭环，框架级可靠性保证 |
| SOP 的机器可执行版本（AI 生成+迭代） | HOP | Python 控制流对 AI 生成最友好 |
| 批量 LLM 处理 + 可靠性统计 | HOP | auto_record_status + ExecutionStats 开箱即用 |
| 长生命周期交互式 Agent（暂停/恢复/回退） | Burr | 不可变状态 + 任意节点快照恢复 |
| 需要可视化流程审计/合规 | Burr | 内置 Web UI + 状态机天然可视化 |
| 非 LLM 决策型应用 | Burr | HOP 与 LLM 深度绑定 |
| 需要与 LangChain/LlamaIndex 集成 | Burr | 框架无关设计 |

---

## 4. 总结

HOP 和 Burr 代表了两种不同的 LLM 应用框架设计路线：

**Burr 路线**：通用编排。用声明式状态机管理应用的控制流和状态，提供持久化、可视化、hooks 等基础设施。LLM 只是 Action 内部的实现细节，框架对 LLM 输出的正确性不做任何保证。

**HOP 路线**：可信执行。把控制流留给 Python（和生成 Python 的 AI），框架精力集中在 LLM 场景的特有问题——核验闭环、重试反馈、可靠性统计。

两者并不互斥。理论上可以在 Burr 的 Action 内部调用 HOP 算子，获得状态机编排 + 核验可靠性的双重能力。但对 HOP 的目标场景——批量处理、实时研判、SOP 自动化——Python 控制流已经足够，状态机层不增加必要能力。

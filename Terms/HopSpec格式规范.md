# HopSpec 格式规范

## 设计动机

### 现状问题

当前常见的Spec是自由文本 markdown，存在两个问题：

1. **缺少结构化原子类型**。常见SPEC的`WHEN...THEN` 只描述任务间的线性转移，无法表达"对集合做遍历"（loop）、"条件分支后执行不同子流程"（branch）等模式。这些模式在实际逻辑中大量存在，但在 Spec 层面被隐藏在自由文本的"执行要点"中。

2. **Spec 到代码的映射含糊**。自由文本需要 AI 猜测循环结构和分支条件。原子化后，**结构**层面的映射变成确定性的。而 LLM 调用的语义细分（提取 vs 判断）可由 AI 从任务描述推断，无需在 Spec 层显式区分。

### 借鉴来源

Oracle [Open Agent Specification](https://github.com/oracle/agent-spec) 定义了一组原子化节点类型（AgentNode、ToolNode、MapNode、BranchingNode 等），用于声明式描述 Agent 工作流。HopSpec 借鉴其**组件类型学**思想，但保持 markdown 格式（不用 YAML），并加入 HOP 特有的核验语义。

### 理论根基

HopSpec 的树结构继承**结构化程序设计**范式（Böhm-Jacopini 1966 证明三种控制结构计算完备；Dijkstra 1968 论证 goto 使程序难以推理）。当执行者从可靠的 CPU 换成会幻觉的 LLM 时，对结构约束的需求只会更强——这是 HopSpec 选择嵌套树而非 DAG/有环图的根本原因，也是与 LangGraph、CrewAI、Dify 等图式 workflow 框架的核心分歧。详见 `Terms/HOP 2.0 技术定位.md` § HopSpec 设计哲学。

---

## 核心规则：结构化树，禁止跳转

HopSpec 的执行流程是一棵**结构化树**，遵循以下规则：

1. **顺序执行**：同级步骤从上到下依次执行
2. **禁止跳转**：任何步骤不得引用非子步骤的步骤编号（无 goto）
3. **作用域封闭**：`loop` 和 `branch` 只能包含自己的子步骤，子步骤执行完毕后自动回到父级继续下一步
4. **嵌套表达**：复杂控制流通过嵌套（步骤N → 步骤N.M → 步骤N.M.K）表达，不通过跳转

### 步骤标识：编号 + 语义名称

每个步骤的标题格式为 `#### 步骤N: step_name`，包含两部分：

| 部分 | 作用 | 示例 | 稳定性 |
|------|------|------|--------|
| **步骤N**（编号） | 阅读序号，从上到下连续编排 | 步骤1, 步骤2, 步骤2.1 | 插入/删除时重编号 |
| **step_name**（语义名称） | 身份标识，用于 Spec↔Code 对齐 | extract_atomic_facts | 不随重编号变化 |

**step_name 命名规则**：
- snake_case 英文，从任务描述派生
- 简洁（2-4 个单词），如 `extract_atomic_facts`、`check_grounding`、`merge_errors`
- 同一 Spec 内唯一
- 容器节点的子步骤 step_name 独立命名（不需要加父前缀）

**为什么需要两部分**：编号方便人阅读（"步骤3在步骤2后面"），但插入步骤后会重排。step_name 是稳定锚点，`/specdiff`、`/specsync`、`/code2spec` 通过它对齐 Spec 与 Code，不受重编号影响。

这与 Python 的块结构完全对应：

```
HopSpec 树                                    Python 代码
──────────                                    ──────────
步骤1: extract_info                           # 步骤1: extract_info — LLM
步骤2: process_items (loop)                    # 步骤2: process_items — loop
  步骤2.1: analyze_item                           # 步骤2.1: analyze_item — LLM
  步骤2.2: check_condition (branch)               # 步骤2.2: check_condition — branch
    步骤2.2.1: handle_special                          # 步骤2.2.1: handle_special — LLM
步骤3: summarize                              # 步骤3: summarize — LLM
```

`loop` 和 `branch` 完成后，控制流**自动**落到下一个同级步骤。不需要声明"结束后跳转到步骤X"。

---

## 原子步骤类型

每个 HopSpec 步骤必须声明一个原子类型。全部 7 种：

| 原子类型 | 含义 | 对应代码 | 节点性质 |
|----------|------|----------|----------|
| `LLM` | LLM 执行（带核验） | `await s.hop_get(...)` 或 `await s.hop_judge(...)` | 叶子 |
| `call` | 外部调用（工具/Hoplet/MCP） | `await s.hop_tool_use(...)` / 函数调用 / MCP | 叶子 |
| `loop` | 循环（for-each 遍历集合 / while 条件循环） | for: `for item in collection:` / while: `while condition:` | 容器 |
| `branch` | 条件分支 | `if condition:` | 容器 |
| `code` | 纯 Python 计算（无 LLM） | 普通 Python 代码 | 叶子 |
| `flow` | 流程控制（退出/继续/中断） | `return` / `continue` / `break` | 叶子 |
| `subtask` | 子任务块（static/dynamic/think）（历史别名 `seq_think` 保持兼容） | 预定义子步骤 / JIT 生成 / 六阶段有序思考 | 容器 |

### 什么需要形式化，什么不需要

HopSpec 的设计原则：**只形式化 AI 容易猜错的东西，其余用自然语言表达**。

**需要形式化**（7 种原子类型）：

- 该不该调 LLM（`LLM` vs `code`）——AI 可能把纯计算也交给 LLM
- 外部调用（`call`）——需要声明调用目标（工具/Hoplet/MCP）和相应参数
- 循环结构（`loop`）——定义树的嵌套层级
- 分支结构（`branch`）——定义树的嵌套层级
- 流程控制（`flow`）——改变控制流（退出/继续/中断），`continue`/`break` 需验证作用域在 `loop` 内部
- 子任务块（`subtask`）——声明展开模式（static/dynamic/think），static 有预定义子步骤，dynamic/think 运行时生成

**不需要形式化，自然语言即可**：

| 自然语言 | 代码映射 | 原因 |
|----------|----------|------|
| "提取/分析/拆解" | `hop_get` | 动词语义无歧义 |
| "判断/检验/核实" | `hop_judge` | 动词语义无歧义 |
| "对每个元素并发处理" | `asyncio.gather` | Python 基础语法 |

这些都是 Python 基础概念，LLM 生成代码时的推断是无歧义的。在 Spec 层为它们发明形式化符号是过度设计。

### 子流程：Hoplet 组合

HopSpec 不支持 Agent Spec 的 FlowNode（子流程嵌套）。复杂任务的拆分通过 **Hoplet 组合**实现：每个 Hoplet 是一个独立的可执行单元（有自己的 HopSpec + Hop.py），Hoplet 之间通过 `call` 节点声明调用。

```python
# 主流程 Hop.py 中调用子 Hoplet
from Tasks.SubTask.Hoplet.Hop import run as sub_run

async with hop_proc.session() as s:
    status, result = await s.hop_get(task="主任务第一步", ...)
    # 调用子 Hoplet
    sub_result = await sub_run(hop_proc, input_data=result)
    status, final = await s.hop_get(task="基于子任务结果继续", context=sub_result)
```

在 Spec 层面，子流程调用使用 `call` + `调用目标：hoplet`：

```markdown
#### 步骤N: call_subtask
- 类型：call
- 调用目标：hoplet
- 任务：调用 SubTask Hoplet 处理中间结果
- Hoplet路径：Tasks/SubTask/Hoplet/Hop.py
- 输入：intermediate_result
- 输出：sub_result
```

这延续了 HOP 的核心理念：**Python 就是控制流**。子流程编排不需要框架层面的抽象，Python 的函数调用就是最好的组合机制。`call` 节点让调用关系在 Spec 层可见、可审计。

---

## 节点属性规范

### LLM（LLM 执行节点）

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `LLM` |
| 任务 | **是** | LLM 要执行的任务，自然语言描述 |
| 输入 | **是** | 数据来源，引用前序步骤的输出变量 |
| 输出 | **是** | 本步骤产出的变量名 |
| 输出格式 | 否 | 结构化输出的格式描述，映射到 `return_format` |
| 核验 | 否 | 核验策略：`逆向`（默认）/ `正向交叉` / `无` / `<自定义核验器名>` |
| 说明 | 否 | 执行要点、约束条件、领域知识。支持自然语言描述控制流细节（如"不满足条件的跳过"） |
| 数据标签 | 否 | 输入变量在 LLM prompt 中的 XML 标签映射。标签名至少两个单词、snake_case，避免与引擎保留词碰撞。如 `model_output → <model_output>`、`context → <reference_doc>` |

```markdown
#### 步骤N: step_name
- 类型：LLM
- 任务：<LLM 任务描述，用 XML 标签引用数据，如"分析<model_output>中的内容">
- 输入：<变量名列表>
- 输出：<变量名>
- 输出格式：<结构描述>
- 核验：逆向
- 数据标签：variable_name → <xml_tag_name>（当变量名本身不适合做标签时声明映射）
- 说明：<执行要点>
```

### call（外部调用节点）

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `call` |
| 调用目标 | **是** | `tool` / `hoplet` / `mcp` / `rag` |
| 任务 | **是** | 调用的目标描述 |
| 输入 | **是** | 数据来源 |
| 输出 | **是** | 本步骤产出的变量名 |
| 工具域 | 条件 | `tool` 时必选，工具域标识（如 `all`、`security`） |
| Hoplet路径 | 条件 | `hoplet` 时必选，如 `Tasks/SubTask/Hoplet/Hop.py` |
| MCP服务 | 条件 | `mcp` 时必选，MCP 服务标识 |
| RAG集合 | 条件 | `rag` 时可选，knowledge base 名称（默认 `default`） |
| 核验 | 否 | 核验策略（`tool` 默认 `tool_use_verifier`） |
| 说明 | 否 | 调用约束 |

```markdown
#### 步骤N: step_name（调用工具）
- 类型：call
- 调用目标：tool
- 任务：<工具调用目标>
- 工具域：<域标识>
- 输入：<变量名列表>
- 输出：<变量名>

#### 步骤N: step_name（调用子Hoplet）
- 类型：call
- 调用目标：hoplet
- 任务：<子流程目标描述>
- Hoplet路径：<Tasks/.../Hoplet/Hop.py>
- 输入：<变量名列表>
- 输出：<变量名>

#### 步骤N: step_name（调用MCP服务）
- 类型：call
- 调用目标：mcp
- 任务：<tool_name: 调用描述>
- MCP服务：<server 标识名，对应 settings.yaml 中 mcp.servers 的 key>
- 输入：<变量名列表>
- 输出：<变量名>

> **任务格式约定**：`tool_name: 自然语言描述`。冒号前是 MCP 工具名（精确匹配 server 上注册的工具），冒号后是给 LLM 的上下文描述（JIT 模式下 LLM 可参考）。也可省略冒号直接使用工具名。

#### 步骤N: step_name（RAG检索）
- 类型：call
- 调用目标：rag
- 任务：检索与 <query_variable> 相关的领域知识
- RAG集合：<collection_name>
- 输入：<变量名列表>
- 输出：<变量名>
```

### loop（循环容器节点）

loop 支持两种模式：**for-each**（遍历集合）和 **while**（条件循环）。

#### for-each 模式

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `loop` |
| 遍历集合 | **是** | 要遍历的集合变量名 |
| 元素变量 | **是** | 循环变量名，子步骤通过此名引用当前元素 |
| 输出 | 否 | 收集子步骤结果的集合变量名 |
| 说明 | 否 | 自然语言解释（面向行业专家） |

```markdown
#### 步骤N: step_name（loop）
- 类型：loop
- 遍历集合：<集合变量名>
- 元素变量：<循环变量名>
- 输出：<结果集合变量名>

  #### 步骤N.1: child_step_name
  - 类型：...
```

**语义**：对 `遍历集合` 中的每个元素，依次执行全部子步骤。子步骤只能引用 `元素变量` 和外层已有的变量。执行完毕后，自动继续步骤 N+1。

**适用范围**：AOT 和 JIT 模式均可用。

#### while 模式

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `loop` |
| 条件 | **是** | Python 布尔表达式，为真时继续循环 |
| 最大轮次 | 否 | 安全上限，防止无限循环 |
| 输出 | 否 | 收集子步骤结果的集合变量名 |
| 说明 | 否 | 自然语言解释（面向行业专家） |

```markdown
#### 步骤N: step_name（loop）
- 类型：loop
- 条件：<Python布尔表达式>
- 最大轮次：<可选安全上限>
- 输出：<结果集合变量名>

  #### 步骤N.1: child_step_name
  - 类型：...
```

**语义**：当条件为真时，重复执行子步骤。每轮结束后重新评估条件。达到最大轮次时强制终止。

**适用范围**：AOT 和 JIT 模式均可用。JIT 模式下 while loop 必须设置 `最大轮次 > 0`（引擎自动注入循环迭代上限防护，防止无限循环线程泄漏）。

**属性互斥**：`遍历集合` 和 `条件` 二选一。有 `遍历集合` → for-each 模式；有 `条件` 无 `遍历集合` → while 模式。

### branch（条件分支容器节点）

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `branch` |
| 条件 | **是** | 布尔表达式，为真时执行子步骤 |

```markdown
#### 步骤N: step_name（branch）
- 类型：branch
- 条件：<布尔表达式>

  #### 步骤N.1: child_step_name
  - 类型：...

  #### 步骤N.2: another_child
  - 类型：...
```

**语义**：条件为真时，依次执行子步骤；条件为假时，跳过全部子步骤。执行完毕后（无论是否进入分支），自动继续步骤 N+1。

多条件分支用**顺序 branch** 表达：

```markdown
#### 步骤N: handle_fail（branch）
- 类型：branch
- 条件：status == "FAIL"

  #### 步骤N.1: exit_fail
  - 类型：flow
  - 动作：exit
  - 输出：error_result
  - 退出标识：EXIT_FAIL

#### 步骤N+1: handle_uncertain（branch）
- 类型：branch
- 条件：status == "UNCERTAIN"

  #### 步骤(N+1).1: supplementary_check
  - 类型：LLM
  - 任务：补充查证
  - ...
```

等价于 Python 的：

```python
if status == "FAIL":
    return error_result
if status == "UNCERTAIN":
    result = await s.hop_get(task="补充查证", ...)
```

### code（纯计算节点）

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `code` |
| 逻辑 | **是** | 自然语言描述的纯计算逻辑（无 LLM 调用） |
| 输入 | **是** | 使用的变量 |
| 输出 | **是** | 产出的变量 |

```markdown
#### 步骤N: step_name
- 类型：code
- 逻辑：<自然语言计算描述>
- 输入：<变量名列表>
- 输出：<变量名>
```

### flow（流程控制节点）

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `flow` |
| 动作 | **是** | `exit` / `continue` / `break` |
| 输出 | 条件 | `exit` 时必选（返回变量名），`continue`/`break` 时不需要 |
| 退出标识 | 否 | `exit` 时可选，用于 `hop_exit` 追踪 |
| 目标循环 | 条件 | `continue`/`break` 时必选，引用包含自己的 `loop` 步骤的 step_name |

```markdown
#### 步骤N: step_name（退出）
- 类型：flow
- 动作：exit
- 输出：<变量名>
- 退出标识：<EXIT_ID>

#### 步骤N: step_name（跳过当前元素）
- 类型：flow
- 动作：continue
- 目标循环：<包含自己的 loop 步骤的 step_name>

#### 步骤N: step_name（中断遍历）
- 类型：flow
- 动作：break
- 目标循环：<包含自己的 loop 步骤的 step_name>
```

**作用域规则**：
- `exit`：可出现在任何位置，终止整个流程
- `continue`：必须在某个 `loop` 的子步骤（含嵌套）中，跳过当前元素继续下一个
- `break`：必须在某个 `loop` 的子步骤（含嵌套）中，提前结束整个遍历

### subtask（子任务容器节点）

subtask 支持三种展开模式：**static**（预定义子步骤）、**dynamic**（JIT 运行时生成或加载固化路径）、**think**（六阶段有序思考）。

#### 通用属性

| 属性 | 必选 | 说明 |
|------|------|------|
| 类型 | **是** | 固定值 `subtask` |
| 展开 | **是** | `static` / `dynamic` / `think` |
| 输入 | 否 | 输入变量列表 |
| 输出 | 条件 | dynamic/think 时必选 |
| 最大深度 | 否 | 最大嵌套深度（默认 0 → 有效值 3；1=叶子禁止嵌套；N=允许 N-1 层子 subtask） |

#### static 模式

| 属性 | 必选 | 说明 |
|------|------|------|
| 子步骤 | **是** | 预定义的子步骤（缩进内嵌） |

```markdown
#### 步骤N: step_name（subtask）
- 类型：subtask
- 展开：static
- 输入：<变量名列表>
- 输出：<变量名>

  #### 步骤N.1: child_step_name
  - 类型：LLM
  - ...

  #### 步骤N.2: another_child
  - 类型：code
  - ...
```

**语义**：顺序执行预定义的子步骤，完成后收集输出。等价于一组逻辑相关步骤的封装。

#### dynamic 模式

| 属性 | 必选 | 说明 |
|------|------|------|
| 任务 | **是** | 子任务的自然语言描述 |
| 输出 | **是** | 输出变量列表 |
| 最大步数 | 否 | 生成子步骤数量上限（默认 10，须 > 0） |
| 约束 | 否 | 允许的子步骤类型（逗号分隔，默认 `LLM,code,call,branch`） |
| 固化路径 | 否 | `.spec.md` 文件路径，存在时优先加载 |
| 子步骤 | 禁止 | dynamic 不应有预定义子步骤 |

```markdown
#### 步骤N: step_name（subtask）
- 类型：subtask
- 展开：dynamic
- 任务：<子任务描述>
- 输入：<变量名列表>
- 输出：<变量名>
- 最大步数：10
- 约束：LLM,code,call,branch
- 固化路径：<path/to/solidified.spec.md>
```

**语义**：运行时由 LLM 生成执行计划并执行。如果有固化路径，优先加载已验证的步骤序列。

#### think（有序思考 / Structured Thinking）模式

| 属性 | 必选 | 说明 |
|------|------|------|
| 任务 | **是** | 子任务的自然语言描述 |
| 输出 | **是** | 输出变量列表 |
| 最大步数 | 否 | 每轮生成子步骤数量上限（默认 10，须 > 0） |
| 最大迭代 | 否 | 迭代轮次上限（默认 5，须 > 0） |
| 约束 | 否 | 允许的子步骤类型（逗号分隔，默认 `LLM,code,call,branch`） |
| 子步骤 | 禁止 | think 不应有预定义子步骤 |

```markdown
#### 步骤N: step_name（subtask）
- 类型：subtask
- 展开：think
- 任务：<子任务描述>
- 输入：<变量名列表>
- 输出：<变量名>
- 最大步数：10
- 最大迭代：5
- 约束：LLM,code,call,branch
```

**语义**：六阶段有序思考（Decompose -> Plan -> Execute+Monitor -> Reflect -> Revise -> Synthesize），每轮反思后判断是否收敛，未收敛则修正方案重试。连续失败时抛出外部交互信号。

**嵌套约束**：subtask 支持有限深度嵌套，通过 `最大深度` 属性控制（默认 3 层）。有效深度 ≤ 1 时 `约束` 属性中的 `subtask` 会被自动移除。子 subtask 的有效深度必须小于父级。

**渐进路径**：think 的成功路径可固化为 `.spec.md` 文件，由 dynamic 模式加载；人类审阅后可转为 static 模式的预定义子步骤。

详见 `hoplogic/docs/hop_subtask.md`。

---

## 属性书写约定

1. **步骤标题格式**：`#### 步骤N: step_name` 或 `#### 步骤N: step_name（类型标注）`。step_name 用 snake_case 英文，从任务描述派生，同一 Spec 内唯一
2. **属性名用自然语言**，与自然语言 Spec 风格一致。代码生成时 AI 映射到对应参数名
3. **变量名用英文小写 + 下划线**（snake_case），与 Python 变量命名一致
4. **布尔表达式**（branch 条件）用 Python 语法书写，便于直接映射
5. **输入变量列表**用逗号分隔：`输入：context_window, claim`
6. **输出格式**用 JSON Schema 风格描述：`{"claims": List[str]}`
7. **核验策略**省略时使用默认值（`LLM` 默认逆向核验）。显式写 `核验：无` 表示跳过语义核验（如逆向核验、正向交叉核验），但格式校验（`format_verifier`）始终自动应用于所有 LLM 步骤，作为所有核验的前置检查。当指定了语义核验器时，执行顺序为 `format_verifier` -> 语义核验器，格式检查失败直接触发重试。格式核验检测结构化输出中的"序列化残留"——任何层级中本应是 dict/list 但被 LLM 字符串化的值都会触发重试。格式核验不调用 LLM，零额外开销
8. **说明字段**是自由文本，可包含补充约束和领域知识
11. **LLM 步骤的数据引用标签**：当 `LLM` 步骤的任务描述中需要引用输入数据时，使用描述性 XML 标签包裹数据，标签名至少两个单词、snake_case，避免与引擎保留词（`context`、`input`、`output`）碰撞。例如 `<model_output>`、`<reference_doc>`、`<claim_list>`。禁止使用单词通用标签如 `<context>`、`<text>`、`<data>`。这确保 LLM 能准确关联任务描述中的引用与实际数据
9. **flow 节点的动作**：`exit`（退出）、`continue`（跳过当前元素）、`break`（中断遍历）。`continue`/`break` 必须通过 `目标循环` 属性引用包含自己的 `loop` 步骤的 step_name
10. **call 节点的调用目标**：`tool`（工具调用）、`hoplet`（子 Hoplet 调用）、`mcp`（MCP 服务调用）、`rag`（RAG 知识库检索）。不同目标需要不同的条件属性（工具域/Hoplet路径/MCP服务/RAG集合）

---

## 完整示例：Verify 任务

```markdown
## 任务概述

对大模型生成的推理输出进行三阶段逻辑核验审计，量化评估幻觉，输出结构化报告。

## 输入定义

- `context_window`: 上下文/参考文档
- `model_output`: 大模型生成的推理或回答

## 硬性约束

- 即使是公认事实，只要 context_window 中未提及，必须标记为外部知识泄露
- 任何不能从前提严格推导出的步骤，必须标记为推导不连贯

## 执行流程

#### 步骤1: extract_atomic_facts
- 类型：LLM
- 任务：将模型输出拆解为独立的原子事实陈述，每条仅含一个知识点
- 输入：model_output
- 输出：atomic_claims
- 输出格式：{"claims": List[str]}
- 核验：无

#### 步骤2: check_grounding（loop）
- 类型：loop
- 遍历集合：atomic_claims
- 元素变量：claim
- 输出：grounding_errors

  #### 步骤2.1: judge_claim_source
  - 类型：LLM
  - 任务：判断该原子陈述的来源类型（Pass/External/Fabrication），在 context_window 中寻找证据
  - 输入：context_window, claim
  - 输出：verdict
  - 输出格式：{"verdict": str, "location": str, "evidence": str}
  - 说明：
    • Pass = 上下文有明确原文支撑
    • External = 上下文未提及，属外部知识泄露
    • Fabrication = 纯粹无中生有
    • verdict 非 Pass 时记入 grounding_errors

#### 步骤3: check_logic
- 类型：LLM
- 任务：分析推理步骤间的推导关系，检测蕴含断裂、概率跳跃、概念漂移、阿谀奉承
- 输入：context_window, model_output
- 输出：logic_errors
- 输出格式：{"errors": List[str], "locations": List[str], "evidences": List[str], "severities": List[str]}

#### 步骤4: check_consistency
- 类型：LLM
- 任务：检验推理自洽性——反事实干扰测试 + 内部冲突检测
- 输入：context_window, model_output
- 输出：is_consistent

#### 步骤5: handle_inconsistency（branch）
- 类型：branch
- 条件：is_consistent == False

  #### 步骤5.1: list_conflicts
  - 类型：LLM
  - 任务：列出推理中的内部冲突和反事实不敏感问题
  - 输入：context_window, model_output
  - 输出：consistency_errors
  - 输出格式：{"conflicts": List[str], "evidences": List[str]}

#### 步骤6: merge_errors
- 类型：code
- 逻辑：合并 grounding_errors + logic_errors + consistency_errors 为 all_errors
- 输入：grounding_errors, logic_errors, consistency_errors
- 输出：all_errors

#### 步骤7: score_reliability
- 类型：LLM
- 任务：根据三阶段审计结果综合评定可靠性评分(0-100)并生成一句话总结
- 输入：all_errors
- 输出：report
- 输出格式：{"reliability_score": int, "verification_summary": str}
- 核验：无

#### 步骤8: assemble_report
- 类型：code
- 逻辑：组装最终报告（reliability_score, hallucination_detected, errors, verification_summary）
- 输入：report, all_errors
- 输出：final_report

#### 步骤9: output_report
- 类型：flow
- 动作：exit
- 输出：final_report

## 输出格式

{
  "reliability_score": 0-100,
  "hallucination_detected": true/false,
  "errors": [{"type": str, "location": str, "evidence": str, "severity": str}],
  "verification_summary": str
}

## 输入日志示例

{
  "context_window": "根据2023年财报，A公司全年营收为120亿元...",
  "model_output": "A公司2023年营收120亿元，增长15%..."
}
```

---

## 树结构可视化

上述 Verify 示例的结构树：

```
步骤1: extract_atomic_facts     LLM        → atomic_claims
步骤2: check_grounding          loop(atomic_claims)
 └ 步骤2.1: judge_claim_source  LLM        → verdict → grounding_errors
步骤3: check_logic              LLM        → logic_errors
步骤4: check_consistency        LLM        → is_consistent
步骤5: handle_inconsistency     branch(is_consistent == False)
 └ 步骤5.1: list_conflicts      LLM        → consistency_errors
步骤6: merge_errors             code       → all_errors
步骤7: score_reliability        LLM        → report
步骤8: assemble_report          code       → final_report
步骤9: output_report            flow:exit(final_report)
```

注意：

- 步骤5（branch）不引用步骤6。步骤5 执行完毕后自动落到步骤6。
- 步骤2（loop）不引用步骤3。loop 内的子步骤对每个元素执行完毕后，自动落到步骤3。
- 没有任何步骤引用非子步骤的编号。控制流完全由**层级嵌套 + 顺序执行**决定。

---

## 为什么禁止跳转

### 1. 与 Python 块结构一致

Python 没有 goto。`for`/`if`/`while` 都是块——进入块，执行内容，退出块，继续下一行。HopSpec 的 loop/branch 完全对应这个模型。跳转是图的概念（Burr、Agent Spec），不是 Python 的概念。

### 2. AI 代码生成更可靠

跳转意味着 AI 需要理解全局拓扑——"步骤5 跳到步骤8"隐含了"步骤6、7 被跳过"。嵌套结构是局部的——每个 branch 只需要看自己的子步骤，不需要理解整棵树。局部性让 AI 生成代码时出错更少。

### 3. Spec 审阅不需要画图

如果有跳转，审阅者需要在脑子里画一个控制流图才能理解流程。禁止跳转后，从上到下读就是执行顺序，遇到缩进就是嵌套块。

### 4. flow 是唯一的"跳出"

`flow` 节点包含三种动作：`exit`（等价于 `return`）终止整个流程，`continue` 跳过当前循环元素，`break` 中断整个循环。它们都不是"跳转到某个步骤"——`exit` 终止流程，`continue`/`break` 改变最近 `loop` 的循环行为。这是结构化编程允许的非顺序控制流，作用域由 `目标循环` 属性约束。

---

## Spec ↔ Code 映射

### 确定性映射（结构层）

每个步骤的 step_name 映射为代码中的注释锚点：`# 步骤N: step_name — type — task`

| Spec 类型 | Python 代码 |
|-----------|------------|
| `LLM` + `输出格式` | `# 步骤N: step_name — LLM` + `await s.hop_get(task=..., return_format=...)` |
| `LLM`（任务描述为判断语义） | `# 步骤N: step_name — LLM` + `await s.hop_judge(task=...)` |
| `call` + `调用目标：tool` | `# 步骤N: step_name — call` + `await s.hop_tool_use(task=..., tool_domain=...)` |
| `call` + `调用目标：hoplet` | `# 步骤N: step_name — call` + `from <path> import <func>; result = await <func>(...)` |
| `call` + `调用目标：mcp` | `# 步骤N: step_name — call` + `result = await mcp_client.call(...)` |
| `loop` + 子步骤 | `# 步骤N: step_name — loop` + `for item in collection:` / `while condition:` + 缩进块 |
| `branch` + 子步骤 | `# 步骤N: step_name — branch` + `if condition:` + 缩进块 |
| `code` | `# 步骤N: step_name — code` + 纯 Python 赋值/计算 |
| `flow` + `动作：exit` | `# 步骤N: step_name — flow` + `session.hop_exit(...)` + `return` |
| `flow` + `动作：continue` | `# 步骤N: step_name — flow` + `continue` |
| `flow` + `动作：break` | `# 步骤N: step_name — flow` + `break` |
| `subtask`（static） | `# 步骤N: step_name — subtask` + 子步骤顺序执行块 |
| `subtask`（dynamic） | `# 步骤N: step_name — subtask` + JIT 生成或加载固化 spec 后执行 |
| `subtask`（think） | `# 步骤N: step_name — subtask` + 六阶段有序思考 |

### AI 推断映射（语义层）

| Spec 自然语言 | Python 代码 | 推断依据 |
|--------------|------------|----------|
| 任务描述为"提取/分析/拆解" | `hop_get` | 动词语义 |
| 任务描述为"判断/检验/核实" | `hop_judge` | 动词语义 |

结构层映射是确定性的（Spec 类型 → 代码结构一一对应）。语义层映射由 AI 从自然语言推断，推断依据无歧义。

### `/verifyspec` 审计能力

HopSpec 的结构化设计使 `/verifyspec` 可以对 Spec 进行 6 项自动审计：

1. **结构完整性**：6 个章节（任务概述、输入定义、硬性约束、执行流程、输出格式、输入日志示例）是否齐全，执行流程是否以 `flow`（动作：exit）结束
2. **原子类型正确性**：每个步骤是否声明了类型，LLM/code/call 区分是否正确，`flow` 的 `continue`/`break` 是否在 `loop` 内部
3. **树结构合规**：无跳转引用，`loop`/`branch` 子步骤正确缩进，`branch` 条件是确定性 Python 表达式
4. **数据流追踪**：每个输入变量是否有前序步骤产出，每个输出变量是否被后续步骤消费，`loop` 子步骤是否引用了元素变量
5. **核验策略审阅**：标记未显式声明核验策略的步骤，建议高风险步骤使用更强核验。领域专家在 Spec 审阅阶段就能决定核验策略（逆向/正向/工具/无/自定义），不需要等到代码生成后才发现
6. **属性与命名规范**：必选属性齐全，变量名 snake_case，步骤编号连续，step_name 唯一且格式正确

---

## AOT/JIT 双模式

HopSpec 支持两种执行模式，通过 Spec 头部的 `模式` 属性声明：

| 模式 | 含义 | 适用场景 |
|------|------|----------|
| **AOT**（Ahead-Of-Time） | 完整预定义流程，所有步骤在执行前已确定 | 流程固定、可审计性要求高的任务 |
| **JIT**（Just-In-Time） | 运行时动态决定下一步，LLM 根据当前状态选择步骤 | 探索性任务、对话式交互、步骤数不确定的任务 |

### 模式对原子类型的约束

| 原子类型 | AOT | JIT | 说明 |
|----------|-----|-----|------|
| `LLM` | 可用 | 可用 | 两种模式均支持 |
| `call` | 可用 | 可用 | 两种模式均支持 |
| `loop`（for-each） | 可用 | 可用 | 遍历有界集合，两种模式均安全 |
| `loop`（while） | 可用 | 可用 | JIT 模式下须设置 `最大轮次 > 0`（自动注入迭代防护） |
| `branch` | 可用 | 可用 | 两种模式均支持 |
| `code` | 可用 | 可用 | 两种模式均支持 |
| `flow` | 可用 | 可用 | 两种模式均支持 |
| `subtask`（static） | 可用 | 可用 | 预定义子步骤，两种模式均支持 |
| `subtask`（dynamic） | 可用 | 可用 | JIT 生成或加载固化路径 |
| `subtask`（think） | 可用 | 可用 | 六阶段有序思考，交互模式下支持外部交互信号 |

### 默认模式

未声明 `模式` 属性时，默认为 **AOT** 模式。

---

## 交互/批量双模式

Hoplet 支持两种运行模式，通过 metainfo.md 的 `运行模式` 属性声明：

| 模式 | 含义 | 适用场景 |
|------|------|----------|
| **交互**（默认） | LACK_OF_INFO/UNCERTAIN 时暂停，等待外部反馈后续解 | CLI 单次执行、View UI 执行 |
| **批量** | LACK_OF_INFO/UNCERTAIN 直接返回，不等待反馈 | 批量测试、自动化管线 |

### 主函数返回约定

主函数 `main_hop_func` 返回 `(HopStatus, str)` 元组，与算子返回模式一致：

| status | 含义 | 交互模式行为 | 批量模式行为 |
|--------|------|-------------|-------------|
| OK | 正常完成 | 输出结果 | 输出结果 |
| LACK_OF_INFO | LLM 推理层信息不足 | CLI/UI 提示补充信息，add_feedback 后重试 | 直接返回 |
| UNCERTAIN | LLM 不确定 | CLI/UI 展示建议，add_feedback 后重试 | 直接返回 |
| FAIL | 失败（传输/核验/能力不足） | 输出错误，不进入反馈循环 | 输出错误 |

> **FAIL vs LACK_OF_INFO 边界**：前置管线失败（RAG 检索无结果、数据源不可达等）应在调用 LLM 算子之前直接返回 `FAIL`。`LACK_OF_INFO` 仅用于 LLM 算子自报告的推理层信息缺失——`add_feedback` 只影响 LLM 对话历史，无法修复管线层问题。FAIL 时应调用 `hop_exit` 关闭 session；LACK_OF_INFO/UNCERTAIN 时不调用 `hop_exit`，保持 session 活跃等待反馈。

### 交互模式的代码映射

交互模式在 Hop.py 的 `main()` 入口中体现为 CLI 反馈循环：
- 检查 main_hop_func 返回的 status
- FAIL -> 直接输出错误，不进入反馈循环（前置管线失败或 LLM 传输/核验失败）
- LACK_OF_INFO -> 打印 missing_info，等待用户输入补充信息
- UNCERTAIN -> 打印 suggestions，等待用户选择方向
- 通过 `session.add_feedback()` 注入反馈，重新调用 main_hop_func

在 View 模式中，Transport 层（app.py/web.py）将反馈循环映射为 UI 交互（显示反馈表单，提交后重新执行）。FAIL 结果不显示反馈表单。

---

## 与 Agent Spec 的关系

| Agent Spec 概念 | HopSpec 对应 | 差异 |
|----------------|-------------|------|
| AgentNode | LLM | HOP 自带核验；get/judge 由 AI 推断 |
| ToolNode | call（调用目标：tool） | HOP 自带工具核验 |
| MapNode | loop | 相同概念；HopSpec 用缩进嵌套而非边引用 |
| BranchingNode | branch | 相同概念；HopSpec 子步骤内嵌，禁止跳转到外部节点 |
| FlowNode（子流程） | call（调用目标：hoplet）/ subtask | HOP 通过 `call` 声明 Hoplet 调用，`subtask` 支持动态子流程生成 |
| StartNode / EndNode | 隐含 / flow（动作：exit） | 第一个步骤即 start |
| ControlFlowEdge | 禁止 | HopSpec 用层级嵌套替代显式边 |
| 序列化格式 | Markdown | Agent Spec 用 YAML/JSON；HOP 用 Markdown |
| 核验声明 | 有 | Agent Spec 无此概念 |

**核心差异**：Agent Spec 是**图**（节点 + 边），HopSpec 是**树**（层级嵌套 + 顺序执行）。图需要跳转（edge），树不需要。树直接映射到 Python 的缩进块结构，是 HOP "Python 就是控制流" 理念在 Spec 层的体现。

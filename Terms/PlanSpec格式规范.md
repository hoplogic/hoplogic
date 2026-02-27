# PlanSpec 格式规范

> JIT 组件版本: v0.12.0

## 设计动机

### 现状问题

长时间任务中，执行者（LLM agent / HOP 引擎）的工作记忆衰减，导致：

- **目标漂移**：做着做着偏离原始需求
- **约束遗忘**：上下文窗口滚动后硬性约束丢失
- **重复劳动**：忘记已完成的步骤，重新执行
- **无法恢复**：中断后无法从断点续跑

HopSpec 的树状结构天然解决这些问题（进度可观测、约束绑定、可恢复执行），但 HopSpec 太重——7 种原子步骤类型、25+ 属性、严格的核验语义——不适合快速规划场景。

### PlanSpec 的定位

PlanSpec 是 HopSpec 的**轻量子集**，支持完整规划和 think 模式动态有序思考：

| 维度 | HopSpec | PlanSpec |
|------|---------|----------|
| 步骤类型 | 7 种（LLM/call/loop/branch/code/flow/subtask） | 4 种（reason/act/decide/subtask） |
| 步骤属性 | 25+（return_format, verifier, call_target, ...） | ~10（description, outputs, detail, inputs, result, status, ...） |
| 数据流 | inputs/outputs 必填 | `→ outputs` 摘要行建议声明，`← inputs` detail 区可选 |
| 核验语义 | 强制（逆向/正向交叉/工具核验） | 无（result 记录实际完成情况） |
| 进度追踪 | 无（静态规范） | 内置（status + progress） |
| 节点细节 | 多行 heading + 属性列表 | `>` 节点体（可折叠） |
| 生成成本 | 高（LLM 需理解复杂格式） | 低（LLM 可快速生成） |
| 适用场景 | 可执行的智能体程序 | 任务规划、进度追踪、结构化思考 |

核心原则：**PlanSpec 是 HopSpec 的规划视图，两者可双向转换**。

PlanSpec 面向 LLM 生成和消费，不是给人手写的。因此格式设计优先考虑**紧凑性**（节省 token）和**机器可解析性**，而非人类编辑友好性。

---

## PlanSpec 格式定义（LLM Prompt Ready）

PlanSpec 是结构化规划树的紧凑文本表示。用于任务规划、进度追踪和结构化思考。

**文档结构**：

```
# Plan: <标题>                              # 可选，规划标题
Goal: <一句话目标>                           # 必选
> <补充说明>                                 # Goal 的 > 续行（可选）
Constraints:                                # 可选，约束列表
- <约束 1>
- <约束 2>
## Steps                                    # 必选，步骤树
1. [x] [reason] 分析输入数据的质量问题 → data_profile
  > ← raw_data                              # 节点体：输入声明（可选）
  > 输出各列缺失率、异常值比例               # 节点体：约束/提示（可选）
2. [x] [act] 清洗数据 → cleaned | 完成      # [x]=done, | 后为 result
3. [>] [subtask] 迭代训练直到达标 → model    # 典型有序思考循环
  3.1. [x] [act] 训练模型并交叉验证 → cv_metrics | Gini=0.35
  3.2. [x] [reason] 诊断模型弱点，建议调整 → adjustments
  3.3. [>] [decide] 是否达标                 # 容器：children 是各条件分支
    3.3.1. [act] 达标 → 输出最终模型
    3.3.2. [act] 未达标 → 应用调整，继续下一轮
4. [act] 生成报告 → report
```

**摘要行**（每步一行）：
- `N.` — 编号，支持多级嵌套（`1.`, `2.1.`, `2.1.3.`）
- `[status]` — 状态标记：`[ ]` pending / `[x]` done / `[>]` active / `[!]` blocked / `[~]` skipped，省略等同 pending
- `[type]` — 步骤类型，4 种：
  - `reason` — 推理/分析（叶子）
  - `act` — 执行动作/计算（叶子）
  - `decide` — 条件决策，children 为各分支（如上例步骤 3.3）
  - `subtask` — 子任务分解，children 为子步骤序列（如上例步骤 3：迭代循环）
- `description` — 面向 LLM 的任务说明（80-130 chars，语义完整，读一行就知道做什么）
- `→ outputs` — 输出变量声明，逗号分隔（`→ var1, var2`）
- `| result` — 实际完成情况（执行后填写）
- `| Progress: N/M` — 迭代进度（done/total），仅用于循环型 subtask

其中 status、result、Progress 可选；outputs 建议每步都声明（确保数据流完整）。

**节点体**（`>` 行）：摘要行之后、下一步骤之前，以 `>` 开头的行提供执行细节、约束、格式要求。`> ← inputs` 声明输入变量（可选，显式覆盖数据流推导）。

**树结构由 step ID 编码**：`2.1` 是 `2` 的子步骤，`2.1.3` 是 `2.1` 的子步骤。缩进仅为视觉辅助，解析器依据 step ID 层级关系构建树。

**Prompt 架构**（四阶段）：

| 阶段 | LLM 收到的上下文 | LLM 的任务 |
|------|-----------------|-----------|
| **生成**（plan generation） | 任务描述 + PlanSpec 格式模板 | 生成完整 PlanSpec 文档 |
| **步骤执行**（step execution） | 步骤自身的 task/inputs/outputs + run_history | 执行当前步骤（history 提供隐式反思上下文） |
| **步骤反思**（step reflection） | status + result + plan_state + can_interact | `status != OK` 时触发，决定重试/跳过/调整/上报 |
| **轮末重规划**（re-plan） | 当前计划状态 + 结构命令列表（ADD/REVISE/REPLAN） | 一轮未收敛时，结构性调整计划 |

引擎自动管理步骤状态（DONE/BLOCKED/SKIP）。LLM 在步骤反思和重规划阶段通过 `PLAN_CMD:` 命令修改计划结构。详见 [Think 反思协议](#think-反思协议) 和 [命令协议（PLAN_CMD）](#命令协议plan_cmd) 章节。

---

## 文档结构

一个完整的 PlanSpec 文档包含四个区域：

```
# Plan: <标题>
Goal: <一句话目标>
> <补充说明>
Constraints:
- <约束条件 1>
- <约束条件 2>
## Steps
1. [x] [type] description → outputs | actual result
  > ← inputs (可选)
  > detail line (节点体)
2. [>] [type] description → outputs
  2.1. [type] description → outputs
```

| 区域 | 必选 | 说明 |
|------|------|------|
| `# Plan: <标题>` | 否 | 规划标题，`# Plan:` 前缀可选 |
| `Goal: <目标>` | **是**（验证要求） | 一句话描述规划目标 |
| `> <补充说明>` | 否 | Goal 的 `>` 续行，提供补充上下文 |
| `Constraints:` | 否 | 约束条件列表，每条以 `- ` 开头 |
| `## Steps` | **是**（验证要求） | 步骤树，至少一个步骤 |

解析器兼容 `**Goal**:` 和 `## Constraints` 写法（向后兼容），但规范格式为 `Goal:` 和 `Constraints:`。

---

## 步骤类型

PlanSpec 定义 4 种步骤类型，每种对应一类认知动作：

| 类型 | 含义 | 典型动词 | 可有 children |
|------|------|----------|:---:|
| `reason` | 推理/分析 | 分析、推断、提取、总结、验证 | 否 |
| `act` | 执行动作 | 计算、过滤、调用、写入 | 否 |
| `decide` | 条件决策 | 判断、选择、分支 | **是** |
| `subtask` | 子任务分解 | 分解、遍历、迭代 | **是** |

### 容器约束

只有 `subtask` 和 `decide` 可以包含子步骤（children）。`reason`、`act` 是叶子节点。

这与 HopSpec 的结构规则一致：容器节点（loop/branch/subtask）可以嵌套，叶子节点（LLM/code/call/flow）不可以。

### 类型选择指南

```
需要 LLM 推理/分析/验证吗？
  ├─ 是 → reason
  └─ 否 → 是确定性计算/动作吗？
           ├─ 是 → act
           └─ 否 → 有多个分支路径？
                    ├─ 是 → decide（children = 各分支）
                    └─ 否 → subtask（children = 子步骤）
```

---

## 步骤格式

### 摘要行

每个步骤的摘要占一行，格式为：

```
N. [status] [type] description → outputs | result | Progress: N/M
```

| 部分 | 必选 | 说明 |
|------|------|------|
| `N.` | **是** | 步骤编号，支持多级（`1.`, `2.1.`, `2.1.3.`） |
| `[status]` | 否 | 状态标记，省略时为 pending |
| `step_name` | 否 | 唯一标识，LLM 生成时省略，外部工具可注入（如 8hex） |
| `[type]` | **是** | 步骤类型，方括号包裹 |
| `description` | 否 | 面向 LLM 的描述性任务说明（80-130 chars，语义完整） |
| `→ outputs` | 建议 | 输出变量声明，逗号分隔（`→ var1, var2`） |
| `\| result` | 否 | 实际完成情况（无标签，`|` 分隔） |
| `\| Progress: N/M` | 否 | 迭代进度，`|` 分隔（仅循环场景） |

**description 设计**：面向 LLM 消费，不是人类扫描用的 3-5 词标签。LLM 读一行摘要就应该知道做什么、怎么做。

**`→ outputs` 设计**：输出变量在摘要行末尾声明（`|` 分隔符之前）。这是该步骤产出的数据，下游步骤可引用。鼓励每步都声明 outputs，确保 PlanSpec → HopSpec 转换时数据流完整。

**step_name 设计**：LLM 生成 PlanSpec 时不需要起名（降低生成负载），外部工具（如 HOP 引擎）可后续注入唯一标识（如 8 位 hex）作为锚点。有名步骤格式：`N. [status] step_name [type] description`。

### 节点体（> detail）

摘要行之后，可以跟随多行以 `>` 开头的节点体，提供执行细节：

```
1. [reason] 分析数据分布和质量问题 → data_profile, clean_suggestions
  > ← synthetic_data
  > 输出 data_profile 包含各列缺失率、分布类型、异常值比例
  > clean_suggestions 为 action list，每条含 column, strategy, params
```

| 元素 | 格式 | 说明 |
|------|------|------|
| `← inputs` | `> ← var1, var2` | 输入变量声明（可选，显式覆盖数据流推导） |
| detail | `> <任意文本>` | 约束、格式要求、执行提示、验收标准 |

**`← inputs` 设计**：放在节点体中而非摘要行，保持摘要行紧凑。以 `← ` 开头的 `>` 行被解析为输入声明，解析后从 detail 中移除。inputs 是可选的——引擎可通过前序步骤的 outputs 集合自动推导数据流。但**规划阶段鼓励声明 inputs**，以确保 PlanSpec → HopSpec 转换时无缺口。

**节点体用途**：
- 执行约束和验收标准
- 输出格式描述（字段结构、类型）
- LLM 执行提示（分析维度、关注点）
- 输入声明（`← inputs`）

### 状态标记

| 标记 | 状态 | 含义 |
|------|------|------|
| `[ ]` | pending | 待执行（序列化时省略） |
| `[x]` | done | 已完成 |
| `[>]` | active | 进行中 |
| `[!]` | blocked | 阻塞 |
| `[~]` | skipped | 跳过 |

pending 状态在序列化输出中省略标记，即 `1. [type]` 等价于 `1. [ ] [type]`。

### 树结构

**嵌套层级通过 step ID 编码**，而非 heading level。`2.1` 是 `2` 的子步骤，`2.1.3` 是 `2.1` 的子步骤。缩进（2 空格/层）仅为视觉辅助，解析器不依赖缩进：

```
1. [subtask] Process all items → results
  1.1. [act] Process item A → item_a_result
    1.1.1. [reason] Verify item A → verification
```

嵌套深度无硬性限制（不再受 markdown heading level 约束）。

### 行内属性

摘要行中 `→ outputs` 之后可用 `|` 分隔追加可选属性：

```
1. [x] [reason] Break output into claims → claims | Extracted 12 atomic claims
2. [subtask] Process all items → results | Progress: 3/5
3. [x] [reason] Check results → verdicts | All 10 checks passed | Progress: 10/10
```

| 属性 | 格式 | 说明 |
|------|------|------|
| outputs | `→ var1, var2` | 步骤输出变量（在 `|` 之前） |
| result | `\| <实际完成情况>` | 执行后填写的完成情况（无标签） |
| Progress | `\| Progress: N/M` 或 `\| Progress: N` | 迭代进度（done_count/total_count） |

所有属性均为可选。`|` 后面非 `Progress:` 开头的段即为 result。

### 与 HopSpec 的属性对比

| HopSpec 属性 | PlanSpec 对应 | 状态 |
|-------------|-------------|------|
| 类型 | `[type]`（摘要行） | 简化 |
| 任务 | description（摘要行） | 简化 |
| 输入 | `← inputs`（节点体，可选） | 简化（detail 区可选声明） |
| 输出 | `→ outputs`（摘要行） | **显式声明** |
| 输出格式 | 节点体 detail | 简化（自然语言描述） |
| 核验 | — | 省略（result 记录实际结果） |
| 说明 | 节点体 detail | 扩展（多行展开细节） |
| 调用目标 | — | 省略 |
| 遍历集合 / 元素变量 | — | 省略 |
| 条件 | description（合并） | 简化 |
| 展开模式 | — | 省略 |

---

## 折叠规则

PlanSpec 支持节点体的**折叠/展开**，这是一种**渲染行为**（文件中 detail 始终存在，渲染器按状态决定显示深度）。

### 按状态折叠（默认规则）

| 状态 | 摘要行 | `>` 节点体 | children | `\| result` |
|------|--------|-----------|----------|-------------|
| `[x]` done | 显示 | **折叠** | 显示 | 显示 |
| `[>]` active | 显示 | **展开** | 显示 | — |
| `[ ]` pending | 显示 | **折叠** | 显示 | — |
| `[!]` blocked | 显示 | **展开** | 显示 | — |
| `[~]` skipped | 显示 | **折叠** | 显示 | — |

默认规则下 children 始终可见（保持树结构概览），只有 `> detail` 按状态折叠。

### 显式展开/折叠（EXPAND / COLLAPSE）

用户或工具（如 `/showplan`）可通过 API 显式覆盖默认折叠规则，用于上下文窗口管理：

| API | 效果 | 用途 |
|-----|------|------|
| `expand_step(plan, step_id)` | 强制显示 detail + children | 想看某个折叠节点的详细内容 |
| `collapse_step(plan, step_id)` | 强制隐藏 detail + children | 释放上下文空间 |

**优先级**：显式标志 > 状态默认规则。

| expanded 标志 | `>` 节点体 | children |
|---------------|-----------|----------|
| `True`（EXPAND） | **展开** | **显示** |
| `False`（COLLAPSE） | **折叠** | **隐藏** |
| `None`（默认） | 按状态规则 | 始终显示 |

`expanded` 是瞬态渲染标志，不参与序列化/解析（不写入 plan 文件）。`serialize_plan(fold=True)` 时生效，`fold=False`（默认）时忽略。

**典型场景**：
- 大型 plan 中只关注步骤 5，COLLAPSE 1-4 和 6-7 节省上下文
- 已完成的 subtask 被 COLLAPSE 后，整个子树收缩为一行
- 想看某个 done 步骤的执行细节，EXPAND 临时展开

**设计理由**：
- **done 折叠**：已完成的步骤只需看到结果，细节不再重要
- **active 展开**：正在执行的步骤需要完整上下文
- **pending 折叠**：尚未执行的步骤只需知道意图，细节待执行时展开
- **blocked 展开**：阻塞的步骤需要看到细节以诊断问题

### 折叠示例

完整文件内容：
```
1. [x] [act] 生成合成保单数据 → synthetic_data | 生成 10K 行
  > 字段：policy_no, vehicle_age, driver_age
  > claim_flag 阳性率约 15%
2. [>] [reason] 分析数据质量 → data_profile, suggestions
  > ← synthetic_data
  > 分析维度：缺失率、分布类型、异常值比例
3. [subtask] 清洗数据 → cleaned_data
  > ← data_profile, suggestions
  > 按 LLM 建议执行清洗策略
```

折叠渲染（/showplan 输出）：
```
1  [x]  [ACT]      生成合成保单数据 → synthetic_data | 生成 10K 行
2  [>]  [REASON]   分析数据质量 → data_profile, suggestions
                   > ← synthetic_data
                   > 分析维度：缺失率、分布类型、异常值比例
3  [ ]  [SUBTASK]  清洗数据 → cleaned_data
```

---

## Think 反思协议

PlanSpec 在 think 模式（`subtask(think)`）下驱动迭代推理。反思不是独立阶段——它嵌在每一步的执行中。

### 设计原理

LLM API 是无状态的，每次调用都重发完整上下文。`hop_get` 通过 session 的 `run_history` 携带前序步骤的执行记录，因此 LLM 在执行每步时**已经具备隐式反思能力**——它能看到之前做了什么、结果如何。

引擎的职责不是"替 LLM 反思"，而是：
1. **确保上下文可用**（run_history 已做到）
2. **在失败信号出现时干预**（而不是盲目继续）
3. **提供结构化计划视图**（history 有原始执行记录，但缺少计划全局状态）

### 反思触发

每步执行后，引擎检查算子返回的 `HopStatus`：

| HopStatus | 触发反思 | 含义 |
|-----------|:--------:|------|
| `OK` | 否 | 正常完成，继续下一步 |
| `FAIL` | **是** | 执行失败（传输/核验/工具） |
| `UNCERTAIN` | **是** | 结果不确信 |
| `LACK_OF_INFO` | **是** | 信息不足 |

触发条件：`status != OK`。

### 反思输入

反思时 LLM 收到的上下文：

| 输入 | 来源 | 说明 |
|------|------|------|
| `status` | 算子返回 | FAIL / UNCERTAIN / LACK_OF_INFO |
| `result` | 算子返回 | 具体错误信息或不确定内容 |
| `plan_state` | `serialize_plan(fold=True)` | 当前计划进度（折叠版） |
| `can_interact` | 运行模式（metainfo） | 环境：能否向用户提问 |

### 反思输出

LLM 基于上下文自主决策。决策分两类：

**引擎动作**（LLM 通过结构化返回指示引擎执行）：

| 决策 | 含义 | 适用场景 |
|------|------|---------|
| RETRY | 重新执行当前步骤 | FAIL + 瞬态错误，UNCERTAIN + 下游强依赖 |
| ACCEPT | 接受当前结果，继续 | UNCERTAIN + 下游不敏感 |
| INTERACT | 上报用户请求输入 | LACK_OF_INFO + 可交互 |

**PLAN_CMD 命令**（修改计划结构）：

| 命令 | 含义 | 适用场景 |
|------|------|---------|
| SKIP | 跳过当前步骤 | FAIL + 不可恢复 |
| REVISE | 修订后续步骤适应缺失 | 前序步骤失败/跳过，下游需调整 |
| ADD | 插入补救/替代步骤 | LACK_OF_INFO + 批量模式，需换路径 |

**关键设计**：决策由 LLM 在计划上下文中判断，而非引擎硬编码。引擎只负责检测信号、提供上下文、执行决策/命令。

### 步骤反思 vs 轮末重规划

| 机制 | 触发时机 | 范围 | 作用 |
|------|---------|------|------|
| **步骤反思** | `status != OK`（每步之后） | 当前步骤 + 后续调整 | 即时响应失败 |
| **轮末 re-plan** | 一轮步骤全部执行完、未收敛 | 整个计划 | 结构性调整的兜底 |

步骤反思处理局部问题（单步失败的即时应对），re-plan 处理全局问题（整体方向偏移、多步连锁失败）。两者互补，不替代。

---

## 数据模型

### PlanStatus

```python
class PlanStatus(str, Enum):
    PENDING = "pending"     # 待执行
    ACTIVE = "active"       # 进行中
    DONE = "done"           # 已完成
    BLOCKED = "blocked"     # 阻塞
    SKIPPED = "skipped"     # 跳过
```

### PlanStep

```python
@dataclass
class PlanStep:
    step_id: str                              # "1", "2.1"
    step_name: str = ""                       # 可选唯一标识（LLM 生成时省略，外部工具可注入）
    step_type: str = ""                       # reason/act/decide/subtask
    description: str = ""                     # 面向 LLM 的描述性任务说明
    inputs: list[str] = field(default_factory=list)   # ← 输入变量（节点体声明）
    outputs: list[str] = field(default_factory=list)  # → 输出变量（摘要行声明）
    detail: list[str] = field(default_factory=list)   # > 节点体展开细节
    result: str = ""                          # 实际完成情况（执行后填写）
    status: PlanStatus = PlanStatus.PENDING
    expanded: bool | None = None              # 渲染控制（瞬态，不序列化/解析）
    done_count: int = 0                       # 已完成轮次
    total_count: int | None = None            # 总轮次（None=非循环）
    children: list[PlanStep] = field(default_factory=list)
```

### PlanSpec

```python
@dataclass
class PlanSpec:
    title: str = ""
    goal: str = ""
    goal_detail: list[str] = field(default_factory=list)  # > 续行（Goal 的补充说明）
    constraints: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)

    @property
    def progress(self) -> dict[str, int]:
        """返回 {"total": N, "done": N, "active": N, "blocked": N, "pending": N, "skipped": N}"""

    @property
    def is_converged(self) -> bool:
        """步骤状态收敛：无 PENDING 或 ACTIVE 步骤"""
```

`progress` 递归计算所有步骤（含嵌套 children）的状态统计。

`is_converged` 放宽收敛条件：BLOCKED 步骤视为已处理（re-plan 已尝试但未解决），只要没有待执行或正在执行的步骤就算步骤层面收敛。引擎层还需检查输出收敛——parent_step 的必要 outputs 是否已产出。

---

## API

所有函数位于 `hop_engine.jit.plan_spec` 模块，从 `hop_engine.jit` 顶层导出。

### parse_plan

```python
def parse_plan(text: str) -> PlanSpec
```

将 PlanSpec 紧凑格式文本解析为 `PlanSpec` 实例。

- 空字符串返回空的 `PlanSpec()`
- **step ID 编码树结构**：`2.1` 自动成为 `2` 的子步骤（不依赖缩进或 heading level）
- 状态标记可选，缺省为 `PENDING`
- `→ outputs` 从描述末尾提取到 `outputs` 字段
- `> ← inputs` 从节点体中提取到 `inputs` 字段（并从 detail 中移除）
- `>` 行收集到 `detail` 字段
- `|` 分隔 result 和 Progress

### serialize_plan

```python
def serialize_plan(plan: PlanSpec, *, fold: bool = False) -> str
```

将 `PlanSpec` 实例序列化为紧凑格式文本。

- `fold=False`（默认）：完整输出，与 `parse_plan` 互为逆操作（roundtrip 保真）
- `fold=True`：按 `expanded` 标志 + status 规则控制 detail/children 可见性（用于 LLM 上下文注入）

```python
plan == parse_plan(serialize_plan(plan))  # roundtrip (fold=False)
```

序列化规则：
- `PENDING` 状态省略标记
- `→ outputs` 追加在 description 之后、`|` 之前
- `← inputs` 序列化为节点体第一行 `> ← var1, var2`
- `detail` 序列化为 `> line` 行（在 `← inputs` 之后）
- `result` 为空时省略
- `done_count == 0` 且 `total_count is None` 时省略 Progress
- 子步骤缩进 2 空格/层（视觉辅助）
- 结果以换行符结尾

`fold=True` 时的折叠规则：
- `expanded=False`：摘要行可见，detail + children 全部隐藏
- `expanded=True`：detail + children 全部显示
- `expanded=None`：按 status 默认规则（active/blocked 展开 detail，其他折叠；children 始终显示）

### validate_plan

```python
def validate_plan(plan: PlanSpec) -> list[str]
```

6 项检查，返回错误/告警信息列表（空列表表示通过）：

| # | 检查项 | 级别 | 信息示例 |
|---|--------|------|---------|
| 1 | 步骤非空 | 错误 | `plan has no steps` |
| 2 | 步骤类型合法 | 错误 | `step 1 (foo): invalid type 'LLM'` |
| 3 | 步骤名称全局唯一（空名跳过） | 错误 | `step 2 (bar): duplicate name, first seen at step 1` |
| 4 | 容器约束 | 错误 | `step 1 (foo): type 'reason' cannot have children` |
| 5 | 目标非空 | 错误 | `plan has no goal` |
| 6 | 结构完整性（subtask/decide 应有 children） | 告警 | `warn: step 1 (foo): type 'subtask' has no children` |

告警以 `warn:` 前缀区分，不影响合法性判定。名称唯一性、容器约束和结构完整性均递归检查所有嵌套层级。

### expand_step / collapse_step

```python
def expand_step(plan: PlanSpec, step_id: str) -> str
def collapse_step(plan: PlanSpec, step_id: str) -> str
```

显式控制步骤的折叠/展开状态，覆盖默认的 status 规则。返回空字符串表示成功，非空为错误信息。

- `expand_step`：设置 `expanded=True`，强制显示 detail + children
- `collapse_step`：设置 `expanded=False`，强制隐藏 detail + children

`expanded` 是瞬态标志，不影响 plan 数据，不参与序列化/解析。仅在 `serialize_plan(fold=True)` 时生效。

EXPAND/COLLAPSE 是**视图操作**（面向人类用户和工具），不通过 LLM 命令协议触发。LLM 在步骤反思和轮末重规划中仅使用结构性命令（ADD/REVISE/REPLAN）。

### replace_children

```python
def replace_children(plan: PlanSpec, step_id: str, new_children: list[PlanStep]) -> str
```

替换指定容器步骤的子步骤列表。用于子树 REPLAN 的第二阶段：引擎生成新的子步骤后，替换到目标容器中。

- 目标步骤必须是 `subtask` 或 `decide` 类型
- 替换后目标步骤状态设为 `ACTIVE`
- 使用列表副本，不共享引用

### 命令协议（PLAN_CMD）

PlanSpec 的修改操作按**职责**分为三层，每层有明确的触发者和触发时机：

| 层 | 职责 | 触发者 | 操作 |
|----|------|--------|------|
| **引擎层** | 步骤状态管理 | HOP 引擎自动 | DONE / BLOCKED / SKIP |
| **LLM 层** | 计划结构修订 | LLM 在步骤反思 / 轮末重规划 | ADD / REVISE / REPLAN |
| **视图层** | 折叠/展开控制 | 用户或工具（`/showplan`） | EXPAND / COLLAPSE |

#### 引擎层——状态管理（自动）

引擎在步骤执行过程中自动管理状态转换，LLM 不需要发出这些命令：

```
PLAN_CMD: DONE <step_id> | <结果摘要>
  — 步骤执行成功后，引擎自动标记为 done

PLAN_CMD: BLOCKED <step_id> | <阻塞原因>
  — 步骤执行失败或前置依赖未满足时，引擎自动标记为 blocked

PLAN_CMD: SKIP <step_id> | <跳过理由>
  — 步骤被跳过（如分支条件不满足），引擎自动标记为 skipped
```

#### LLM 层——结构修订（步骤反思 + 轮末重规划）

引擎在两个时机调用 LLM 修订计划：**步骤反思**（`status != OK` 时立即触发）和**轮末重规划**（一轮未收敛时触发）。两个阶段都将当前计划状态 + 可用命令列表注入 prompt，LLM 通过 `PLAN_CMD:` 行式命令修订计划结构，引擎确定性执行。命令以 `PLAN_CMD:` 前缀标识，每行一条，引擎忽略非 `PLAN_CMD:` 开头的行（LLM 推理文本不影响解析）。

```
PLAN_CMD: ADD 2.3 [reason] 验证清洗后数据无空值且行数 ≥ 原始 95%
> ← cleaned_data, raw_data
> 检查空值率 < 0.1%，行数保留率 >= 95%
  — 在 step 2.3 位置插入新步骤，[type] 指定步骤类型，后跟完整描述。
    任务信息超过单行时，紧跟 > 开头的续行作为节点体（detail），
    提供约束、输入声明、执行提示

PLAN_CMD: REVISE 3.1 [reason] 分析特征相关性矩阵，识别冗余特征 → feature_analysis
> ← feature_matrix
> 输出冗余特征列表和建议删除理由
  — 替换步骤的类型、描述和节点体（整行替换）。
    紧跟 > 续行替换目标步骤的 detail；不带 > 续行则保留原有 detail

PLAN_CMD: REPLAN 4 | 模型迭代策略失效，需重新分解子步骤
  — 清空容器步骤 4 的所有子步骤，引擎将重新生成。仅限 subtask/decide 容器

PLAN_CMD: REPLAN ALL | 目标理解偏差，需从头重新规划
  — 丢弃整个计划，引擎完全重新生成。必须写 ALL，裸 REPLAN 会被忽略
```

**安全设计**：全局 REPLAN 要求显式 `ALL` 关键字，避免误操作。裸 `REPLAN`（无 step_id 也无 ALL）被静默跳过并记录 debug 日志。

#### 视图层——折叠/展开（用户/工具）

EXPAND/COLLAPSE 是**视图操作**，由用户或工具（如 `/showplan`）通过 API 调用，控制渲染时的 detail/children 可见性。不通过 LLM 命令协议触发。

```python
expand_step(plan, "4")    # 展开步骤 4 的节点体和子步骤
collapse_step(plan, "3")  # 折叠步骤 3，隐藏 detail 和 children
```

详见 [折叠规则](#折叠规则) 和 [expand_step / collapse_step](#expand_step--collapse_step) API。

### PlanCommand

```python
@dataclass
class PlanCommand:
    op: str              # DONE/BLOCKED/SKIP/ADD/REVISE/REPLAN/EXPAND/COLLAPSE
    step_id: str = ""    # 目标步骤 ID（REPLAN 时可为 "ALL"）
    step_type: str = ""  # 步骤类型（ADD/REVISE 用）
    description: str = ""  # 描述（ADD/REVISE 用）
    result: str = ""     # 结果/原因（DONE/BLOCKED/SKIP/REPLAN 用）
    detail: list[str] = field(default_factory=list)  # > 续行节点体（ADD/REVISE 用）
```

解析后的命令数据模型。`op` 是 8 种合法操作之一，按职责分三组：

| 组 | 操作 | 触发者 | 用途 |
|----|------|--------|------|
| 引擎层 | DONE / BLOCKED / SKIP | 引擎自动 | 步骤状态管理 |
| LLM 层 | ADD / REVISE / REPLAN | LLM 步骤反思 / 轮末重规划 | 计划结构修订 |
| 视图层 | EXPAND / COLLAPSE | 用户/工具 | 折叠/展开控制 |

### parse_plan_commands

```python
def parse_plan_commands(text: str) -> list[PlanCommand]
```

从 LLM 输出文本中提取 `PLAN_CMD:` 前缀的行式命令，忽略其他文本（LLM 推理内容）。

- 只识别 `PLAN_CMD:` 开头的行
- 不合法的操作动词被静默跳过
- `REPLAN ALL` 中的 `ALL` 关键字不区分大小写

### apply_command / apply_commands

```python
def apply_command(plan: PlanSpec, cmd: PlanCommand) -> str
def apply_commands(plan: PlanSpec, commands: list[PlanCommand]) -> list[str]
```

确定性执行一条或批量命令。就地修改 `plan` 实例。

- 返回值：空字符串/空列表表示成功，非空为错误信息
- 全局 `REPLAN`（无 step_id 或 step_id="ALL"）不在此处执行——返回空字符串，由引擎层协调重新生成
- 子树 `REPLAN <step_id>`：清空目标容器的 children，状态重置为 PENDING

### plan_to_steps

```python
def plan_to_steps(plan: PlanSpec) -> list[StepInfo]
```

将 PlanSpec 转换为 HopSpec 的 `StepInfo` 列表，用于 HopSpec 互操作。

**转换规则**：

| PlanStep type | → StepInfo type | 转换逻辑 |
|---------------|-----------------|----------|
| `reason` | `LLM` | `task=description`, `verifier=""` |
| `act` | `code` | `description=description` |
| `decide` | `branch` | `condition=description`, children 递归 |
| `subtask` | `subtask` | `expand_mode="static"`, children 递归 |

**数据流传递**：`inputs` 和 `outputs` 直接传递到 StepInfo 对应字段。

无名步骤自动生成 `step_name`：`step_1`、`step_2_1` 等（step_id 中的 `.` 替换为 `_`）。

末尾自动追加 `flow:exit`（`EXIT_OK`），如果最后一步不是 `flow` 类型。

### steps_to_plan

```python
def steps_to_plan(
    steps: list[StepInfo],
    title: str = "",
    goal: str = "",
    constraints: list[str] | None = None,
) -> PlanSpec
```

将 HopSpec 的 `StepInfo` 列表转换为 PlanSpec，生成 HopSpec 的简化规划视图。

**转换规则**：

| StepInfo type | → PlanStep type | 转换逻辑 |
|---------------|-----------------|----------|
| `LLM` | `reason` | `description=task`（核验策略是实现细节，不区分） |
| `code` | `act` | `description=description` |
| `call` | `act` | `description=task` |
| `branch` | `decide` | `description=condition` |
| `loop` | `subtask` | `description` 含遍历/条件信息 |
| `subtask` | `subtask` | `description=description` |
| `flow` | **跳过** | 流程控制是结构性的，非规划内容 |

**数据流保留**：`inputs` 和 `outputs` 从 StepInfo 直接传递到 PlanStep。

---

## 循环处理策略

PlanSpec 没有 `loop` 类型。循环场景有两种处理方式：

### 方案 A：展开为具体子步骤（优先）

将循环展开为 `subtask` + 具体 children，每个子步骤独立追踪 status：

```
1. [subtask] Process each item in batch → results
  1.1. [x] [act] Process item A → item_a
  1.2. [x] [act] Process item B → item_b
  1.3. [act] Process item C → item_c
```

适用于迭代次数已知、每个迭代有不同语义的场景。

### 方案 B：迭代计数

当迭代次数未知或子步骤同构时，用 `done_count` / `total_count` 追踪进度：

```
1. [subtask] Process each item in batch → results | Progress: 3/5
```

- `done_count`: 已完成的轮次
- `total_count`: 总轮次（`None` 表示未知）
- 序列化为 `| Progress: N/M`（total_count 已知）或 `| Progress: N`（未知）

---

## 与 HopSpec 的关系

### 双向转换

```
PlanSpec ──plan_to_steps()──→ StepInfo[] (HopSpec)
PlanSpec ←──steps_to_plan()── StepInfo[] (HopSpec)
```

转换会丢失信息：
- **Plan → Hop**：丢失 status、result、progress、detail（HopSpec 不追踪执行状态）
- **Hop → Plan**：丢失 return_format、verifier 细节、call_target、flow 步骤（PlanSpec 不关心实现细节）

双向转换保留**核心结构**（步骤层级、类型映射、输入输出）。

### 渐进固化路径

```
PlanSpec (完整规划)
    ↓ plan_to_steps() + 人工补充属性
HopSpec (可执行规范)
    ↓ /spec2code
Hop.py (可执行代码)
```

反方向用于观测：

```
Hop.py / HopSpec
    ↓ steps_to_plan()
PlanSpec (进度视图)
    ↓ /showplan
终端可视化
```

---

## 完整示例

```
# Plan: 车险赔付率预测
Goal: 基于合成保险数据，通过 XGBoost + LLM 迭代优化构建理赔预测模型
Constraints:
- 合成数据内置生成，不依赖外部文件
- polars 处理 DataFrame，XGBoost 做二分类
- 最多 5 轮迭代，目标 Gini ≥ 0.40
## Steps
1. [x] [act] 生成 10K 条合成保单数据，含 5% 缺失值和异常值噪声 → synthetic_data | 生成完成
  > 字段：policy_no, vehicle_age, driver_age, vehicle_value, annual_mileage,
  >   region(5类), vehicle_type(3类), driver_gender, years_licensed,
  >   previous_claims, premium, claim_flag, claim_amount
  > claim_flag 阳性率约 15%，claim_amount 服从 log-normal
2. [>] [reason] 分析数据分布和质量问题，给出清洗策略和特征工程建议 → data_profile, clean_suggestions, feature_suggestions
  > ← synthetic_data
  > 输出 data_profile 包含：各列缺失率、分布类型、异常值比例
  > clean_suggestions 为 action list，feature_suggestions 为 transform list
3. [subtask] 根据 LLM 画像建议清洗原始数据 → cleaned_data
  3.1. [reason] 确定具体清洗规则（缺失填充策略、异常截断阈值、类型修正） → cleaning_plan
    > ← data_profile, clean_suggestions
  3.2. [act] 对 synthetic_data 执行清洗计划，校验行数和空值率 → cleaned_data
4. [subtask] 基于清洗后数据构造预测特征 → feature_matrix
  4.1. [reason] 提出特征变换方案（交互项、分箱、编码）→ feature_plan
    > ← cleaned_data, feature_suggestions
  4.2. [act] 按方案构造特征矩阵，输出 polars DataFrame → feature_matrix
5. [subtask] 迭代训练 XGBoost 直到 Gini ≥ 0.40 或满 5 轮 → cv_metrics, feature_importance
  5.1. [x] [act] 训练 XGBoost 二分类器，5 折分层交叉验证 → cv_metrics | Gini=0.38, AUC=0.69
  5.2. [x] [act] 计算 Gini 系数、AUC、A/E ratio，提取特征重要性排名 → gini, auc, ae_ratio, feature_importance
  5.3. [>] [reason] 从 CV 指标和特征重要性诊断模型弱点，建议参数和特征调整方案 → diagnosis, param_adjustments
    > ← cv_metrics, feature_importance
    > 分析：过拟合（train/val gap）、特征冗余、类别不平衡
    > 建议：learning_rate/max_depth/reg_lambda 调整 + 特征增删
    > 输出 adjustments[]，每条含 param, current, suggested, reason
  5.4. [decide] 检查 Gini 是否达到目标阈值
    5.4.1. [act] Gini ≥ target → 跳出迭代进入报告
    5.4.2. [act] 应用参数调整方案，继续下一轮迭代
6. [act] 生成精算分析报告，涵盖模型性能、特征洞察和业务建议 → report
  > ← cv_metrics, feature_importance, data_profile, cleaning_plan, feature_plan
  > 报告结构：executive_summary + model_performance + feature_analysis
  >   + iteration_history + recommendations
  > Markdown 格式，含表格和关键指标高亮
7. [act] 组装最终输出并退出 → final_output
```

对应进度：

```
total: 14, done: 2, active: 2, blocked: 0, pending: 10, skipped: 0
```

---

## 验证规则速查

| # | 规则 | 级别 | 违反示例 |
|---|------|------|---------|
| 1 | 至少一个步骤 | 错误 | `steps: []` |
| 2 | 类型必须是 reason/act/decide/subtask | 错误 | `step_type: "LLM"` |
| 3 | step_name 全局唯一（含嵌套，空名跳过） | 错误 | 两个有名步骤都叫 `analyze` |
| 4 | 只有 subtask/decide 可有 children | 错误 | `reason` 带 children |
| 5 | goal 非空 | 错误 | `goal: ""` |
| 6 | subtask/decide 应有 children | 告警 | childless `subtask`（`warn:` 前缀） |

---

## 命令行工具

### 存储约定

PlanSpec 文件存储在项目根目录 `planspec/` 下（.gitignore 保护，纯本地工作区）。每个 plan 一个 `.md` 文件，文件名为 snake_case（如 `implement_auth.md`）。已完成的 plan 可归档到 `planspec/archive/`。

`Tasks/<name>/plan.md` 用于 Task 级别的 plan（与 Task 生命周期绑定），不受 `planspec/` 管理。两者共存互不冲突。

### /planspec

```
/planspec <description>          # 创建新 plan（先交流确认，再生成）
/planspec <name>                 # 继续/查看已有 plan
```

创建时写入 `planspec/<name>.md`。查看时从 `planspec/` 下匹配文件名加载。

### /listplan

```
/listplan                        # 列出 planspec/ 下所有 plan 概览
```

扫描 `planspec/*.md`，解析每个文件的 title、goal、progress，输出紧凑列表。

### /archiveplan

```
/archiveplan <name>              # 归档已完成的 plan
```

将 `planspec/<name>.md` 移动到 `planspec/archive/<name>.md`。

### /showplan

```
/showplan <name_or_path>
```

在终端以级联树状结构展示 PlanSpec，复用 `/showspec` 的可视化风格。查找路径优先级：`planspec/<name>.md` → `Tasks/<name>/plan.md` → 作为文件路径直接加载。

type badge 映射：

| step_type | badge |
|-----------|-------|
| reason | `[REASON]` |
| act | `[ACT]` |
| decide | `[DECIDE]` |
| subtask | `[SUBTASK]` |

**折叠规则**：渲染时按状态折叠节点体（见"折叠规则"章节）。`→ outputs` 始终显示在摘要行中。

输出示例：

```
═══ PlanSpec: 车险赔付率预测 ═══

Goal: 基于合成保险数据，通过 XGBoost + LLM 迭代优化构建理赔预测模型

Constraints:
  - 合成数据内置生成
  - polars + XGBoost

Progress: 2/14 (14%)

1  [x]  [ACT]      生成 10K 条合成保单数据 → synthetic_data | 生成完成
2  [>]  [REASON]   分析数据分布和质量问题 → data_profile, clean_suggestions, feature_suggestions
                   > ← synthetic_data
                   > 输出 data_profile 包含：各列缺失率、分布类型、异常值比例
3  [ ]  [SUBTASK]  根据 LLM 画像建议清洗原始数据 → cleaned_data
├─ 3.1  [ ]  [REASON]   确定具体清洗规则 → cleaning_plan
└─ 3.2  [ ]  [ACT]      对 synthetic_data 执行清洗计划 → cleaned_data
...

───
步骤: 14 | reason: 4 | act: 6 | decide: 1 | subtask: 3
进度: 2/14 (14%)
```

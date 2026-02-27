# HopSpec vs Kiro Spec：两种 Spec-Driven Development 的设计路线

## 引言

[Kiro](https://kiro.dev/) 是 Amazon 推出的 AI IDE，其核心特性是 **Spec-Driven Development**（规范驱动开发）——用结构化的 requirements / design / tasks 三文件替代传统的 chat-driven 开发。HopSpec 是 HOP 框架的任务规范格式，用 7 种原子步骤类型组成的结构化树描述 LLM 推理流程，驱动代码生成与双向同步。

两者都反对"对着 AI 聊天写代码"，都主张用结构化规范提升 AI 编程质量。但从根本上，它们回答的是不同的问题：

- **Kiro Spec**：AI 如何理解我的需求，正确地写出代码？
- **HopSpec**：LLM 推理的每一步，如何保证可信可靠？

本文通过系统对比，阐述两种 Spec 的设计差异与互补关系。

---

## 1. 定位差异

### 1.1 Kiro Spec：软件需求管理的 AI 自动化

Kiro 的出发点是传统软件工程的 SDLC（Software Development Life Cycle）。它观察到 AI 编程助手的核心瓶颈不是代码生成能力，而是**需求理解的模糊性**——开发者在 chat 中描述需求，AI 边猜边写，结果偏离预期。

Kiro 的解法是在 AI 写代码之前，先建立结构化的需求契约：

```
用户想法 → requirements.md → design.md → tasks.md → 代码
```

每个阶段有明确的格式约束（EARS 记法、架构图、checkbox 任务列表），AI 在每个阶段的输出都是可审阅的文档产物，而非直接代码。

### 1.2 HopSpec：LLM 推理流程的执行规范

HopSpec 的出发点不是软件开发流程，而是 **LLM 的幻觉问题**。在金融、医疗等专业场景，LLM 的推理输出必须达到 99%+ 的可靠性。仅靠 prompt engineering 无法保证这一点——需要在程序层面对 LLM 的每个推理节点实施核验闭环。

HopSpec 的解法是用结构化程序骨架约束 LLM 的推理过程：

```
任务描述 → HopSpec.md（7 种原子步骤 + 核验策略）→ Hop.py（async 协程）→ 执行 + 逐步核验
```

Spec 不仅描述"做什么"，还描述"怎么验证 LLM 说的对不对"。

---

## 2. 文件结构对比

### 2.1 Kiro：三文件分离 + steering 上下文

```
.kiro/
├── specs/
│   └── <feature>/
│       ├── requirements.md    # 用户故事 + EARS 验收标准
│       ├── design.md          # 架构设计 + 错误处理 + 测试策略
│       └── tasks.md           # 扁平 checkbox 任务列表
├── steering/
│   ├── structure.md           # 代码架构分析
│   ├── tech.md                # 技术栈与模式
│   └── product.md             # 业务上下文
```

三个 spec 文件对应三个阶段（需求→设计→任务），关注点分离。steering 文档是 Kiro 自动生成的代码库理解，作为 AI 的背景上下文。

### 2.2 HopSpec：单文件六章节 + 元数据契约

```
Tasks/<TaskName>/Hoplet/
├── HopSpec.md         # 单文件：任务概述 + 输入定义 + 硬性约束 + 执行流程 + 输出格式 + 示例
├── metainfo.md        # 元数据契约（输入/输出 schema、运行模式、测试指标）
├── SKILL.md           # AgentSkills.io 互操作描述
└── Hop.py             # 从 HopSpec 生成的可执行代码
```

HopSpec 将所有信息聚合在一个 Markdown 文件中。它关注的不是"谁做什么"，而是"LLM 在哪个节点以什么方式推理、如何核验"。`metainfo.md` 承担类似 Kiro `requirements.md` 的契约角色，但更侧重数据 schema 而非用户故事。

---

## 3. 需求描述方式

### 3.1 Kiro：用户故事 + EARS 验收标准

Kiro 使用传统软件工程的用户故事格式，验收标准采用 EARS（Easy Approach to Requirements Syntax）记法：

```markdown
### Requirement 1: Product Search
**User Story:** As a shopper, I want to search for products by name,
so that I can quickly find items I'm looking for.

**Acceptance Criteria:**
- WHEN user enters a search term THE SYSTEM SHALL return matching products
- GIVEN no matching products WHEN search completes THEN display "No results found"
- WHEN search results exceed 20 items THE SYSTEM SHALL paginate results
```

EARS 的 WHEN/THEN 结构面向**用户可观测行为**——描述的是系统对外表现，不涉及内部实现。

### 3.2 HopSpec：领域约束 + 数据契约

HopSpec 不使用用户故事，而是直接声明领域约束和数据边界：

```markdown
## 输入定义
- `context_window`: 上下文/参考文档
- `model_output`: 大模型生成的推理或回答

## 硬性约束
- 即使是公认事实，只要 context_window 中未提及，必须标记为外部知识泄露
- 任何不能从前提严格推导出的步骤，必须标记为推导不连贯

## 输出格式
{"reliability_score": int, "hallucination_detected": bool, "errors": [...]}
```

HopSpec 的约束面向 **LLM 推理行为**——约束的不是系统外部表现，而是 LLM 在推理过程中必须遵守的规则。这些约束会被注入到 LLM 的 prompt 中，作为推理的硬边界。

### 3.3 差异本质

| 维度 | Kiro EARS | HopSpec 约束 |
|------|-----------|-------------|
| 约束对象 | 系统行为（用户视角） | LLM 推理（算子视角） |
| 验证时机 | 事后（测试） | 运行时（核验闭环） |
| 表达粒度 | 功能级（"搜索返回结果"） | 推理级（"未在上下文中出现的事实必须标记"） |
| 消费者 | AI 编程助手 + 人类审阅者 | HOP 引擎 + LLM prompt |

---

## 4. 执行流程表达

这是两者最根本的差异。

### 4.1 Kiro tasks.md：扁平 checklist

```markdown
# Implementation Plan
- [ ] 1. Set up database schema for products
    - Create products table with columns: id, name, price, category
    - Add full-text search index on name column
    - _Requirements: 1.1, 1.3_
- [ ] 2. Create search API endpoint
    - Add GET /api/products/search route
    - Implement query parameter validation
    - Add pagination with limit/offset
    - _Requirements: 1.1, 1.5, 2.1_
- [ ] 3. Build search results UI component
    - Create SearchResults React component
    - Implement empty state display
    - _Requirements: 2.1, 2.2, 3.1_
```

tasks.md 是一个**工作分解结构**（WBS）。每个条目是一个开发任务，AI 逐个执行，完成后勾选。任务之间的依赖关系隐含在顺序中，没有显式的控制流。

### 4.2 HopSpec 执行流程：结构化步骤树

```markdown
#### 步骤1: extract_atomic_facts
- 类型：LLM
- 任务：将模型输出拆解为独立的原子事实陈述
- 输出格式：{"claims": List[str]}
- 核验：无

#### 步骤2: check_grounding（loop）
- 类型：loop
- 遍历集合：atomic_claims
- 输出：grounding_errors

  #### 步骤2.1: judge_claim_source
  - 类型：LLM
  - 任务：判断该原子陈述的来源类型
  - 输出格式：{"verdict": str, "evidence": str}

#### 步骤3: check_logic
- 类型：LLM
- 任务：分析推理步骤间的推导关系

#### 步骤4: handle_inconsistency（branch）
- 类型：branch
- 条件：is_consistent == False

  #### 步骤4.1: list_conflicts
  - 类型：LLM
  - 任务：列出推理中的内部冲突

#### 步骤5: merge_errors
- 类型：code
- 逻辑：合并所有错误集合
```

HopSpec 执行流程是一棵**控制流树**。7 种原子步骤类型（LLM / call / loop / branch / code / flow / subtask）对应程序的基本构造块——顺序、循环、分支、子程序调用。树结构直接映射到 Python 的缩进块，禁止任何形式的跳转（goto）。

### 4.3 核心差异

| 维度 | Kiro tasks.md | HopSpec 执行流程 |
|------|--------------|-----------------|
| **结构** | 扁平列表（无嵌套） | 结构化树（loop/branch 嵌套任意深度） |
| **步骤类型** | 无类型区分 | 7 种原子类型，每种有固定属性集 |
| **控制流** | 隐含顺序 | 显式：for-each / while / if / exit / continue / break |
| **变量追踪** | 无（依赖自然语言描述） | 显式：每步声明输入/输出变量，数据流可静态审计 |
| **核验声明** | 无 | 每个 LLM 步骤可声明核验策略 |
| **代码映射** | AI 自由推断 | 确定性映射（LLM→hop_get, loop→for, branch→if） |
| **理论基础** | 工作分解结构（WBS） | 结构化程序定理（Bohm-Jacopini） |

**类比**：Kiro tasks.md 像是给施工队的**任务单**（"第一天浇地基，第二天砌墙"），HopSpec 像是**建筑图纸**（"这里是承重墙，那里是管道走向，每根钢筋的强度标准是多少"）。

---

## 5. 核验与可靠性保障

### 5.1 Kiro：事后测试

Kiro 在 `design.md` 中包含测试策略，但核验发生在代码生成之后：

```
AI 生成代码 → 运行测试 → 发现问题 → 修改 Spec → 重新生成
```

Kiro 的 Spec 是 AI 的"上下文参考"——AI 读取 Spec 理解需求，但 Spec 本身不参与运行时验证。代码质量依赖 AI 的代码生成能力和测试覆盖率。

### 5.2 HopSpec：运行时逐步核验

HopSpec 的核验是**声明在 Spec 中、执行在运行时**的：

```markdown
#### 步骤3: check_logic
- 类型：LLM
- 任务：分析推理步骤间的推导关系
- 核验：逆向核验
```

这一行 `核验：逆向核验` 意味着：

1. 执行 LLM（run_llm）生成推理结果
2. 格式核验器检测序列化残留（纯本地，零 LLM 开销）
3. 独立的核验 LLM（verify_llm）反向验证结果正确性
4. 核验失败 → 注入反馈 → 自动重试（最多 hop_retry 次）
5. LLM 自报告置信度（OK / LACK_OF_INFO / UNCERTAIN），低置信触发反馈循环

```
LLM 生成结果 → format_verifier → 语义核验 → 失败 → 注入反馈 → 重试
                                           → 成功 → 继续下一步
```

核验不是"事后测试"，而是**每个 LLM 推理节点的内置质量门**。

### 5.3 对比

| 维度 | Kiro | HopSpec |
|------|------|---------|
| 核验时机 | 代码生成后（测试阶段） | 每步 LLM 调用时（运行时） |
| 核验对象 | 生成的代码是否满足验收标准 | LLM 每步输出是否正确 |
| 核验方式 | 单元测试 / 集成测试 | 逆向核验 / 正向交叉核验 / 工具核验 / 格式核验 |
| 失败处理 | 修改 Spec 重新生成 | 自动重试 + 反馈注入 |
| 置信度机制 | 无 | OK / LACK_OF_INFO / UNCERTAIN 三级自报告 |
| 幻觉防御 | 依赖测试覆盖 | 结构化输出 + 序列化残留检测 + 语义核验 |

---

## 6. 代码生成与双向同步

### 6.1 Kiro：任务驱动的自由生成

Kiro 的代码生成是 **AI 自由推断**的过程。AI 读取 tasks.md 中的 checkbox 描述，结合 steering 文档（代码架构、技术栈）生成实现代码。生成的代码与 Spec 之间没有结构化的映射关系——Spec 是"指导"，不是"蓝图"。

迭代方式：修改 requirements.md → 点击 "Refine" → Kiro 自动更新 design.md 和 tasks.md → 重新执行任务。这是**单向精化**——Spec 到代码的信息流是单向的。

### 6.2 HopSpec：确定性映射 + 双向同步

HopSpec 的每种步骤类型有精确的代码模式映射：

| Spec 步骤类型 | Python 代码 |
|-------------|------------|
| `LLM`（提取/分析语义） | `await s.hop_get(task=..., return_format=...)` |
| `LLM`（判断/核实语义） | `await s.hop_judge(task=...)` |
| `call`（工具调用） | `await s.hop_tool_use(task=..., tool_domain=...)` |
| `loop`（遍历） | `for item in collection:` |
| `branch`（条件） | `if condition:` |
| `code`（纯计算） | Python 赋值/计算 |
| `flow: exit` | `session.hop_exit(...); return` |

步骤的 `step_name` 作为代码中的锚点注释：`# 步骤N: step_name -- type -- task`。这使得 Spec 和 Code 之间可以**双向同步**：

```
HopSpec.md ──/specsync──→ Hop.py     # Spec 变更增量同步到 Code
HopSpec.md ←──/code2spec── Hop.py     # Code 变更反向同步到 Spec
HopSpec.md ←─/specdiff──→ Hop.py     # 对比差异（只读）
```

双向同步意味着开发者既可以先改 Spec 再同步代码，也可以先在 debug 中改代码再回写 Spec。`/verifyspec` 还提供 6 项自动审计（结构完整性、数据流追踪、核验策略审阅等），在 Spec 层面就能发现问题。

---

## 7. 执行模式

| 维度 | Kiro | HopSpec |
|------|------|---------|
| AOT/JIT | 仅 AOT（预定义任务列表） | AOT + JIT 双模式 |
| 子任务 | 无 | subtask 3 种展开：static / dynamic / think（历史别名 `seq_think` 保持兼容） |
| 运行模式 | 单一（开发时执行） | 交互 / 批量双模式 |
| 渐进固化 | 无 | think 成功路径 → dynamic 固化 → static 预定义 |

HopSpec 的 JIT 模式允许运行时动态决定下一步——LLM 根据当前状态选择步骤类型和参数。think 的六阶段有序思考（分解→规划→执行+监控→反思→修正→综合）提供了探索性任务的执行框架，成功路径可逐步固化为确定性流程。

这种渐进固化（JIT → AOT）是 HOP "越用越确定、越可靠"理念在 Spec 层的体现。Kiro 没有类似机制。

---

## 8. 理论根基

### 8.1 Kiro：软件工程最佳实践

Kiro 的设计植根于传统软件工程方法论：

- **用户故事**（User Stories）来自敏捷开发
- **EARS 记法**（Easy Approach to Requirements Syntax）来自需求工程
- **架构文档**来自 SAD（Software Architecture Document）传统
- **任务分解**来自 WBS（Work Breakdown Structure）

Kiro 用 AI 自动化了这些已被验证的工程实践，让 AI 编程助手在结构化需求的约束下工作，而非自由发挥。

### 8.2 HopSpec：结构化程序定理

HopSpec 的设计植根于计算机科学的基础理论：

- **Bohm-Jacopini 定理**：任何可计算函数都能用顺序、循环、分支三种结构表达，无需 goto
- **7 种原子步骤** = 顺序执行 + loop（循环）+ branch（分支）+ flow（控制转移）+ LLM/call/code（原子操作）+ subtask（子程序）
- **禁止跳转**：与 Python 块结构一致，控制流完全由层级嵌套 + 顺序执行决定

这意味着 HopSpec 的表达能力与 Python 等价——任何 Python 程序的控制流都能用 HopSpec 表达，反之亦然。这不是巧合，而是设计目标：HopSpec 是 Python 控制流的 Markdown 表示。

与之对比，Kiro 的 tasks.md 仅是一个有序列表，不具备控制流表达能力。循环、条件、子程序调用等概念在 tasks.md 中无法表达——它们被推迟到代码生成阶段由 AI 自由推断。

---

## 9. 互补关系

Kiro Spec 和 HopSpec 解决的是**不同层面**的问题：

```
Kiro 层：需求理解 → 架构设计 → 任务分解
                                    ↓
HopSpec 层：               LLM 推理流程 → 核验策略 → 可执行代码
```

一个 Kiro tasks.md 中的条目完全可以是：

```markdown
- [ ] 5. Implement hallucination detection using HOP framework
    - Create HopSpec for 3-stage verification (grounding + logic + consistency)
    - Generate Hop.py with /spec2code
    - Run batch tests with /batchhoptest
    - _Requirements: 3.1, 3.2, 3.3_
```

Kiro 管"开发流程中 AI 如何理解需求"，HopSpec 管"运行时 LLM 推理如何保证可靠"。前者是开发阶段的质量控制，后者是运行阶段的质量控制。

### 总结

| 维度 | Kiro Spec | HopSpec |
|------|-----------|---------|
| **一句话** | 用结构化需求替代 AI chat | 用结构化程序骨架约束 LLM 推理 |
| **本质** | 需求管理框架 | 执行规范 |
| **粒度** | 功能级（"创建搜索 API"） | 推理级（"提取原子事实 → 逐条核验 → 评分"） |
| **控制流** | 无（扁平 checklist） | 结构化树（7 种原子步骤类型） |
| **核验** | 事后测试 | 运行时逐步核验 |
| **信任模型** | 信任 AI 生成代码 | 不信任 LLM 输出 |
| **代码映射** | AI 自由推断 | 确定性映射 + 双向同步 |
| **迭代** | 单向精化（Spec → Code） | 双向同步（Spec ↔ Code） |
| **理论基础** | 软件工程最佳实践 | 结构化程序定理 |
| **适用层** | 软件开发全流程 | LLM 推理流程编排 |

---

## 参考资料

- [Kiro Specs Documentation](https://kiro.dev/docs/specs/)
- [Kiro Best Practices](https://kiro.dev/docs/specs/best-practices/)
- [From Chat to Specs: A Deep Dive — Kiro Blog](https://kiro.dev/blog/from-chat-to-specs-deep-dive/)
- [Understanding Spec-Driven Development — Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [HopSpec 格式规范](HopSpec格式规范.md)
- [HOP 高阶程序](HOP高阶程序.md)
- [HOP vs Burr](HOP%20vs%20Burr.md)

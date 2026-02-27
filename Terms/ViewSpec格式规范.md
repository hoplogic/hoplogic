# ViewSpec 格式规范

## 设计动机

**ViewSpec 以与 HopSpec 一脉相承的简洁格式组织和约束 UI 交互逻辑，让人轻松定制，让 AI 准确实现。**
**HopSpec 的核心是结构化编程，ViewSpec 的核心是组件封装与事件驱动。**

**一脉相承**：同样是 Markdown、编号步骤、原语驱动——会 HopSpec 就会 ViewSpec。HopSpec 用 `LLM`/`call`/`branch`/`loop` 描述执行流，ViewSpec 用 `render`/`call`/`branch`/`emit` 描述交互流，格式相同，语义对偶，无额外学习成本。从设计到实现同样平滑——先想清楚界面分几块、展示什么数据，再定义各块之间怎么通信，最后细化每个交互的具体步骤。每一层粒度都是可用的设计产物，下一层在上一层基础上展开，不存在断层。到实现时，每条声明都有确定的代码生成目标，AI 逐项映射即可，不需要推断或脑补。

**人与 AI 的分工**：人关注设计决策——界面布局、数据展示、交互行为；AI 关注实现机制——异步调度、状态同步、样式渲染。每个文件决策在前、细节在后，人读完决策即可停止，AI 从头到尾全读。

### 借鉴来源

| 来源 | 借鉴点 |
|------|--------|
| [JSON Schema Form](https://rjsf-team.github.io/react-jsonschema-form/) | 数据 Schema 与 UI Schema 分离 |
| [W3C Design Tokens](https://design-tokens.github.io/community-group/format/) | 设计变量抽象为 token |
| [HopSpec](./HopSpec格式规范.md) | Markdown 格式、编号步骤、原子原语 |

---

## 核心概念

### 设计哲学

**HopSpec 的核心是结构化编程，ViewSpec 的核心是组件封装与事件驱动。**

HopSpec 将 LLM 智能置于确定性程序骨架的受控节点中，通过算子、步骤、核验构成结构化执行流。ViewSpec 的对偶在于：将 UI 组件封装为**相互隔离的交互分区（Zone）**——每个 Zone 拥有自己的界面元素和状态，Zone 间通过**消息事件**通信，禁止直接操作其他 Zone 的内部状态。

| 范式 | 核心单元 | 组合机制 | 约束手段 |
|------|---------|---------|---------|
| HopSpec（结构化编程） | 原子步骤（LLM/call/loop/...） | 步骤序列 + 控制流 | 核验闭环（逆向/正向/工具） |
| ViewSpec（组件封装+事件） | Zone（隔离的交互分区） | 消息事件传递 | 边界封装（状态私有、接口公开） |

**三条边界规则**：

1. **Zone 拥有自己的 DOM 子树和状态** — 外部代码不得直接读写 Zone 内部元素或变量
2. **Zone 间通过消息事件通信** — Zone 通过 `emit` 发出事件，通过 `on` 接收事件。不允许 Zone A 直接 `set Zone B 内部的 #element`
3. **Zone 同一时刻至多执行一个异步协程** — 异步 `call` 直接内嵌在事件步骤序列中（与 HopSpec 一致），Zone 保证同一时刻只有一个协程事件在执行。等待期间自身可显示进展、可中止，也可执行其他未被 guard 禁用的同步事件

### ViewSpec 与 HopSpec 的对比

| 维度 | HopSpec | ViewSpec |
|------|---------|----------|
| 描述对象 | 后端执行逻辑 | 前端 UI 交互 |
| 输入来源 | 任务描述（SOP 原文） | 数据契约（输入/输出字段）+ 执行逻辑（状态分支）|
| 生成目标 | 单文件可执行代码 | 多文件 UI 工程 |
| 核心抽象 | 7 种原子步骤类型（结构化编程） | Zone + 消息事件（组件封装+事件驱动）|
| 锚点机制 | step_name（Spec↔Code 对齐） | zone_id + event_name + field_name |
| 交互模型 | coroutine 步骤树 | Zone 树 + 事件路由 |
| 异步处理 | async/await 协程 | coroutine 事件（`call` 内嵌步骤序列，单 Zone 单协程）|

### 目录结构

```
ViewSpec/
├── index.md           # 总览：Tab 列表 + Zone 索引 + API 适配 + 通用行为 + 原语定义 + 文件路由表
├── rendering.md       # 渲染映射：输入/输出字段 + 复合组件 + 结果归一化 + 统计聚合
├── theme.md           # 布局主题：Design Tokens + 布局尺寸 + CSS 类清单 + 动画
└── tabs/              # 交互流：每个 Tab 一个目录，每个 Zone 一个文件
    ├── main/          #   主功能 Tab（命名按应用场景，如 audit/, solve/, edit/）
    │   ├── _tab.md    #     Tab 总览：布局 + Zone 拓扑 + 事件路由表
    │   ├── InputForm.md     # Zone: 输入表单
    │   └── ResultArea.md    # Zone: 结果展示
    ├── settings/      #   设置 Tab（示例）
    │   ├── _tab.md
    │   └── SettingsForm.md
    └── ...
```

> **HOP 应用示例**：在 Hoplet 项目中，ViewSpec 通常放在 `Tasks/<TaskName>/View/ViewSpec/`，典型的 Tab 组合为 audit/batch/history/stats/perf 五个 Tab。

**设计原则**：

- **每个 Zone 独立文件** — Zone 是 ViewSpec 的核心单元，一个文件一个 Zone，独立维护、独立 diff
- **每个 Tab 一个目录** — Tab 目录下 `_tab.md` 声明布局和 Zone 间路由，其余文件各是一个 Zone
- **Zone 文件以 PascalCase 命名** — 与代码中的组件命名一致：`InputForm.md`、`DetailPane.md`
- **rendering.md 合并输入+输出+统计** — 它们紧密关联，分开反而增加跳转成本
- **theme.md 独立** — 跨任务几乎不变，独立便于复用/覆盖
- **index.md 是入口** — 包含元信息头、Tab 总览表、Zone 索引、通用行为和文件路由表，AI 读 ViewSpec 从这里开始

### 生成流水线

```
数据契约 + 执行逻辑 ──> ViewSpec/ ──> 代码生成 ──> UI 工程文件
                        (可手动编辑)
```

> **HOP 工具链**：`/code2viewspec` 从 metainfo.md + HopSpec.md 初始生成 ViewSpec，`/code2view` 从 ViewSpec 生成 View 代码，`/view2spec` 反向同步。

### ViewSpec 的双重角色

随着代码成熟度提升，ViewSpec 承担两种角色：

| 角色 | 适用对象 | ViewSpec 内容 | 工具链行为 |
|------|---------|-------------|-----------|
| **生成规格** | generated Zone（每个任务独立生成的代码） | 步骤序列是规范性的，定义"代码应该做什么" | `/code2view` 读取 → 生成代码 |
| **接口契约** | shared Zone（共享库中的固定代码） | 步骤序列是描述性的，记录"代码做了什么"；参数化接口声明定制能力 | `/code2view` 仅提取配置参数 |

同一个 ViewSpec 目录内可以混合两种角色的 Zone 文件（见 §2.1 Zone 的实现来源）。这与 HOP 引擎层的渐进固化理念一致——代码从"每次生成"渐进固化为"共享库"后，ViewSpec 自然从生成指令演进为接口契约。

---

## 一、总览（Hub Layer） — `index.md`

index.md 是 ViewSpec 入口，包含全局信息、文件路由表和文件索引。不包含具体 Tab 的交互细节（那些在 `tabs/*.md` 中）。

### 1.1 元信息头

声明 ViewSpec 的输入来源，便于追溯数据契约和执行逻辑：

```markdown
# ViewSpec: <AppName>

> 数据契约: <数据契约文件路径> -- 输入/输出字段
> 执行逻辑: <执行逻辑文件路径> -- 状态分支、交互流程（可选）
```

> **HOP 示例**：Hoplet 项目中通常为 `> 数据契约: Hoplet/metainfo.md` + `> 执行逻辑: Hoplet/HopSpec.md`。

### 1.2 Tab 列表

用表格列出所有 Tab，链接到对应描述文件：

```markdown
## Tab 列表

| # | tab_id | 名称 | 布局 | 描述目录 |
|---|--------|------|------|---------|
| 1 | **audit** | 执行 [默认] | form + result | [tabs/audit/_tab.md](tabs/audit/_tab.md) |
| 2 | **batch** | 批量 | form + progress | [tabs/batch/_tab.md](tabs/batch/_tab.md) |
| 3 | **history** | 历史 | sidebar + detail | [tabs/history/_tab.md](tabs/history/_tab.md) |
| 4 | **stats** | 统计 | grid | [tabs/stats/_tab.md](tabs/stats/_tab.md) |
| 5 | **perf** | 性能 | grid + table | [tabs/perf/_tab.md](tabs/perf/_tab.md) |
```

**布局模式**：

| 布局 | 说明 | 典型 Tab |
|------|------|---------|
| `form + result` | 上方表单，下方结果 | 执行 |
| `form + progress` | 上方配置，下方进度 | 批量 |
| `chat-flow` | 顶部输入 + 中部滚动消息流 + 底部反馈栏 | 交互求解 |
| `sidebar + detail` | 左侧列表（固定宽度），右侧详情 | 历史 |
| `grid` | 等宽网格卡片 | 统计 |
| `grid + table` | 卡片网格 + 数据表格 | 性能 |

可追加 **按需加载** 表，说明每个 Tab 切换时的数据请求策略：

```markdown
| Tab | 切换时触发 | 缓存 |
|-----|-----------|------|
| audit | 无（等待用户操作）| 无 |
| batch | `refreshBatchFiles()` | 每次重新加载 |
| history | `loadHistoryFiles()` | 每次重新加载 |
| stats | `loadProfileSelector()` + `loadStats()` | Profile 列表仅加载一次 |
| perf | `loadPerf()` | 每次重新加载 |
```

### 1.3 API 适配层

前端通过 HTMX 声明式属性直接发起 HTTP 请求，服务端返回 HTML fragments。无需 JS API 适配器。

```markdown
## API 适配层

前端通过 HTMX 声明式属性直接发起 HTTP 请求，服务端返回 HTML fragments。无需 JS API 适配器。

**端点映射**:

| API 方法 | 方式 | 端点 | 响应类型 |
|----------|------|------|---------|
| `runTask(input)` | POST | `/api/run` | HTML fragment |
| `listTestFiles()` | GET | `/api/test-files` | HTML fragment |
| `loadResult(name)` | GET | `/api/results/{name}` | HTML fragment |
| `getStats(profile?)` | GET | `/api/stats?profile=` | HTML fragment |
```

### 1.4 通用行为

适用于所有 Tab 的全局行为声明：

```markdown
## 通用行为

- **Error Overlay**: 底部固定红色面板，捕获 `window.error` + `unhandledrejection`，8 秒自动消失
- **错误边界**: Zone 事件处理中未捕获的异常由 Error Overlay 统一兜底，不影响其他 Zone 正常运行
- **长列表性能**: 滚动容器默认启用虚拟滚动；有特殊需求时在元素表说明列标注替代策略（分页 / 截断）
- **Loading**: spinner（16x16px 旋转圈，border-top accent 色）
- **文本可选**: body / textarea / result-card / json-block / err-table td/th 声明 `user-select:text`
- **HTML 转义**: 所有用户数据经 `esc()` 转义
```

### 1.5 交互原语

定义 Zone 文件中事件处理使用的原语。分为**步骤原语**（Zone 内操作）和**通信原语**（Zone 间消息）。

```markdown
## 步骤原语（Zone 内部操作）

| 原语 | 含义 | 示例 |
|------|------|------|
| `render` | 渲染内容到本 Zone 元素 | `render .content <- spinner` |
| `set` | 设置本 Zone 元素属性 | `set .btn-run <- disabled, text="Running..."` |
| `code` | 本地逻辑（计算、DOM 操作、fire-and-forget 调用） | `code pct = round(completed / total * 100)` |
| `branch` | 条件分支 | `branch files 为空 -> render ..., return` |
| `loop` | 遍历 | `loop file in files -> render .file-item(file.name)` |
| `timer` | 启动/清除定时器 | `timer 启动 _pollTimer = setInterval(..., 1000ms)` |

## 通信原语（Zone 间消息传递）

| 原语 | 含义 | 示例 |
|------|------|------|
| `emit` | 向外发出事件（路由表分发到目标 Zone）| `emit task_submit(desc, ctx)` |
| `call` | 异步 API 调用（await，Zone 在此挂起） | `call API.runTask({...}) -> r` |
```

**关键约束**：`render` 和 `set` 只能操作**本 Zone 内**的元素。操作其他 Zone 的状态必须通过 `emit` 发出事件，由目标 Zone 自行处理。

**render 三种子操作**：
- **替换**：`render .content <- spinner` — 清空元素内容后写入新内容
- **追加**：`render .chat-flow <- append .msg.msg-user(...)` — 在元素末尾追加子节点
- **移除**：`render 移除 .thinking` — 从 DOM 中移除匹配的子节点

**code 范围**：`code` 包含不涉及 API 调用的本地逻辑——纯计算（`pct = round(...)`）、DOM 查询/操作（`scrollToBottom`）、状态更新（`_retryCount++`）。也用于 fire-and-forget 的异步调用——不等待返回、不挂起 Zone：`code API.cancelTask({...})（fire-and-forget）`。

**多路 branch**：当分支超过两条时，使用冒号引出分支列表，每条分支缩进，可含编号子步骤：

```markdown
5. branch r.hop_status:
   - "OK":
     1. render .content <- ConfirmedCard(r)
     2. emit hide_feedback
   - "UNCERTAIN":
     1. render .content <- SolutionCard(r)
     2. emit show_feedback("feedback")
   - "FAIL":
     1. render .content <- ErrorCard(r)
     2. emit show_feedback("retry")
```

双路分支可用 `->` 简写：`branch r.error -> render error-card; return`。

**编号约定**: 步骤使用连续整数编号（1, 2, 3...）。手工插入新步骤时用字母后缀（如在 2 和 3 之间插入 `2a`, `2b`），无需重编号后续步骤。AI 处理时自动重排为干净的连续编号。

### 1.6 文件索引

列出 ViewSpec 目录下所有文件，便于导航。Zone 文件在各 Tab 的 `_tab.md` 中索引。

```markdown
## 文件索引

- [rendering.md](rendering.md) -- 渲染映射（输入/输出字段 + 复合组件 + 统计聚合）
- [theme.md](theme.md) -- 布局主题（Design Tokens + 布局尺寸 + CSS 类清单 + 动画）
- [tabs/audit/_tab.md](tabs/audit/_tab.md) -- 执行 Tab（2 Zones: InputForm + ResultArea）
- [tabs/batch/_tab.md](tabs/batch/_tab.md) -- 批量 Tab（1 Zone: BatchPanel）
- [tabs/history/_tab.md](tabs/history/_tab.md) -- 历史 Tab（2 Zones: FileList + DetailPane）
- [tabs/stats/_tab.md](tabs/stats/_tab.md) -- 统计 Tab
- [tabs/perf/_tab.md](tabs/perf/_tab.md) -- 性能 Tab
```

### 1.7 文件路由表（推荐）

当 View 层的运行时代码分散在多个文件中（共享库模板、任务级配置、快照文件等），在 `index.md` 中添加**文件路由表**可有效防止改错文件。

表格采用「改什么 → 改哪个文件」的映射格式：

```markdown
## 文件路由表

> 关键参考，防止改错文件。

| 改什么 | 改哪个文件 |
|--------|-----------|
| JS 交互逻辑 | `hoplogic/hop_view/chatflow/chatflow.js`（共享 IIFE） |
| JS 配置常量注入 | `hoplogic/hop_view/templates/base.html`（`{% if interactive %}` 块） |
| CSS 样式 | `hoplogic/hop_view/chatflow/chatflow.css` |
| 结果卡片 HTML | `hoplogic/hop_view/templates/fragments/run_result.html` |
| SSE 端点 | `hoplogic/hop_view/transport.py` |
| 任务配置 | `Tasks/<TaskName>/View/config.py` |
| Transport 薄启动器 | `Tasks/<TaskName>/View/app.py` / `web.py` |
| 快照（不要改） | `Tasks/<TaskName>/View/index.html` |
```

**使用场景**：
- 项目使用 `hop_view` 共享库时，运行时逻辑在共享模板中，而非 `index.html` 快照中——文件路由表明确这一区别
- ChatFlow 等交互组件涉及 JS/CSS/HTML fragment/Transport 多文件，路由表帮助 AI 和人直接定位目标文件
- 非交互项目（纯 HTMX）文件较少时可省略

---

## 二、交互流（Interaction Layer） — `tabs/*/`

每个 Tab 一个目录，存放在 `ViewSpec/tabs/` 下。**每个 Zone 一个独立文件**，`_tab.md` 声明 Tab 布局和 Zone 间事件路由。

### 2.1 Zone（交互分区）

Zone 是 ViewSpec 的核心结构单元，对应界面上一个独立的交互分区。

**Zone 的四要素**：

| 要素 | 说明 | 示例 |
|------|------|------|
| **元素** | Zone 拥有的 DOM 子树 | `textarea`, `button`, `div.content` |
| **状态变量** | Zone 内部的运行时变量 | `_sessionId`, `_retryCount` |
| **入站事件** | Zone 从外部接收的消息 | `on task_submit(desc, ctx)` |
| **出站事件** | Zone 向外发出的消息 | `emit need_feedback("supplement")` |

**封装规则**：
- Zone 内的 `render`/`set` 只能操作自身元素
- 要改变其他 Zone 的状态，必须 `emit` 事件，由对方 Zone 处理
- Zone 之间没有共享变量

**启用/禁用状态**：
- Zone 内的每个交互元素（按钮、输入框等）有 enabled / disabled 状态
- Zone 的每个事件处理器有 enabled / disabled 状态（disabled 时忽略触发）
- 当事件处理器被 disabled 时，**沿路由表反向传播**：其他 Zone 中 `emit` 到该事件的触发元素也自动 disabled（见 §2.4 协程守卫）

#### Zone 的实现来源

Zone 的实现代码有两种来源，ViewSpec 文件的角色随之不同：

| 实现来源 | 代码位置 | ViewSpec 角色 | `/code2view` 行为 |
|---------|---------|-------------|-----------------|
| **generated** | 由 `/code2view` 生成到 `Tasks/*/View/` | **生成规格** — 步骤序列是代码生成的输入 | 读取 ViewSpec → 生成代码 |
| **shared** | 共享库固定代码（如 `hop_view/chatflow/chatflow.js`） | **接口契约** — 记录已固化行为，声明参数化接口 | 跳过代码生成，仅提取配置参数 → `config.py` |

**generated Zone**（默认）：ViewSpec 的步骤序列是规范性的——AI 按步骤生成代码，步骤变更触发代码重新生成。这是 ViewSpec 的原始角色。

**shared Zone**：代码已固化到共享库中，运行时通过参数注入定制行为。此时：
- **共享库内的 ViewSpec**（如 `hoplogic/hop_view/chatflow/ViewSpec/`）记录完整的事件流和行为，作为组件的**接口文档**——它描述的是"代码做了什么"，而非"代码应该做什么"
- **任务级的 Zone 文件**只声明**定制点**（参数值、分支细节、字段映射），引用共享 ViewSpec 获取完整行为

**渐进固化**：Zone 的实现来源不是静态的。随着代码成熟，Zone 可以从 `generated` 固化为 `shared`——代码被提升到共享库，任务级 ViewSpec 从生成规格收缩为定制声明。这与 HOP 引擎层的渐进固化（`think → dynamic → static`）（历史别名 `seq_think` 保持兼容）是同一理念在 View 层的投影。

```
generated Zone                    shared Zone
┌─────────────────────┐          ┌─────────────────────────────────┐
│ Task ViewSpec       │          │ Shared ViewSpec (hop_view/)     │
│ ┌─────────────────┐ │          │ ┌─────────────────────────────┐ │
│ │ 完整步骤序列     │ │   固化    │ │ 完整步骤序列（接口文档）      │ │
│ │ （生成规格）     │ │ ──────→ │ │ 参数化接口声明               │ │
│ └─────────────────┘ │          │ └─────────────────────────────┘ │
│         ↓           │          │                                 │
│   /code2view 生成   │          │ Task ViewSpec                   │
│                     │          │ ┌─────────────────────────────┐ │
│                     │          │ │ 引用共享 ViewSpec            │ │
│                     │          │ │ 定制参数 + 分支细节          │ │
│                     │          │ └─────────────────────────────┘ │
│                     │          │         ↓                       │
│                     │          │   /code2view 仅生成 config.py   │
└─────────────────────┘          └─────────────────────────────────┘
```

### 2.2 文件模板

**`_tab.md`（Tab 总览文件）**：

```markdown
# <tab_id>（<tab_name>）

布局: <layout>

## Zone 拓扑

```
ZoneA ──event1──► ZoneB
  ▲                 │
  └───event2────────┘
```

## 事件路由

| 源 Zone | 事件 | 目标 Zone | 触发动作 |
|---------|------|-----------|---------|
| ZoneA | event1(args) | ZoneB | 执行 xxx |
| ZoneB | event2(args) | ZoneA | 更新 xxx |

## Zone 文件

- [ZoneA.md](ZoneA.md) -- 职责描述
- [ZoneB.md](ZoneB.md) -- 职责描述
```

**`<ZoneName>.md`（generated Zone 文件）**：

```markdown
# Zone: <ZoneName>

> <Zone 的职责描述>

事件: event1[coroutine] | event2[sync] | ...
内部过程: proc1(args), ...   （可选）

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `.xxx` | <type> | <initial> | | <desc> |
| `.btn-foo` | .btn-primary | 启用 | → event_name | <desc> |

## 状态变量

`_var1 = null`, `_var2 = 0`

## 事件: <event_name>  [sync|coroutine]

> <触发条件>
> guard: <.element>, <event:name>, ...   （仅 coroutine，声明执行期间 disabled 的元素和事件）

（编号步骤序列。coroutine 事件含 `call` 步骤，执行到 call 时挂起等待）

## 内部过程: <procedure_name>(params)

> <用途说明>

（编号步骤序列。非事件，不可从外部触发，仅被本 Zone 的事件调用）
```

**`<ZoneName>.md`（shared Zone 定制文件 — 任务级）**：

当 Zone 的实现来自共享库时，任务级文件仅声明定制点：

```markdown
# Zone: <ZoneName>（<TaskName> 定制）

> 共享实现: [`<共享 ViewSpec Zone 文件路径>`](...)
> 本文件仅描述定制点。通用行为见共享 ViewSpec。

## 定制参数

| 参数 | 值 | 说明 |
|------|---|------|
| thinking_steps | ["Analyzing...", "Searching...", ...] | thinking 气泡步骤文案 |
| max_feedback_rounds | 5 | 最大反馈轮次 |
| retry_quota | None (Infinity) | 重试配额 |

## <TaskName> 特化行为

（仅描述任务特有的分支细节、字段映射等。
不重复共享 ViewSpec 中已记录的协议、状态机、通用事件流。）
```

**shared Zone 文件不描述**（由共享 ViewSpec 承载）：
- 事件步骤序列（已固化在共享库代码中）
- 状态变量定义（同上）
- DOM 选择器和元素表（同上）
- 通用协议细节（SSE、状态机等）

**shared Zone 文件只描述**：
- 引用声明（指向共享 ViewSpec）
- 定制参数值
- 任务特有的分支细节（如各 `hop_status` 对应的卡片内容）
- 字段归一化映射（任务输出字段名 → 模板查找链）

**Zone 文件结构**：标题 → 职责描述（`>`） → **事件摘要行**（一行列出全部事件和内部过程名称，让人一眼掌握 Zone 全貌）→ `## 元素` → `## 状态变量` → `## 事件`（可多个）→ `## 内部过程`（可选，可多个）。附加说明节（如 `## Server-Authoritative State 规则`）放在最后。

**元素触发列**：元素表的 `触发` 列建立选择器→事件的映射，使事件全链路可倒推：从元素表找到触发事件 → 从事件步骤找到 emit → 从路由表找到目标 Zone 和事件。非交互元素（容器、显示区）留空。

**内部过程**：当多个事件共享同一段步骤序列时，提取为内部过程。内部过程不是事件——不可从外部触发，没有 guard，不算入"同一时刻至多一个协程"的约束。它只是被事件步骤中的 `code <procedure_name>(args)` 调用的可复用步骤块。

**事件参数类型**：事件携带参数时，在触发条件行下方用 `>` 标注参数的类型约束：

```markdown
## 事件: show_feedback(mode)  [sync]

> 接收 ChatFlow.show_feedback
> mode: "supplement" | "feedback" | "retry" | "resume"
```

简单类型（string、number）在路由表的参数列表中已隐含，可省略类型标注。枚举值、联合类型等非平凡约束应显式声明。

**命名规则**：Zone 文件名使用 PascalCase（如 `InputForm.md`、`DetailPane.md`），与代码中的组件/函数命名风格对应。`_tab.md` 以下划线前缀区分于 Zone 文件。

### 2.3 同步事件

不涉及 API 调用的事件，触发后立即完成。编号步骤序列。

```markdown
## 事件: fill_example  [sync]

> 点击"Fill Example"

1. set .inp-task <- 示例 task_description
2. set .inp-context <- 示例 context
```

### 2.4 协程事件（coroutine）

包含 `call`（API 调用）的事件。`call` 直接内嵌在步骤序列中，执行到 `call` 时 Zone 挂起等待返回，后续步骤处理结果——与 HopSpec 的异步步骤一致。

**约束**：同一 Zone 同一时刻至多一个协程事件在执行。

**等待期间的行为**：
- **进展显示** — `call` 前的 `render` 步骤已将 UI 切到 loading/thinking 状态
- **中止** — 用户可触发 Zone 的 `cancel` 同步事件打断协程
- **其他同步事件** — Zone 仍可接收和处理同步事件（如更新输入值），但实现者需防止与协程结果处理的状态冲突

**协程守卫（guard）**：

协程事件开始执行时，需同步声明哪些元素和事件进入 disabled 状态，防止等待期间触发冲突操作。协程完成（正常返回或被取消）时**自动恢复**为 enabled。

格式：在事件触发条件下方用 `> guard:` 声明，逗号分隔：

```markdown
## 事件: run_task(data)  [coroutine]

> 接收 InputForm.submit
> guard: .btn-run, event:submit_feedback

1. render .content <- ThinkingCard
2. call API.runTask(data) -> r
...
```

guard 列表中的项：
- **元素** — `.selector`：本 Zone 内的元素置为 disabled（按钮灰掉、输入框不可编辑）
- **事件** — `event:<event_name>`：本 Zone 的事件处理器置为 disabled（触发时忽略）

**跨 Zone 传播**：当事件处理器被 disabled 时，沿路由表反向查找：所有 `emit` 到该事件的源 Zone 触发元素也自动 disabled。

传播示例（chat-flow 模式，ChatFlow + ChatInputBar 两个 Zone）：
1. ChatFlow 的 `task_submit` guard 声明 `event:submit_feedback, event:retry_task` disabled
2. 路由表：`ChatInputBar | submit_feedback → ChatFlow | submit_feedback`
3. → ChatInputBar 中触发 `submit_feedback` 的按钮（`.btn-feedback`）自动 disabled
4. 协程完成 → guard 恢复 → ChatInputBar 的按钮也自动恢复 enabled

ViewSpec 只需在 guard 中声明本 Zone 的 disabled 项，跨 Zone 传播由代码生成器根据路由表自动推导。

**格式**（coroutine 事件完整示例）：

```markdown
## 事件: run_task(data)  [coroutine]

> 接收 InputForm.submit
> guard: event:submit_feedback

1. render .content <- ThinkingCard
2. call API.runTask(data) -> r
3. render 移除 ThinkingCard
4. branch r.error -> render .content <- ErrorCard(r.error); emit show_feedback("retry"); return
5. branch r.hop_status:
   - OK → render .content <- ConfirmedCard(r); emit hide_feedback
   - UNCERTAIN → render .content <- SolutionCard(r); emit show_feedback("feedback")
   - FAIL → render .content <- ErrorCard(r); emit show_feedback("retry")
```

**取消处理**：如果 Zone 需要支持中止，声明一个独立的 `cancel` 同步事件：

```markdown
## 事件: cancel  [sync]

> 用户点击中止按钮（协程等待期间）

1. code 中止当前协程
2. render 移除 ThinkingCard
3. render .content <- info-card("已中断")
4. emit show_feedback("resume")
```

**取消与 guard 恢复时序**：cancel 同步事件执行后，挂起的协程视为已终止，guard 立即恢复。具体实现可以是 AbortController 中止网络请求，或 `_cancelled` 标志使协程 `call` 返回后跳过后续步骤。无论哪种方式，cancel 事件完成时 guard 声明的所有 disabled 项（含跨 Zone 传播）恢复为 enabled。

**Guard 完备性规则（强制）**：

每个 coroutine 事件必须在 `> guard:` 行中显式声明以下三类守卫，缺少任一项的 ViewSpec 视为不合格：

| 守卫类型 | 格式 | 说明 |
|---------|------|------|
| **状态变量守卫** | `> guard: _conversationActive` | 事件入口处 `if (flag) return` 防止重入 |
| **元素守卫** | `> guard: .btn-send` | 执行期间 disable 的按钮/输入框 |
| **事件互斥守卫** | `> guard: event:submit_feedback` | 执行期间 disabled 的其他事件处理器 |

**完整 guard 声明示例**：

```
## 事件: task_submit(body)  [coroutine]

> 外部 InputArea emit
> guard: _conversationActive, .btn-send, event:submit_feedback, event:retry_task
```

**恢复路径**：guard 声明的元素和事件在会话终结时恢复（正常返回、cancel、error）。ViewSpec 中必须声明恢复函数名（如 `_unlockSend()`），且所有终态路径（OK/FAIL/CONFIRMED/error/cancel）都必须调用该函数。

**测试映射**：每个 guard 声明必须在 `test_html_builder.py` 中有对应的约束测试，验证生成的 HTML 包含该守卫的代码模式。

**错误处理**：API 调用失败（网络异常等）在 `call` 返回后通过 `branch` 处理，与业务分支一致——不需要独立的"拒绝"阶段。如需区分网络错误和业务错误，用 `branch r._network_error` 分支。

**与 HopSpec 的对应**：

| HopSpec | ViewSpec |
|---------|----------|
| `await session.hop_get(...)` | `call API.runTask(...)` |
| `if status != OK: return` | `branch r.error -> ...; return` |
| `session.add_feedback(...)` | `emit show_feedback(...)` |

异步 `call` 在步骤序列中就是一个挂起点，前面的步骤是准备（UI loading），后面的步骤是处理结果。这与 HopSpec 中 `await` 算子调用的模式完全一致。

### 2.5 Zone 间事件路由

Zone 通过 `emit` 发出事件，目标 Zone 通过入站事件接收。

**emit 语法**：`emit <event_name>(args)` — Zone 文件中只写事件名，不写目标 Zone。路由表负责将事件名映射到目标 Zone 的入站事件。

**事件路由表**（在 `_tab.md` 中声明）：

路由表四列：源 Zone、事件名（路由表中的唯一标识）、目标 Zone、目标事件名（目标 Zone 的入站事件名）。事件名和目标事件名通常一致（同名直通），不一致时路由表提供映射。

```markdown
## 事件路由

| 源 Zone | 事件 | 目标 Zone | 目标事件 |
|---------|------|-----------|---------|
| InputArea | task_submit(desc, ctx) | ChatFlow | task_submit |
| ChatFlow | show_feedback(mode) | FeedbackBar | show_feedback |
| ChatFlow | hide_feedback | FeedbackBar | hide_feedback |
| FeedbackBar | submit_feedback(text) | ChatFlow | submit_feedback |
| FeedbackBar | confirm_solution | ChatFlow | confirm_solution |
| FeedbackBar | retry_task | ChatFlow | retry_task |
```

这张表在 `_tab.md` 中集中声明，让 Zone 间的通信拓扑一目了然，也是代码审查和 diff 的核心锚点。各 Zone 文件只需处理自己的入站事件，无需了解全局路由。

**权威性规则**：路由表是事件名称的唯一权威来源。Zone 文件中的 `emit` 目标事件名和入站事件名必须与路由表一致。当路由表和 Zone 文件出现命名分歧时，以路由表为准。

### 2.6 Zone 内元素声明

声明 Zone 拥有的 DOM 元素（包括初始隐藏的）。

**格式**：

| 列 | 说明 | 示例 |
|----|------|------|
| 选择器 | Zone 内的 DOM 选择器 | `.btn-run`, `.content`, `textarea` |
| 类型 | HTML 元素类型或 CSS 类 | `textarea`, `select`, `.btn-primary`, `div` |
| 初始状态 | 页面加载时的状态 | `空`, `hidden`, `value=5`, `启用, "Run"` |
| 说明 | 元素用途 | `输入: task_description`, `执行按钮` |

**选择器命名约定**：
- Zone 内元素用相对选择器：`.btn-run`, `.content`, `textarea`
- 实际生成代码中，前缀由 Zone 所在 Tab 的 `tab_id` 确定（如 `.solve-input .btn-run`）
- 无固定选择器的用圆括号标注：`(Fill Example)`

**动态子元素**（可选）：对于 Zone 内条件渲染的子元素，用第二张表声明。「选择器」和「说明」两列必选，中间列可按 Zone 语义自定义（如「条件」、「角色」、「触发」等）：

```markdown
动态子元素:

| 选择器 | 条件 | 说明 |
|--------|------|------|
| .stats-grid (4 cards) | 有记录时 | 批次摘要卡片组 |
| .result-card | 有 credit_score | gauge + errors table + Raw JSON |
```

对话流等场景中，中间列可改为「角色」等语义更贴切的名称：

```markdown
动态子元素（消息气泡，追加到 .chat-flow）:

| 选择器 | 角色 | 说明 |
|--------|------|------|
| `.msg.msg-user` | 用户 | 用户消息气泡（右对齐）|
| `.msg.msg-system` | 系统 | 系统消息气泡（左对齐）|
```

### 2.7 何时需要独立 Zone

**需要独立 Zone**：
- 区域有自己的生命周期（出现/消失/状态切换）
- 区域会被多个其他区域触发
- 区域有自己的异步操作
- 区域的交互逻辑足够复杂（>5 个事件）

**不需要独立 Zone**：
- 纯展示区域（无交互、无状态）
- 一次性渲染的卡片（SolutionCard 内容由 ChatFlow 渲染，不需要独立 Zone）
- 只有简单同步事件、无异步操作、只被一个 Zone 控制的区域（如反馈输入栏，作为父 Zone 的内部元素即可——见 §2.8 ResultArea）

**经验法则**：区域有独立的异步操作或被多个 Zone 触发时，才需要独立 Zone。纯 emit 薄壳（收集输入 → emit）通常不值得拆分。

### 2.8 实例：执行 Tab（form 模式，2 个 Zone）

目录结构：

```
tabs/audit/
├── _tab.md          # Tab 总览 + 事件路由
├── InputForm.md     # Zone: 输入表单
└── ResultArea.md    # Zone: 结果展示 + 反馈
```

**`_tab.md`**：

```markdown
# audit（执行）

布局: form + result

## Zone 拓扑

```
InputForm ──run_task──► ResultArea
```

## 事件路由

| 源 Zone | 事件 | 目标 Zone | 目标事件 |
|---------|------|-----------|---------|
| InputForm | run_task(data) | ResultArea | run_task |

## Zone 文件

- [InputForm.md](InputForm.md) -- 输入表单：填写数据，提交触发执行
- [ResultArea.md](ResultArea.md) -- 结果区域：显示结果 + 反馈交互
```

**`InputForm.md`**：

```markdown
# Zone: InputForm

> 输入表单：填写审计数据，提交触发执行

事件: fill_example[sync] | submit[sync]

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `textarea.inp-context` | textarea | 空, rows=6 | | 输入: context_input |
| `textarea.inp-model` | textarea | 空, rows=6 | | 输入: model_output |
| `.btn-run` | .btn-primary | 启用, "Run Audit" | → submit | 执行按钮 |
| (Fill Example) | .btn-secondary | 启用 | → fill_example | 填充示例数据 |

## 事件: fill_example  [sync]

> 点击 (Fill Example)

1. set .inp-context <- 示例 context（见 rendering.md 示例数据）
2. set .inp-model <- 示例 model_output

## 事件: submit  [sync]

> 点击"Run Audit"

1. code 校验 .inp-context 和 .inp-model 非空，否则 return
2. emit run_task({context_input, model_output})
```

**`ResultArea.md`**：

```markdown
# Zone: ResultArea

> 结果区域：显示执行结果，处理状态分支，管理反馈交互

事件: run_task[coroutine] | submit_feedback[coroutine]

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `.content` | div | 空 | | 结果渲染区 |
| `.feedback-area` | div | hidden | | 反馈容器 |
| `textarea.feedback-input` | textarea | 空 | | 反馈文本 |
| `.btn-submit` | .btn-primary | hidden | → submit_feedback | 提交反馈按钮 |

## 状态变量

`_sessionId = null`, `_feedbackRound = 0`, `MAX_FEEDBACK = 3`

## 事件: run_task(data)  [coroutine]

> 接收 InputForm.submit
> guard: .btn-submit, event:submit_feedback

1. render .content <- spinner
2. set .feedback-area <- hidden
3. call API.runTask(data) -> r
4. set `_sessionId` <- r.session_id
5. render .content <- 空
6. branch r.error -> render .content <- error-card(r.error); return
7. branch r:
   - r 含 credit_score -> render .content <- result-card（见 rendering.md）
   - r.status === "LACK_OF_INFO":
     1. render .content <- result-card
     2. set .feedback-area <- visible
     3. set .feedback-input placeholder <- "请补充信息..."
   - r.status === "UNCERTAIN":
     1. render .content <- result-card
     2. set .feedback-area <- visible
     3. set .feedback-input placeholder <- "输入修改意见..."

## 事件: submit_feedback  [coroutine]

> 点击 .btn-submit
> guard: .btn-run, event:run_task

1. code `_feedbackRound++`; branch >= MAX_FEEDBACK -> set .btn-submit disabled; return
2. code 读取 .feedback-input.value -> text; 若空则 return
3. set .feedback-input <- 空
4. render .content 追加 spinner
5. call API.submitFeedback({session_id: _sessionId, feedback: text}) -> r
6. render .content <- 空
7. branch r: 同 run_task 步骤 6-7
```

FeedbackArea 没有独立 Zone 的必要——无异步操作、只被 ResultArea 控制、交互简单。反馈栏的显隐和提交作为 ResultArea 的内部元素和事件即可。

### 2.9 实例：批量 Tab（单 Zone，异步 + 定时器）

当 Tab 交互简单（无跨区域通信）时，Tab 目录下只有 `_tab.md` + 一个 Zone 文件。

目录结构：

```
tabs/batch/
├── _tab.md          # Tab 总览（无跨 Zone 路由）
└── BatchPanel.md    # Zone: 唯一 Zone
```

**`_tab.md`**：

```markdown
# batch（批量）

布局: form + progress

## Zone 文件

- [BatchPanel.md](BatchPanel.md) -- 批量测试：文件选择 + 执行 + 进度轮询
```

**`BatchPanel.md`**：

```markdown
# Zone: BatchPanel

> 批量测试：文件选择 + 执行 + 进度轮询

事件: tab_switch[coroutine] | start_batch[coroutine] | poll_progress[coroutine]

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `select.file` | select | 空 | | 文件选择器, 项格式: `name (N records)` |
| `input.workers` | input[number] | value=5, min=1, max=20 | | 并发数配置 |
| `.btn-batch` | .btn-primary | 启用, "Start Batch" | → start_batch | 开始按钮 |
| (Refresh) | .btn-secondary | 启用 | → tab_switch | 刷新文件列表 |
| `.progress` | div | hidden | | 进度区容器 |
| `.progress-bar` | .progress-bar | width=0% | | 进度条 |
| `.status` | div | 空 | | 状态文字 |

## 状态变量

`_pollTimer = null`

## 事件: tab_switch  [coroutine]

> 切换到 batch Tab 时自动触发

1. call API.listTestFiles() -> files
2. render select.file <- files.map -> `<option>name (N records)</option>`

## 事件: start_batch  [coroutine]

> 点击"Start Batch"
> guard: .btn-batch, select.file, input.workers

1. code 读取 select.file.value -> file; 若空则 return
2. code 读取 input.workers.value -> workers
3. set .progress <- visible
4. call API.startBatch({filename: file, workers}) -> result
5. branch result.error -> render .status <- error; return
6. timer 启动 _pollTimer = setInterval(poll_progress, 1000ms)

## 事件: poll_progress  [coroutine]

> 定时器每 1000ms 触发

1. call API.getBatchProgress() -> p
2. code pct = p.total ? round(p.completed / p.total * 100) : 0
3. set .progress-bar width <- pct%
4. render .status <- `{completed}/{total} ({pct}%) {errors} errors`
5. branch p.running === false:
   - timer 清除 _pollTimer
   - set .btn-batch <- enabled
   - render .status 追加 `-- Done: {output_file}`
```

### 2.10 实例：历史 Tab（双 Zone，跨 Zone 通信）

目录结构：

```
tabs/history/
├── _tab.md          # Tab 总览 + 事件路由
├── FileList.md      # Zone: 左侧文件列表
└── DetailPane.md    # Zone: 右侧详情区
```

**`_tab.md`**：

```markdown
# history（历史）

布局: sidebar(240px) + detail(flex:1), 总高 calc(100vh - 100px)

## Zone 拓扑

```
FileList ──file_selected──► DetailPane
```

## 事件路由

| 源 Zone | 事件 | 目标 Zone | 目标事件 |
|---------|------|-----------|---------|
| FileList | file_selected(name) | DetailPane | load_file |

## Zone 文件

- [FileList.md](FileList.md) -- 左侧文件列表，240px 固宽
- [DetailPane.md](DetailPane.md) -- 右侧详情区，flex:1
```

**`FileList.md`**：

```markdown
# Zone: FileList

> 左侧文件列表，240px 固宽

事件: tab_switch[coroutine] | click_file[sync]

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `.file-list` | div | 空 | | 文件列表容器 |

动态子元素:

| 选择器 | 触发 | 说明 |
|--------|------|------|
| `.file-item` | → click_file | 文件列表项 |

## 事件: tab_switch  [coroutine]

> 切换到 history Tab 时自动触发

1. call API.listResults() -> files
2. branch files 为空 -> render .file-list <- empty-state "No results"; return
3. loop file in files -> render .file-list <- .file-item(file.name)

## 事件: click_file(name)  [sync]

> 点击 .file-item

1. set 所有 .file-item 移除 active; set 当前项 <- .active
2. emit file_selected(name)
```

**`DetailPane.md`**：

```markdown
# Zone: DetailPane

> 右侧详情区，flex:1

事件: load_file[coroutine]

## 元素

| 选择器 | 类型 | 初始状态 | 触发 | 说明 |
|--------|------|---------|------|------|
| `.detail` | div | "Select a result file" | | 详情渲染区 |

动态子元素:

| 选择器 | 条件 | 说明 |
|--------|------|------|
| .stats-grid (4 cards) | 有记录时 | 批次摘要 |
| .result-card (meta) | `_type === "meta"` | Profile/LLM 信息卡 |
| .result-card (audit) | 有 credit_score | gauge + errors table + Raw JSON |

## 事件: load_file(name)  [coroutine]

> 接收 FileList.file_selected

1. render .detail <- spinner
2. call API.loadResult(name) -> records
3. branch records 为空 -> render .detail <- empty-state "Empty"; return
4. code computeBatchStats(records) -> batchStats
5. render .detail <- renderBatchSummary(batchStats)
6. loop (i, rec) in records:
   - branch rec._type === "meta" -> render meta-card
   - branch rec 有 credit_score -> render result-card(data, idx, expectedScore)
   - else -> render `<details>Record #{i+1}</details>` + json-block
```

---

## 三、渲染映射（Rendering Layer） — `rendering.md`

渲染映射定义字段与 UI 组件的对应关系。分为：输入字段、输出字段、复合渲染组件、结果归一化、统计聚合。

**文件结构**：顶部 `## 字段映射速览` 用精简表格列出输入/输出/统计的字段→Widget→规则（人决策点），后续完整字段属性节（列宽、CSS 映射、子字段等）供 AI 逐项映射。

### 3.1 输入字段映射

声明每个输入契约字段的表单组件和属性。

**格式**：

```markdown
## 输入字段

#### <field_name>
- 类型: <data_type>
- Widget: <widget_type>
- <key>: <value>
```

**Widget 类型**（输入）：

| Widget | 适用类型 | 说明 |
|--------|---------|------|
| `textarea` | `string` | 多行文本输入（默认） |
| `input` | `string` | 单行文本输入 |
| `number` | `int` / `float` | 数值输入 |
| `select` | `enum` | 下拉选择 |
| `checkbox` | `bool` | 勾选框 |
| `json-editor` | `object` / `array` | JSON 编辑器 |

**属性语法**：

| 属性 | 适用 Widget | 示例 |
|------|------------|------|
| `rows` | `textarea` | `rows=6` |
| `placeholder` | `textarea`, `input` | `placeholder=输入上下文` |
| `min` / `max` | `number` | `min=0, max=100` |
| `options` | `select` | `options=High\|Low` |
| `default` | 所有 | `default=5` |

**示例数据**（用于"填充示例"按钮）：

```markdown
## 示例数据

` ` `json
{
  "context_input": "根据2023年财报...",
  "model_output": "A公司2023年营收..."
}
` ` `
```

### 3.2 输出字段映射

声明每个输出契约字段的渲染组件和规则。

**格式**：

```markdown
## 输出字段

#### <field_name>
- 类型: <data_type>
- Widget: <widget_type>
- 规则: <rendering_rules>
```

**Widget 类型**（输出）：

| Widget | 适用类型 | 渲染效果 |
|--------|---------|---------|
| `gauge-circle` | `int` / `float` | 圆形指示器（带颜色阈值）|
| `badge` | `bool` / `enum` | 状态标签（双色）|
| `text` | `string` | 纯文本显示 |
| `table` | `array[object]` | 表格（子字段为列头）|
| `list` | `array[string]` | 有序/无序列表 |
| `json` | `object` / `any` | 可折叠 JSON 显示 |

**规则语法**：

gauge-circle 阈值：`>=70:green, >=40:orange, <40:red`

badge 双值：`true:已检出/red, false:未检出/green`

table 列声明：`columns:type,location,evidence,severity[badge]`

**可选属性**：

| 属性 | 说明 | 示例 |
|------|------|------|
| `范围` | 数值字段的合法值域 | `范围: 0-100` |
| `说明` | 字段语义描述 | `说明: 可信度评分` |
| `空值提示` | 数据为空时的替代文案 | `空值提示: 未检测到错误` |
| `CSS 类映射` | 值到 CSS 类的映射 | `CSS 类映射: .gauge.s5/.s4 -> green` |
| `尺寸` | 元素尺寸 | `尺寸: 48x48px, border 3px` |
| `列宽` | 表格列宽分配 | `列宽: type 30%, explanation 自适应` |
| `子字段` | array[object] 的子字段声明 | 缩进 bullet list |

**实例**：

```markdown
#### credit_score
- 类型: int
- Widget: gauge-circle
- 规则: >=4:green, >=3:orange, <3:red
- 范围: 1-5
- CSS 类映射: `.gauge.s5`/`.s4` -> green, `.s3` -> orange, `.s2`/`.s1` -> red
- 尺寸: 48x48px, border 3px, font-size 20px

#### errors
- 类型: array[{fact|logic, explanation, severity}]
- Widget: table
- 规则: columns:fact|logic,explanation,severity[badge]
- 空值提示: 未检测到错误（绿色文字）
- 列宽: fact|logic 30%, explanation 自适应, severity 70px
- 子字段:
  - fact|logic: string, text
  - explanation: string, text
  - severity: string, badge -- High:red, Low:orange
```

### 3.3 复合渲染组件

当多个输出字段组合为一个复合 UI 组件时，在此声明其结构。

**格式**：用 ASCII 树描述 DOM 结构，附文字说明各部分的渲染规则。

**实例**：

```markdown
## 复合渲染组件

### result-card

.result-card
  .result-header
    .gauge.s{N}          -- credit_score gauge-circle
    [expected 对比区]     -- 条件渲染
    credit_score 文本     -- "Credit Score: N/5"
    errors 计数           -- "N error(s) found"
  .err-table             -- errors 表格（或空值提示）
  <details>Raw JSON</details>

### expected 对比（条件渲染）

当记录含 `expected_credit_score` 字段时渲染:
- 半透明小 gauge（32x32px, opacity:0.5）显示期望值
- zone 匹配标记: `=`(green) 匹配 / `!=`(red) 不匹配

**Zone 映射规则**:

| 分数 | Zone |
|------|------|
| 1-2  | 0    |
| 3    | 1    |
| 4-5  | 2    |
```

### 3.4 结果归一化

当前端需要处理多种数据格式时，声明归一化规则：

```markdown
## 结果归一化

前端 `normalizeResponse()` 统一处理多种数据格式:

| 格式 | 来源 | 识别方式 | 提取逻辑 |
|------|------|---------|---------|
| 直接 dict | API.runTask | `credit_score` 在顶层 | 直接使用 |
| 嵌套 result | batch 输出 | `result` 字段（JSON 字符串）| `JSON.parse(result)` |
| HOP 元组 | `(status, json_str)` | `Array.isArray && length===2` | `JSON.parse(r[1])` |
```

### 3.5 统计聚合映射

声明统计 Tab 中的聚合指标。

**格式**：

```markdown
## 统计聚合

#### <display_label>
- 源字段: <field_path>
- 聚合: <agg_type>
- Widget: <widget_type>
- 格式: <format_spec>
- 颜色规则: <threshold_rules>  (可选)
```

**聚合方式**：

| 聚合方式 | 适用类型 | 说明 |
|----------|---------|------|
| `count` | 所有 | 记录总数 |
| `mean` | `int`/`float` | 均值 |
| `rate(value)` | `bool`/`enum` | 特定值的比率 |
| `distribution(subfield)` | `array[object]` | 子字段值分布 |
| `zone_accuracy` | 自定义 | zone 匹配率 |
| `group_by(field)` | 分组 | 按字段分组聚合 |

**Widget 类型**（统计）：

| Widget | 说明 |
|--------|------|
| `stat-card` | 数值卡片（大字 + 标签）|
| `bar-chart` | 水平条形图 |
| `table` | 对比表格 |

可按需分为 **服务端统计**（Stats Tab，来自 `API.getStats`）和 **客户端统计**（history 批次摘要，前端计算）两个子节。

---

## 四、布局与主题（Layout Layer） — `theme.md`

### 4.1 主题声明

```markdown
## 主题

- 风格: Tokyo Night / Apple
- 颜色模式: auto (prefers-color-scheme)
- 字体: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Menlo', monospace
- 字号-正文: 13px
- 字号-标签: 11px (uppercase, letter-spacing .5px)
- 字号-控件: 12px
- 行高: 1.5
- 圆角-卡片: 8px
- 圆角-控件: 6px
- 间距基准: 8px
```

### 4.2 Design Tokens

分 Light 和 Dark 两组。如果使用默认 Tokyo Night 配色，可简写为 `[默认 Tokyo Night 配色]`。

**完整格式**：

```markdown
## Design Tokens

### Light

- --bg: #f5f5f7
- --bg-card: #ffffff
- --bg-input: #eeeef0
- --bg-tab: #e8e8ec
- --border: #d1d1d6
- --text: #1d1d1f
- --text-dim: #86868b
- --accent: #0071e3
- --accent-fg: #ffffff
- --green: #34c759
- --red: #ff3b30
- --orange: #ff9500
- --purple: #af52de

### Dark

- --bg: #1a1b26
- --bg-card: #24283b
- --bg-input: #1f2335
- --bg-tab: #16161e
- --border: #3b4261
- --text: #c0caf5
- --text-dim: #565f89
- --accent: #7aa2f7
- --accent-fg: #1a1b26
- --green: #9ece6a
- --red: #f7768e
- --orange: #e0af68
- --purple: #bb9af7
```

**扩展变量**（任务特定语义变量，格式 `--name: <light_value> / <dark_value>`）：

```markdown
### 扩展

- --badge-high-bg: rgba(255,59,48,.15) / rgba(247,118,142,.15)
- --badge-low-bg: rgba(255,149,0,.15) / rgba(224,175,104,.15)
```

### 4.3 窗口

```markdown
## 窗口

- 标题: <AppName>
- 宽度: 1200
- 高度: 820
- 最小宽度: 900
- 最小高度: 600
- macOS 红绿灯预留: 80px
```

### 4.4 布局尺寸

用表格列出关键 UI 区域的尺寸数值：

```markdown
## 布局尺寸

| 区域 | 属性 | 值 |
|------|------|-----|
| Tab bar | button padding | 6px 16px |
| History 文件列表 | width | 240px (flex-shrink:0) |
| Stats grid | grid-template-columns | repeat(auto-fill, minmax(180px, 1fr)) |
| Gauge circle | 尺寸 | 48x48px, border 3px |
| Progress bar | height | 20px |
| JSON block | max-height | 300px (overflow-y:auto) |
```

### 4.5 CSS 类清单

列出所有自定义 CSS 类及其所属 Tab 范围：

```markdown
## CSS 类清单

| 类名 | 用途 | 所在 Tab |
|------|------|---------|
| `.tab-bar` | Tab 切换栏 | 全局 |
| `.panel` / `.panel.active` | Tab 面板显隐 | 全局 |
| `.gauge` / `.gauge.s1`-`.s5` | 分数圆形指示器 | audit, history |
| `.badge` / `.badge.high` / `.badge.low` | 严重度标签 | audit, history |
| `.result-card` | 单条结果卡片 | audit, history |
| `.stats-grid` | 统计卡片网格 | stats, perf, history |
| `.stat-card` | 统计卡片 | stats, perf, history |
| `.err-table` | 数据表格 | audit, history, stats, perf |
| `.spinner` | 加载动画 | 全局 |
| `.empty-state` | 空数据提示 | 全局 |
```

### 4.6 动画

```markdown
## 动画

- `.spinner`: `spin .6s linear infinite`
- `.progress-bar`: `transition: width .3s`
- Tab button: `transition: all .15s`
```

---

## ViewSpec 与代码的映射

### 渲染层 -> 代码映射

| ViewSpec 声明 | 目标文件 | 生成内容 |
|--------------|----------|---------|
| 输入字段声明 | `index.html` | 表单 `<textarea>` / `<input>` / `<select>` |
| 输入字段声明 | `app.py` | `Api.run_task()` 参数列表 |
| 输入字段声明 | `web.py` | `RunTaskRequest` Pydantic 模型字段 |
| 输出字段声明 | `renderer.py` | `render_result_card()` 中的 Widget 渲染 |
| 复合组件声明 | `renderer.py` + `templates/` | Jinja2 模板渲染 |
| 结果归一化 | `renderer.py` | `normalize_response()` 函数 |
| 统计聚合声明 | `hop_view.datastore` | `get_stats()` 中的 ibis 聚合表达式 |

### 交互层 -> 代码映射

| ViewSpec 声明 | 目标文件 | 生成内容 |
|--------------|----------|---------|
| Tab 列表 | `index.html` | Tab bar 按钮、Panel 容器 |
| Zone 元素表 | `index.html` | HTML 元素声明（class、初始状态），Zone 对应 DOM 容器 |
| Zone 状态声明 | `renderer.py` / Jinja2 | Python renderer / Jinja2 模板状态 |
| 事件路由表 | `index.html` | `emit` 映射为函数调用/自定义事件分发 |
| 同步事件步骤 | `index.html` | HTMX + ~100行 JS |
| coroutine 事件步骤 | `index.html` + `web.py` | HTMX hx-post/hx-get + server-side rendering |
| guard 声明 | `index.html` | 协程入口处 disable 元素/事件 + finally 恢复；跨 Zone 传播按路由表推导 |
| API 端点映射 | `index.html` | HTMX hx-* 属性 |
| API 端点映射 | `web.py` | FastAPI 路由（返回 HTMLResponse） |
| API 端点映射 | `app.py` | pywebview 薄启动器（内嵌 uvicorn） |

### 主题层 -> 代码映射

| ViewSpec 声明 | 目标文件 | 生成内容 |
|--------------|----------|---------|
| Design Tokens | `index.html` | `:root { --bg: ...; }` CSS 变量 |
| 主题属性 | `index.html` | `@media (prefers-color-scheme: dark)` |
| 窗口属性 | `app.py` | `webview.create_window(width=..., height=...)` |
| 布局尺寸 | `index.html` | CSS 尺寸数值 |
| CSS 类清单 | `index.html` | CSS 类定义 |
| 动画 | `index.html` | `@keyframes` + `transition` |

---

## 设计决策与权衡

### 为什么选择 Zone + 事件驱动，而非全局步骤列表

旧版 ViewSpec 采用扁平事件处理（`on_xxx` 步骤序列 + 全局状态变量），实践中暴露三个问题：

1. **全局状态耦合** — `_sessionId`、`_feedbackRound` 等变量散布在多个事件处理函数中，任意事件都能读写任意变量，改一处要排查全局影响
2. **跨区域操作隐式** — 一个事件的步骤中直接 `set #chat-input-bar <- hidden`（属于另一个逻辑区域），依赖关系只能通过阅读步骤序列推断
3. **异步路径隐式** — API 调用写在步骤列表中间（如"步骤 6: call API.runTask"），取消/错误路径靠 `_cancelled` 标志散落各处检查

Zone + 事件驱动解决这三个问题：

1. **状态封装** — 每个 Zone 拥有自己的状态，外部不可直接读写。Zone A 的 `_sessionId` 不会被 Zone B 的事件意外修改
2. **通信显式** — Zone 间交互通过 `emit` 事件声明在路由表中，拓扑一目了然。代码审查时看路由表即可理解 Zone 间依赖
3. **异步协程约束** — 单 Zone 单协程，`call` 内嵌步骤序列（与 HopSpec 一致），取消/错误通过同步事件和 `branch` 处理

### 为什么每个 Zone 独立文件

Zone 是 ViewSpec 的核心单元，每个 Zone 文件包含：元素表（~5-10 行）+ 状态（~1 行）+ 事件（每个 ~5-15 行）。总量在 20-60 行。独立文件的好处：

1. **粒度精准** — 修改 ChatInputBar 的交互，只打开 `ChatInputBar.md`，不影响同 Tab 的其他 Zone
2. **diff 精确** — 变更局限于单个 Zone 文件，代码审查时一目了然
3. **复用可能** — 未来同一 Zone 定义可被多个 Tab 引用
4. **并行编辑** — 不同 Zone 的编辑不冲突，即使在同一个 Tab 内

`_tab.md` 文件只包含布局声明和事件路由表（~15 行），是 Zone 间的"接线图"，保持轻量。

### 为什么 `call` 内嵌步骤序列，而非独立生命周期

曾考虑将异步事件拆为独立阶段（触发/执行/解决/取消/拒绝），但实践中发现：

1. **与 HopSpec 不一致** — HopSpec 的 `await session.hop_get()` 就是步骤序列中的一行，前面是准备，后面是处理结果。拆分阶段引入了 HopSpec 没有的额外结构
2. **过度形式化** — 大部分事件的"触发"只有 1-2 行（设 loading），"解决"就是 branch 处理结果，拆成独立节增加了格式噪音
3. **取消是独立事件** — 取消发生在等待期间，本质上是另一个事件（用户点击中止按钮），应声明为 Zone 的独立同步事件，而非塞进同一个事件的子阶段

最终选择：`call` 内嵌在步骤序列中（和 HopSpec 一致），取消/中止是独立的同步事件，错误通过 `branch` 处理。规则简单：**同一 Zone 同一时刻至多一个协程在执行**，解决竞态。

```
## 事件: run_task(data)  [coroutine]     ## 事件: cancel  [sync]
> guard: event:submit_feedback            > （无 guard，同步事件）
1. render .content <- spinner             1. code 中止当前协程
2. call API.runTask(data) -> r            2. render 移除 ThinkingCard
3. render 移除 spinner                    3. render .content <- "已中断"
4. branch r.error -> ...
5. branch r.hop_status -> ...
                                          guard 自动恢复:
                                            event:submit_feedback <- enabled
                                            源 Zone 触发元素 <- enabled（传播）
```

左侧是协程事件的线性步骤（`call` 处挂起，guard 在进入时 disable、完成时自动恢复），右侧是等待期间用户触发的取消事件（取消也触发 guard 恢复）。两者是 Zone 的两个独立事件，而非一个事件的子阶段。

### Zone 粒度的权衡

**过粗**（一个 Tab 一个 Zone）：退化为旧版全局状态，失去封装优势。

**过细**（每个按钮一个 Zone）：emit 泛滥，简单交互也要声明路由，增加规范噪音。

**经验法则**：Zone 拆分的判据是**独立的异步操作**或**被多个 Zone 触发**。纯同步的"收集输入 → emit"薄壳（如反馈输入栏）不值得拆为独立 Zone，作为父 Zone 的内部元素即可——少一层路由，少一份文件，少一次跳转。

### 跨 Zone 数据传递

Zone 之间没有共享变量。如果 Zone B 需要 Zone A 持有的数据，有两种方式：

1. **通过事件参数传递**（推荐）：Zone A emit 事件时将数据作为参数传出，Zone B 在入站事件中接收并缓存到自己的状态。
2. **通过 API 响应获取**：Zone B 调用 API 后，从响应中获取所需数据。

**反面模式**：Zone B 的事件步骤中直接引用 Zone A 的状态变量（如 `_lastTaskDescription`）。这违反封装规则，即使代码实现上 Zone 只是同一 HTML 文件中的 JS 变量，ViewSpec 层面仍禁止这种隐式依赖——它让 Zone 间耦合不可见于路由表。

### chat-flow 布局模式

`chat-flow` 是多轮对话式交互的典型布局（如 HOP 的 SolutionSolver Hoplet），区别于 form+result 的一次性提交模式。特征：

- **追加式渲染** — 每轮交互追加消息气泡，不清空历史。大量使用 `render X <- append Y`
- **多协程共存** — task_submit、submit_feedback、retry_task 三个协程事件互斥（guard 互锁），但共享同一个消息流容器
- **内部过程** — 多个协程共用 handleResponse 等分支逻辑，提取为内部过程避免重复
- **Server-Authoritative State** — 显示值（轮次、session_id）来自 API 响应，前端状态仅用于控制流

这种模式下 Zone 拆分通常为：InputArea（首次输入）+ ChatFlow（消息流，拥有 API 调用和状态机）+ ChatInputBar（底部反馈栏，纯 emit）。ChatFlow 是最重的 Zone，承载核心状态和所有协程事件。

### Shared Zone 与 Generated Zone 的选择

同一个 Tab 内可以混合使用 shared 和 generated Zone。典型场景：

```
SolutionSolver / solve Tab:
  InputArea      [generated]  — 每个任务的输入表单不同，由 /code2view 生成
  ChatFlow       [shared]     — 共享库固定代码，参数化定制
  ChatInputBar   [shared]     — 共享库固定代码，参数化定制
```

**判断依据**：Zone 的事件步骤序列是否在多个任务间完全相同（仅参数不同）？
- **是** → 适合固化为 shared（代码提升到共享库，ViewSpec 分化为接口文档 + 定制声明）
- **否** → 保持 generated（每个任务有独特的事件流）

**渐进固化路径**（Zone 层面）：

```
[generated]  多任务各自生成相似代码
     ↓       发现代码高度重复，仅参数不同
[提取]       代码提升到 hop_view 共享库，参数化
     ↓       共享库内创建 ViewSpec 目录记录行为
[shared]     任务级 Zone 文件收缩为定制声明
```

详见 §2.1 Zone 的实现来源、§2.2 shared Zone 定制文件模板。

**反面模式**：shared Zone 的任务级文件仍复述共享组件的协议（端点、状态机、事件步骤），导致共享组件升级后任务 ViewSpec 过期，AI 按过期描述生成代码与运行时不一致。

### 什么需要形式化，什么不需要

借鉴 HopSpec 的原则 -- **只形式化 AI 容易猜错的东西**：

**需要形式化**（结构化声明）：
- Zone 拓扑和事件路由（AI 可能跨 Zone 直接操作状态）
- 协程守卫 guard（AI 可能遗漏异步期间的 disabled 互斥，或忘记跨 Zone 传播）
- 协程事件的 `call` 步骤和错误分支（AI 可能遗漏错误处理或取消事件）
- 字段->Widget 映射（AI 可能用错组件类型）
- 阈值和颜色规则（AI 可能随意设定）
- 统计聚合方式（AI 可能漏掉或用错聚合函数）
- 页面元素和初始状态（保证事件流引用一致）
- 错误边界（Zone 事件异常的兜底策略，AI 可能遗漏未捕获异常的处理）
- 长列表性能策略（AI 可能对大数据量列表不做虚拟滚动或分页）

**不需要形式化**（自然语言或省略）：
- CSS 细节（AI 根据 Design Tokens 推导）
- HTML 标签结构（AI 根据布局模式推导）
- 响应式适配（AI 根据布局模式和窗口尺寸推导断点和折叠策略）
- 复杂 Zone 的状态枚举和状态转换图（AI 从状态变量和事件推导生成，供人审阅参考）
- loading/error 等通用状态（所有任务一致，写在 index.md 通用行为里）
- Zone 内部的 DOM 层次（AI 根据元素表推导）

### 人决策 vs AI 细节的文件内分区

每个 ViewSpec 文件内部，人需要决策的内容前置，AI 需要的实现细节后置。人读到分隔线即可停止，AI 从头到尾全读。

| 文件 | 人决策（前置） | AI 细节（后置） |
|------|-------------|---------------|
| **_tab.md** | 布局、Zone 拓扑、事件路由 | （无，全是决策） |
| **Zone 文件** | 职责描述、事件摘要行、事件流语义、guard | 元素表选择器、初始状态细节 |
| **rendering.md** | 字段映射速览表（字段→Widget→规则） | 完整属性（列宽、CSS 映射、子字段） |
| **theme.md** | 风格、窗口标题/尺寸 | Design Tokens hex 值、布局 px、CSS 类清单 |
| **index.md** | Tab 列表、API 端点列表 | pvArgs、双模式适配、原语定义 |

**Zone 文件事件摘要行**：Zone 文件标题和职责描述后，紧跟一行事件摘要，让人一眼看到 Zone 的全部事件和内部过程：

```markdown
# Zone: ChatFlow

> 消息流：管理对话历史，执行 API 调用，按 hop_status 分支渲染。

事件: task_submit[coroutine] | submit_feedback[coroutine] | retry_task[coroutine] | cancel[sync]
内部过程: handleResponse(r)
```

**rendering.md 字段映射速览表**：rendering.md 顶部增加精简的映射速览表（输入/输出/统计各一小表），人看速览即可把握全貌。后续完整字段属性节供 AI 逐项映射。

### 跨文件追溯锚点（可选）

当字段数量增多或需要跨文件重命名时，可为字段添加 8 字节 hex 锚点实现显式追溯。锚点在数据契约（源头）分配，ViewSpec 和生成代码继承同一 ID。

**语法**：锚点附在字段声明末尾，格式 `@<8hex>`。

```
数据契约                    rendering.md 输出字段        生成代码
──────────────────         ──────────────────          ──────────────────
credit_score @a3f7b2c1     #### credit_score @a3f7b2c1  <!-- @a3f7b2c1 -->
                                                        <div class="gauge">
```

`grep -r a3f7b2c1` 即可定位同一字段在数据契约、ViewSpec、生成代码中的所有出现位置。字段改名不断链。

**适用粒度**：字段级（输入/输出契约字段）。Zone 和事件通过 `zone_id` / `event_name` 已有稳定标识，不需要额外锚点。

---

## HOP 工具链（Hoplet 应用场景）

ViewSpec 在 HOP 项目中用于描述 Hoplet 的观测 UI。以下命令和参考实现为 HOP 专属。

### 命令

| 命令 | 用途 | 方向 |
|------|------|------|
| `/code2viewspec <task>` | metainfo + HopSpec → ViewSpec 初始生成 | 契约 → 规范 |
| `/code2view <task>` | ViewSpec + metainfo → View 代码 | 规范 → 代码 |
| `/view2spec <task>` | View 代码 → ViewSpec 反向同步 | 代码 → 规范 |

```
metainfo.md + HopSpec.md
        |
  /code2viewspec --> ViewSpec/ <-> View/ (files)
  (初始生成)            |           ^
                        |           |
              /code2view --+  +-- /view2spec
              (正向生成)        (反向同步)
```

### 参考实现

完整的 ViewSpec 实例见 `Tasks/VerifyFast/View/ViewSpec/` 目录：
- `index.md` — 总览（Tab 表 + API 适配 + 通用行为 + 原语 + 文件路由表 + 文件索引）
- `rendering.md` — 渲染映射（2 输入 + 2 输出 + 复合组件 + 归一化 + 6 统计指标）
- `theme.md` — 布局主题（Light/Dark tokens + 23 布局尺寸 + 26 CSS 类 + 5 动画）
- `tabs/audit/` — 执行 Tab（`_tab.md` + 2 Zone 文件: InputForm + ResultArea）
- `tabs/batch/` — 批量 Tab（`_tab.md` + 1 Zone 文件: BatchPanel）
- `tabs/history/` — 历史 Tab（`_tab.md` + 2 Zone 文件: FileList + DetailPane）
- `tabs/stats/` — 统计 Tab（`_tab.md` + Zone 文件）
- `tabs/perf/` — 性能 Tab（`_tab.md` + Zone 文件）

### 相关文档

- 数据契约定义：`Tasks/<TaskName>/Hoplet/metainfo.md`
- 五层架构规范：`Terms/HopletView架构规范.md`
- 执行逻辑规范：`Terms/HopSpec格式规范.md`
- `/code2viewspec` 命令规范：`.claude/commands/code2viewspec.md`
- `/code2view` 命令规范：`.claude/commands/code2view.md`
- `/view2spec` 命令规范：`.claude/commands/view2spec.md`

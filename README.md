# HOP 2.0 Studio

**HOP（High-Order Program）** 是面向大模型的可信智能体编程范式——**可控、可靠、可持续进化**。

通过结构化程序骨架约束 LLM 智能、算子级核验闭环消除幻觉、渐进固化实现持续进化，使 LLM 在金融、医疗等专业场景中达到 99%+ 可靠性。

HOP 2.0 Studio 是 HOP 的规范与引擎开发环境，提供从自然语言任务描述到可执行智能体的完整工具链。

> **技术定位**：人定意图约束，AI 可信实现，代码智能双态融合，智力资产持续沉淀。

---

## 核心理念

| 原则 | 说明 |
|------|------|
| **可控** | HopSpec 继承结构化程序设计范式（Bohm-Jacopini / Dijkstra），7 种原子步骤类型覆盖顺序、选择、循环 + LLM 推理 + 外部调用 + 任务分解 + 流程控制，执行路径可预判、可审计 |
| **可靠** | 确定性骨架隔离 LLM 非确定性（幻觉不扩散），三大算子内建多层核验（逆向/正向交叉/工具/格式），核验失败自动重试并追加反馈 |
| **可持续进化** | subtask 从探索（think 有序思考）渐进固化为确定性流程，Spec-Code 双向同步不脱节，Bad Case 通过残差分析转化为知识或技能改进 |

### 代码智能双态融合

```
              loop (确定性: 遍历集合)
             /    \
        LLM         branch (确定性: Python 表达式求值)
      (非确定性)      /      \
                   LLM       flow:continue
                (非确定性)    (确定性)
```

**控制流完全确定，非确定性严格隔离在叶子节点。** 单个节点幻觉不会导致控制流层面的无序传播。

---

## 架构

### 三层执行架构

```
用户代码 (Hop.py / examples)
    |
HopSession  -- 执行边界：对话历史、HopState、ExecutionStats、持久化(StateStore)
    |
HopProc     -- 算子抽象：hop_get / hop_judge / hop_tool_use（无状态、可共享）
    |
LLM         -- 传输层：连接复用、多引擎适配、结构化输出
```

### 三大算子（均为 async）

| 算子 | 用途 | 默认核验 |
|------|------|----------|
| `hop_get()` | 信息获取 / 知识抽取 | 逆向核验 |
| `hop_judge()` | 真伪研判 / 条件判断 | 逆向核验 |
| `hop_tool_use()` | 工具选择与调用 | 工具核验 |

### 核验体系

| 核验器 | 方式 | 成本 |
|--------|------|------|
| `format_verifier` | 序列化残留检测（纯本地） | 零 LLM 开销 |
| `reverse_verify` | 独立 LLM 反向验证 | 1 次 LLM 调用 |
| `forward_cross_verify` | 3 路并发取多数 | 3 次 LLM 调用 |
| `tool_use_verifier` | 合法性 + 参数 + 交叉核验 | 视工具而定 |

### AOT / JIT 双模式

- **AOT（Ahead-of-Time）**：人类编写 SOP -> HopSpec -> 代码生成 -> 执行。适合固化的、反复执行的任务。
- **JIT（Just-in-Time）**：用户任务描述 -> LLM 动态生成 HopSpec -> 确定性验证 -> 引擎解释执行。适合即时的、探索性的任务。
- **渐进固化**：think（有序思考）-> dynamic（加载固化路径）-> static（预定义步骤）。越用越确定、越可靠。

---

## 项目结构

```
.
├── Tasks/                          # HOP 任务目录（5 个任务）
│   └── <TaskName>/
│       ├── Task.md                 # Echo 编写的任务描述（只读）
│       ├── Hoplet/                 # 可执行的智能体单元
│       │   ├── metainfo.md         # 元数据契约（输入/输出/运行模式/测试指标）
│       │   ├── SKILL.md            # AgentSkills.io 互操作描述
│       │   ├── HopSpec.md          # 规范化的任务规格说明书
│       │   └── Hop.py              # 可执行代码
│       ├── TestCases/              # 测试用例与结果
│       └── View/                   # 观测 UI（SSR 架构，桌面 + Web 双模式）
│           ├── ViewSpec/           # UI 规范（Zone-per-file 结构）
│           ├── config.py           # ViewConfig 声明
│           ├── app.py / web.py     # Transport 薄启动器
│           ├── index.html          # Frontend（SSR 渲染）
│           └── test/               # 集成测试
├── HopLib/                         # 可复用技能库（4 个技能）
│   ├── ConfigManager/              # 配置管理工具（uv run hop config）
│   ├── Chart/                      # 图表生成
│   ├── OCR/                        # 文字识别
│   └── WebSearch/                  # 网络搜索
├── Terms/                          # 术语定义与规范文档（16 篇）
├── hoplogic/                       # HOP Engine 核心代码
│   ├── hop_engine/                 # 引擎包（8 组件）
│   │   ├── config/                 #   配置与常量（HopStatus, ModelConfig）
│   │   ├── utils/                  #   共享工具（JSON 解析、格式修复）
│   │   ├── llm/                    #   LLM 传输层（多引擎适配）
│   │   ├── prompts/                #   Prompt 模板与策略
│   │   ├── tools/                  #   工具注册
│   │   ├── validators/             #   核验器
│   │   ├── core/                   #   核心引擎（HopProc、HopSession、StateStore）
│   │   └── jit/                    #   JIT 引擎（Spec 解析/验证/执行/subtask）
│   ├── hop_view/                   # View 共享库（SSR 渲染、配置驱动）
│   ├── hop_rag/                    # RAG 组件（DuckDB VSS、知识库检索增强）
│   ├── hop_mcp/                    # MCP Client（工具连接与调用）
│   ├── hop_mcp_server/             # MCP Server（HOP 技能暴露为 MCP 服务）
│   ├── hop_skill/                  # Skill 组件（技能发现、注册、适配）
│   ├── code_template/              # Hop.py 代码模板
│   ├── examples/                   # 示例应用（5 个）
│   ├── docs/                       # API 文档（35 篇）
│   └── test/                       # 单元测试套件
├── .claude/commands/               # Claude Code 斜杠命令（16 个）
├── .roo/commands/                  # Roo Code 命令（同步）
├── pyproject.toml                  # 项目元数据（Python >= 3.14）
└── uv.lock                         # 依赖锁文件
```

---

## 安装

**环境要求**：Python >= 3.14，包管理使用 [uv](https://docs.astral.sh/uv/)。

```bash
# 克隆仓库
git clone <repo-url> && cd hop_spec_ide

# 安装依赖
uv sync

# 安装开发依赖
uv sync --group dev
```

---

## 快速开始

### 运行 Hoplet

```bash
# 推荐：通过 uv run task 命令执行（无需 cd）
uv run task <TaskName>

# 启动观测 UI（桌面模式）
uv run view <TaskName>

# 启动观测 UI（Web 模式）
uv run view <TaskName> --web
```

### 配置管理

```bash
# 图形化配置编辑器（桌面模式）
uv run hop config

# Web 模式
uv run hop config --web

# 列出所有技能
uv run hop list

# 按名称执行技能
uv run hop run <skill_name> '<json_input>'
```

### 运行示例

```bash
# 配置 LLM API（编辑 hoplogic/settings.yaml 和 .env）
cd hoplogic

# 钓鱼邮件检测
uv run python -m examples.phishing.phishing

# 集成测试（需要 LLM API）
uv run python test.py
```

### 运行单元测试

```bash
# 全部测试（约 1500+ tests，纯 mock，无需 LLM API）
cd hoplogic && uv run pytest test/ -v

# 各组件测试
cd hoplogic && uv run pytest hop_view/test/ -v
cd hoplogic && uv run pytest hop_skill/test/ -v
cd hoplogic && uv run pytest hop_rag/test/ -v
cd hoplogic && uv run pytest hop_mcp/test/ -v
```

---

## 双向迭代流水线

```
Task.md ──→ HopSpec.md ⇄ Hop.py + metainfo.md ──→ 执行/测试
 Echo编写   /task2spec  │    ↑                    /hoprun
                        │    │
          /specsync ────┘    └──── /code2spec
          (Spec→Code增量)         (Code→Spec反向)

                /specdiff (对比差异，不修改文件)

metainfo.md + HopSpec.md ──→ ViewSpec/ ⇄ View/
  (数据契约)   (执行逻辑)       │           ↑
                  │             │           │
        /code2viewspec    /code2view ──┘    └── /view2spec
```

### 典型工作流

```bash
# 完整流水线（以 VerifyFast 任务为例）
/task2spec VerifyFast       # Task.md -> HopSpec.md
/verifyspec VerifyFast      # 审计 HopSpec（可选）
/spec2code VerifyFast       # HopSpec -> Hop.py（全量生成）
/hoprun VerifyFast          # 执行并 debug

# 批量测试（自动包含结果分析）
/batchhoptest VerifyFast test_data.jsonl --workers 10

# 迭代 A：debug 后回写 Spec
/hoprun VerifyFast          # 运行，AI 修复了代码
/specdiff VerifyFast        # 查看 Code 改了什么
/code2spec VerifyFast       # 修改回写到 Spec

# 迭代 B：修改 Spec 后增量同步 Code
/specsync VerifyFast        # 增量更新 Code
/hoprun VerifyFast          # 验证执行

# 生成观测 UI
/code2viewspec VerifyFast   # 初始生成 ViewSpec
/code2view VerifyFast       # ViewSpec -> View 代码
```

---

## 斜杠命令一览

| 命令 | 用途 | 方向 |
|------|------|------|
| `/task2spec <task>` | Task.md -> HopSpec | Task.md -> HopSpec.md |
| `/verifyspec <task>` | 审计并修改 HopSpec | HopSpec.md -> HopSpec.md |
| `/showspec <task>` | 命令行可视化 HopSpec 树结构 | HopSpec.md（只读） |
| `/spec2code <task>` | HopSpec -> 代码（全量生成） | HopSpec.md -> Hop.py + metainfo.md + SKILL.md |
| `/specsync <task>` | Spec -> Code 增量同步 | HopSpec.md -> Hop.py |
| `/code2spec <task>` | Code -> Spec 反向同步 | Hop.py -> HopSpec.md |
| `/specdiff <task>` | 对比差异（只读） | HopSpec.md + Hop.py |
| `/solidify <task>` | 审阅并确认固化路径 | think -> dynamic |
| `/hoprun <task>` | 执行并 debug | Hop.py |
| `/batchhoptest <task> <file>` | 批量测试 + 自动分析 | Hop.py -> TestCases/ |
| `/batchanalysis <task>` | 分析历史测试结果 | TestCases/ |
| `/diagnose <task>` | 诊断并修复测试失败 | TestCases/ -> Hop.py |
| `/code2viewspec <task>` | 初始生成 ViewSpec | metainfo.md -> ViewSpec/ |
| `/code2view <task>` | 生成观测 UI | ViewSpec/ -> View/ |
| `/view2spec <task>` | View -> ViewSpec 反向同步 | View/ -> ViewSpec/ |
| `/rag-index` | 构建/更新 Terms/ RAG 索引 | Terms/ -> 索引 |

---

## HopSpec：7 种原子步骤类型

HopSpec 使用 7 种原子步骤类型组成的结构化树描述 LLM 推理流程，理论基础为 Bohm-Jacopini 结构化程序定理：

| 类型 | 用途 | 代码映射 |
|------|------|----------|
| **LLM** | LLM 推理（提取/分析/判断） | `hop_get()` / `hop_judge()` |
| **call** | 工具调用 | `hop_tool_use()` |
| **loop** | 循环（for-each / while） | `for item in collection:` / `while cond:` |
| **branch** | 条件分支 | `if condition:` |
| **code** | 纯 Python 计算 | 赋值 / 计算 |
| **flow** | 流程控制 | `return` / `continue` / `break` |
| **subtask** | 子任务（static/dynamic/think） | 子函数 / JIT 展开 |

---

## 场景验证

| 场景 | 模型 | baseline 正确率 | HOP 完成率 | HOP 正确率 |
|------|------|----------------|-----------|-----------|
| 8 位大数相乘 | Qwen3-235B-A22B | 30.33% | 100.00% | 97.30% |
| 钓鱼邮件检测 | Qwen3-32B | 84.32% | 97.56% | 99.01% |
| 医疗重复诊疗 | Qwen3-235B-A22B | 76.00% | 100.00% | 99.00% |

**指标说明**：
- **HOP 完成率** = 通过核验的样本数 / 样本总数
- **HOP 正确率** = 通过核验且正确的样本数 / 通过核验的样本数

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **Python 3.14** | 全程 async/await 协程 |
| **openai** (AsyncClient) | LLM 调用，兼容 vllm / siliconflow / bailian / ollama / sglang 等 |
| **pydantic** | 结构化输出（Structured Outputs） |
| **pyyaml** | 配置文件解析 |
| **DuckDB VSS** | RAG 向量存储 |
| **Jinja2** | View SSR 渲染 |
| **HTMX** | 前端交互（无 JS 框架） |
| **pywebview** | 桌面应用容器 |
| **uv** | 包管理 |

---

## 配置

### settings.yaml（三区块格式）

```yaml
defaults:                          # 全局默认参数
  max_tokens: 4000
  temperature: 0.1

llms:                              # LLM 端点定义
  kimi-k2:
    base_url: "https://..."
    model: "Kimi-K2-Instruct-0905"
    protocol: "aistudio-vllm"
  qwen3-235b:
    base_url: "https://..."
    model: "Qwen3-235B-A22B"

profiles:                          # LLM 组合（第一个为默认）
  kimi-full:
    run: kimi-k2
    verify: kimi-k2
  cross-verify:
    run: kimi-k2
    verify: qwen3-235b
```

### .env 密钥配置

```env
HOP_KEY_kimi_k2=sk-xxx
HOP_KEY_qwen3_235b=sk-xxx
```

LLM 名与 `.env` 变量名两侧均做 `-.` -> `_` + 大写归一化后匹配。

---

## 文档

### 引擎 API 文档（`hoplogic/docs/`，35 篇）

| 文档 | 内容 |
|------|------|
| [hop.md](hoplogic/docs/hop.md) | 三大算子 API（入口文档） |
| [hop_session.md](hoplogic/docs/hop_session.md) | HopSession 会话管理 |
| [hop_processor.md](hoplogic/docs/hop_processor.md) | HopProc 内部方法 |
| [hop_validators.md](hoplogic/docs/hop_validators.md) | 核验器详解 |
| [hop_config.md](hoplogic/docs/hop_config.md) | 配置与常量 |
| [hop_settings.md](hoplogic/docs/hop_settings.md) | Settings 配置指南 |
| [hop_engineering.md](hoplogic/docs/hop_engineering.md) | 工程规范总纲 |
| [hop_view.md](hoplogic/docs/hop_view.md) | View 共享库 API |
| [hop_skill.md](hoplogic/docs/hop_skill.md) | Skill 组件 API |
| [hop_rag.md](hoplogic/docs/hop_rag.md) | RAG 组件 API |
| [hop_mcp.md](hoplogic/docs/hop_mcp.md) | MCP Client API |
| [hop_subtask.md](hoplogic/docs/hop_subtask.md) | subtask 与渐进固化 |
| [hop_batch_runner.md](hoplogic/docs/hop_batch_runner.md) | 批量测试 CLI |
| [hop_testing.md](hoplogic/docs/hop_testing.md) | 单元测试说明 |
| [getting_started.md](hoplogic/docs/getting_started.md) | 快速入门 |

### 术语与规范文档（`Terms/`，16 篇）

| 文档 | 内容 |
|------|------|
| [HOP高阶程序.md](Terms/HOP高阶程序.md) | HOP 整体定义、设计理念 |
| [HOP核心算子.md](Terms/HOP核心算子.md) | 核心算子调用说明 |
| [HOP 2.0 技术定位.md](Terms/HOP%202.0%20技术定位.md) | 技术定位与设计哲学 |
| [HopSpec格式规范.md](Terms/HopSpec格式规范.md) | 7 种原子步骤类型格式规范 |
| [ViewSpec格式规范.md](Terms/ViewSpec格式规范.md) | 三层 UI 规范 |
| [HopletView架构规范.md](Terms/HopletView架构规范.md) | View 五层架构规范 |
| [HopLib规范.md](Terms/HopLib规范.md) | 技能库规范 |
| [HopSpec vs Kiro Spec.md](Terms/HopSpec%20vs%20Kiro%20Spec.md) | 与 Kiro Spec 对比分析 |
| [HOP vs Burr.md](Terms/HOP%20vs%20Burr.md) | 与 Burr 框架对比分析 |
| [HopJIT.md](Terms/HopJIT.md) | JIT 模式架构与 API |
| [ChatFlow组件规范.md](Terms/ChatFlow组件规范.md) | 交互对话流组件规范 |
| [批量测试数据格式规范.md](Terms/批量测试数据格式规范.md) | 批量测试 JSONL 格式规范 |

---

## License

[Mozilla Public License Version 2.0](LEGAL.md)

## 声明

非发布版本的 HOP 禁止在任何生产环境中使用，可能存在漏洞、功能不足、安全问题或其他问题。

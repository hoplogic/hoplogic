# HOP JIT：LLM 生成 HopSpec + 运行时解释执行

## 动机：AOT vs JIT

当前 HOP 采用 **AOT（Ahead-of-Time）** 模式：

```
人类编写 Task.md → /task2spec 生成 HopSpec.md → /spec2code 生成 Hop.py → 执行
```

这个流水线适合**固化的、反复执行的任务**（如钓鱼检测、事实核查），但对于**即时的、一次性的任务**来说流程太重。

**JIT（Just-in-Time）** 模式将 HOP 从"编程框架"升级为"元编程框架"：

```
用户任务描述 → LLM 生成 HopSpec → 确定性验证 → 引擎解释执行
```

LLM 在受约束的 DSL（6 种原子类型、树结构）内"编程"，引擎在运行时解释执行生成的程序。每个 LLM 步骤仍保留核验闭环。

## 架构

```
用户任务描述
    │
    ▼
┌─────────────────────────┐
│ Spec Generator           │  LLM 生成 HopSpec（1 次 LLM 调用）
│ 输入: 任务 + HopSpec速查  │  输入 context 注入速查文档作为格式参考
└─────────────────────────┘
    │ HopSpec markdown
    ▼
┌─────────────────────────┐
│ Spec Parser              │  解析 markdown → StepInfo 树（纯 Python）
└─────────────────────────┘
    │ List[StepInfo]
    ▼
┌─────────────────────────┐
│ Spec Validator           │  6 项结构审计（纯 Python，零 LLM 成本）
│ ✗ → 返回错误，重新生成    │
└─────────────────────────┘
    │ validated List[StepInfo]
    ▼
┌─────────────────────────┐
│ Spec Executor            │  遍历 StepInfo 树，按类型调度到 HopSession 算子
│ LLM → hop_get/hop_judge  │  每步带核验
│ code → LLM 翻译 + exec   │
│ loop/branch → 控制流调度   │
└─────────────────────────┘
    │
    ▼
  结构化结果 JSON
```

## 双层核验设计

JIT 模式有**两层**核验：

### 第一层：Spec 级（确定性）

Spec Validator 对 LLM 生成的 HopSpec 执行 6 项纯 Python 验证：

1. **结构完整性** — 6 章节齐全，以 flow:exit 结束
2. **类型正确性** — 类型合法，flow continue/break 在 loop 内
3. **树结构合规** — 无跳转，容器属性完整
4. **数据流连通** — 每个输入有前序产出
5. **核验策略覆盖** — LLM 步骤核验声明（warning 级）
6. **命名规范** — snake_case，step_name 唯一

不通过则附带错误信息让 LLM 重新生成。零 LLM 成本，纯结构审计。

### 第二层：执行级（LLM 核验）

SpecExecutor 执行每个 LLM 步骤时，仍使用 HopSession 的核验闭环（逆向核验/正向交叉/工具核验）。这是 HOP 引擎原有的核验能力，JIT 完全复用。

## 文件结构

```
hoplogic/hop_engine/jit/
├── __init__.py              # 导出公开 API
├── models.py                # StepInfo, ValidationError, ContinueSignal, BreakSignal
├── spec_parser.py           # HopSpec markdown → StepInfo 树
├── spec_validator.py        # 6 项确定性验证
├── spec_executor.py         # 解释执行 StepInfo 树
├── spec_generator.py        # LLM 生成 HopSpec
└── hop_jit.py               # 顶层编排
```

## API 使用示例

### 全自动 JIT（动态生成 + 执行）

```python
from hop_engine.processors.hop_processor import HopProc
from hop_engine.config.model_config import ModelConfig
from hop_engine.jit import HopJIT

hop_proc = HopProc(
    run_model_config=ModelConfig.from_yaml("settings.yaml", "system_model_config"),
    verify_model_config=ModelConfig.from_yaml("settings.yaml", "verify_model_config"),
)

# spec_reference 自动从内嵌资源加载（按 i18n 语言选择中/英版本）
# 也可显式传入自定义内容覆盖默认
jit = HopJIT(hop_proc)

result = await jit.run(
    task_description="对大模型输出进行事实落地性、逻辑蕴含、自洽性三阶段审计",
    input_data={"context_window": "...", "model_output": "..."},
    output_schema='{"reliability_score": int, "errors": list, "verification_summary": str}',
)

print(result["result"])   # 结构化执行结果
print(result["spec"])     # 生成的 HopSpec（可审计、可保存）
print(result["stats"])    # 算子统计
```

### 预编译 Spec 执行（已有 HopSpec）

```python
spec_md = open("Tasks/Verify/Hoplet/HopSpec.md").read()

result = await jit.run_spec(
    spec_markdown=spec_md,
    input_data={"context_window": "...", "model_output": "..."},
)
```

### 仅解析 + 验证（不执行）

```python
from hop_engine.jit import parse_full_spec, validate_spec

parsed = parse_full_spec(open("Tasks/Verify/Hoplet/HopSpec.md").read())
errors = validate_spec(parsed["steps"], parsed["sections"])

for e in errors:
    print(f"[{e.check}] 步骤{e.step_id}: {e.message}")
```

## 与纯 Agent 的对比

| 维度 | 纯 Agent（AutoGPT 式） | HOP JIT |
|------|------------------------|---------|
| 规划 | LLM 自由规划 | LLM 在 DSL 约束内规划 |
| 验证 | 无结构验证 | 6 项确定性 Spec 验证 |
| 执行 | LLM 自主决策 | 引擎按树结构调度 |
| 核验 | 无/人工 | 每步自动核验 |
| 可审计 | 日志级 | Spec 级（可读/可存/可重放） |
| 可重复 | 低 | 高（同一 Spec 确定性执行） |

核心差异：Agent 的"大脑"在 LLM 的下一步决策中；JIT 的"大脑"在确定性的树结构遍历中。LLM 只负责填充每个节点的内容，不决定执行顺序。

## code 步骤的执行策略

`code` 步骤的 `description`（逻辑字段）是自然语言描述。JIT 用 LLM 将其翻译为 Python 代码片段，然后在受限环境中执行。

受限环境只暴露：
- 输入变量 + 安全内置函数（len, sum, max, min, range, zip 等）
- json 模块
- 不暴露 os, sys, subprocess 等危险模块

每个 code 步骤消耗 1 次轻量 LLM 调用（无核验）。未来可通过模板匹配常见模式（合并列表、过滤、组装 dict）实现零 LLM 成本。

## 局限性

1. **code 步骤需要 LLM 翻译**：当前实现中 code 步骤也消耗 LLM 调用
2. **hoplet/MCP 调用未实现**：call 步骤暂只支持 tool 调用
3. **错误恢复有限**：某步骤失败时只能继续执行后续步骤，无法回退
4. **并发未优化**：loop 步骤目前顺序执行，未利用 asyncio.gather 并发
5. **Spec 缓存未实现**：相同任务描述每次都重新生成 Spec

## 与 AOT 的关系

JIT 不替代 AOT，而是互补：

- **AOT**：适合固化任务，人类精调 Spec 和 Code，追求最优质量
- **JIT**：适合即时任务，快速原型，或者 AOT 流水线中的自动化 Spec 生成步骤

JIT 生成的 Spec 可以保存下来，进入 AOT 流水线继续精调：

```
JIT 生成 Spec → 保存为 HopSpec.md → /verifyspec → /spec2code → 进入 AOT 迭代
```

# HopSpec i18n 方案：中英文双语支持

## 一、问题分析

HOP JIT 系统中有 333 处中文散布在 7 个源文件中。这些中文按功能性质分为三类，**每类需要不同的解决方案**：

| 类型 | 性质 | 示例 | 解决方案 |
|------|------|------|---------|
| **DSL 语法** | HopSpec 的关键字/属性名 | `步骤`/`Step`、`类型`/`Type`、`核验：逆向`/`Verify: reverse` | SpecGrammar 语法配置 |
| **用户消息** | 验证错误、执行日志 | `缺少必选章节`/`Missing required sections` | gettext 兼容的 `_()` 消息表 |
| **LLM 交互** | Spec 生成 prompt、code 步骤翻译 prompt | `根据任务描述生成 HopSpec`/`Generate a HopSpec from task description` | 语言感知的 Prompt 模板 |

**关键原则**：三类问题三套机制，各模块只依赖自己需要的那一层。

---

## 二、架构总览

```
┌───────────────────────────────────────────────────────┐
│                    hop_jit.py                          │
│  HopJIT(hop_proc, lang="zh")                          │
│  接受 lang 参数，分发到各组件                             │
└───────┬──────────────┬──────────────┬─────────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────────┐
│ SpecGrammar  │ │  _()     │ │ Prompt Templates │
│ (DSL 语法)   │ │ (用户消息) │ │ (LLM 交互)       │
│              │ │          │ │                  │
│ ZH_GRAMMAR   │ │ dict     │ │ zh_prompt        │
│ EN_GRAMMAR   │ │ 消息表    │ │ en_prompt        │
└──────┬───────┘ └────┬─────┘ └────────┬─────────┘
       │              │                │
       ▼              ▼                ▼
  spec_parser    spec_validator   spec_generator
  spec_executor  spec_executor
```

各模块的依赖关系：

| 模块 | SpecGrammar | `_()` 消息表 | Prompt 模板 |
|------|:-:|:-:|:-:|
| spec_parser | Y | - | - |
| spec_validator | Y（章节名） | Y（错误消息） | - |
| spec_executor | Y（核验值） | 可选（日志） | - |
| spec_generator | Y（属性名方向） | - | Y |
| hop_jit | 透传 | 透传 | 透传 |
| models | - | - | - |

---

## 三、DSL 语法层：SpecGrammar

HopSpec 的属性名（`类型`/`Type`）不是用户界面文本，而是 DSL 的关键字——类似编程语言的 keyword。用**可插拔的语法配置**解决，不用 gettext。

### 3.1 数据结构

新建 `hop_engine/jit/grammar.py`：

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SpecGrammar:
    """HopSpec DSL 语法定义 — 每种语言一套"""

    # parser: 步骤标题
    step_prefix: str                              # "步骤" / "Step"

    # parser: 属性名 → StepInfo 字段
    attr_map: dict[str, str] = field(default_factory=dict)

    # parser/validator: 章节逻辑名 → 显示名
    section_names: dict[str, str] = field(default_factory=dict)

    # parser: "无输入" 标记
    empty_markers: tuple[str, ...] = ()

    # executor: 核验策略 显示名 → 内部名
    verifier_map: dict[str, str] = field(default_factory=dict)

    # generator: 指示 LLM 使用的属性语言
    attr_lang_instruction: str = ""

    @property
    def required_sections(self) -> set[str]:
        """验证器需要的必选章节名集合"""
        return set(self.section_names.values())

    @property
    def execution_section(self) -> str:
        """执行流程章节的显示名"""
        return self.section_names["execution"]
```

### 3.2 中文语法

```python
ZH_GRAMMAR = SpecGrammar(
    step_prefix="步骤",
    attr_map={
        "类型": "step_type",
        "任务": "task",
        "输入": "inputs",
        "输出": "outputs",
        "输出格式": "return_format",
        "核验": "verifier",
        "说明": "description",
        "描述": "description",
        "逻辑": "description",
        "调用目标": "call_target",
        "工具域": "tool_domain",
        "Hoplet路径": "hoplet_path",
        "MCP服务": "mcp_service",
        "动作": "action",
        "目标循环": "target_loop",
        "退出标识": "exit_id",
        "条件": "condition",
        "遍历集合": "collection",
        "元素变量": "element_var",
        "最大轮次": "max_iterations",
    },
    section_names={
        "overview": "任务概述",
        "input_def": "输入定义",
        "constraints": "硬性约束",
        "execution": "执行流程",
        "output_format": "输出格式",
        "input_example": "输入日志示例",
    },
    empty_markers=("（无）", "(无)"),
    verifier_map={
        "无": "none",
        "逆向": "reverse",
        "正向交叉": "forward_cross",
    },
    attr_lang_instruction="属性名使用中文。",
)
```

### 3.3 英文语法

```python
EN_GRAMMAR = SpecGrammar(
    step_prefix="Step",
    attr_map={
        "Type": "step_type",
        "Task": "task",
        "Input": "inputs",
        "Output": "outputs",
        "Output Format": "return_format",
        "Verify": "verifier",
        "Description": "description",
        "Logic": "description",
        "Call Target": "call_target",
        "Tool Domain": "tool_domain",
        "Hoplet Path": "hoplet_path",
        "MCP Service": "mcp_service",
        "Action": "action",
        "Target Loop": "target_loop",
        "Exit ID": "exit_id",
        "Condition": "condition",
        "Collection": "collection",
        "Element Var": "element_var",
        "Max Iterations": "max_iterations",
    },
    section_names={
        "overview": "Overview",
        "input_def": "Input Definition",
        "constraints": "Constraints",
        "execution": "Execution Flow",
        "output_format": "Output Format",
        "input_example": "Input Example",
    },
    empty_markers=("(none)", "none"),
    verifier_map={
        "none": "none",
        "reverse": "reverse",
        "forward cross": "forward_cross",
    },
    attr_lang_instruction="Use English attribute names.",
)
```

### 3.4 语法注册表与自动检测

```python
from hop_engine.jit.models import SpecLang

GRAMMARS: dict[SpecLang, SpecGrammar] = {
    SpecLang.ZH: ZH_GRAMMAR,
    SpecLang.EN: EN_GRAMMAR,
}

def detect_lang(spec_markdown: str) -> SpecLang:
    """从 Spec 内容自动检测语言"""
    if re.search(r"####\s+步骤", spec_markdown):
        return SpecLang.ZH
    if re.search(r"####\s+Step", spec_markdown):
        return SpecLang.EN
    # fallback: 中文字符密度
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", spec_markdown[:500]))
    return SpecLang.ZH if zh_chars > 5 else SpecLang.EN

def get_grammar(lang: SpecLang) -> SpecGrammar:
    return GRAMMARS[lang]
```

### 3.5 各模块如何使用 SpecGrammar

**spec_parser.py**：

```python
# 之前：硬编码
_STEP_HEADER_RE = re.compile(r"...步骤(?P<id>[\d.]+)...")
_ATTR_MAP = {"类型": "step_type", ...}

# 之后：从 grammar 构造
def parse_spec(spec_markdown: str, grammar: SpecGrammar = ZH_GRAMMAR) -> list[StepInfo]:
    step_re = re.compile(
        rf"^(?P<indent>\s*)####\s+{re.escape(grammar.step_prefix)}"
        rf"(?P<id>[\d.]+)(?::\s*(?P<name>\w+))?"
    )
    # 使用 grammar.attr_map 替代硬编码 _ATTR_MAP
    # 使用 grammar.execution_section 替代硬编码 "执行流程"
    # 使用 grammar.empty_markers 替代硬编码 "（无）"
    ...
```

**spec_validator.py**：

```python
# 之前：硬编码
_REQUIRED_SECTIONS = {"任务概述", "输入定义", ...}

# 之后：从 grammar 读取
def check_structure(sections, steps, grammar: SpecGrammar = ZH_GRAMMAR):
    missing = grammar.required_sections - set(sections.keys())
    ...
```

**spec_executor.py**：

```python
# 之前：硬编码中文核验值
if verifier_str == "无": return None
if verifier_str == "逆向": return _UNSET
if verifier_str == "正向交叉": return forward_cross_verify

# 之后：从 grammar.verifier_map 查表
def _resolve_verifier(self, verifier_str: str):
    internal = self.grammar.verifier_map.get(verifier_str, "")
    match internal:
        case "none": return None
        case "reverse": return _UNSET
        case "forward_cross": return forward_cross_verify
        case _: return _UNSET
```

---

## 四、用户消息层：gettext 兼容的 `_()`

验证错误消息是用户可见的输出，采用 gettext 的 `_()` 调用约定，底层先用 dict 实现，保留未来迁移到 gettext 的能力。

### 4.1 实现

新建 `hop_engine/jit/i18n.py`：

```python
"""i18n — gettext 兼容的轻量消息国际化

调用约定与 gettext 完全一致：
    from hop_engine.jit.i18n import _, set_lang
    set_lang("zh")
    msg = _("Missing required sections: {missing}").format(missing="...")

迁移到 gettext 时只改本文件，所有 _() 调用点零改动。
"""

from threading import local

_state = local()

# 英文为 msgid（源码中写英文），中文为翻译
MESSAGES: dict[str, dict[str, str]] = {
    "zh": {
        # === structure ===
        "Missing required sections: {missing}":
            "缺少必选章节: {missing}",
        "Execution flow is empty, no steps found":
            "执行流程为空，没有任何步骤",
        "Last top-level step should be flow(action=exit), got {actual}":
            "最后一个顶层步骤应为 flow(action=exit)，实际为 {actual}",

        # === type ===
        "Invalid step type: \"{step_type}\", valid types: {valid}":
            "无效的步骤类型: \"{step_type}\"，有效类型: {valid}",
        "flow:{action} must be inside a loop":
            "flow:{action} 必须在 loop 子步骤内部使用",
        "{step_type} container has no child steps":
            "{step_type} 容器没有子步骤",
        "JIT mode: while loop requires max_iterations > 0 for loop guard":
            "JIT 模式下 while loop 必须设置 max_iterations > 0（循环迭代上限防护）",

        # === tree ===
        "flow:{action} missing target_loop":
            "flow:{action} 缺少目标循环(target_loop)属性",
        "flow:{action} target loop \"{target}\" does not match any ancestor loop (available: {available})":
            "flow:{action} 的目标循环 \"{target}\" 不匹配任何祖先 loop 步骤（可用: {available}）",
        "branch step missing condition":
            "branch 步骤缺少条件(condition)属性",
        "loop for-each missing element_var":
            "loop for-each 模式缺少元素变量(element_var)属性",
        "loop while max_iterations cannot be negative: {value}":
            "loop while 模式的最大轮次不能为负数: {value}",
        "loop step needs collection (for-each) or condition (while)":
            "loop 步骤需要遍历集合(collection)属性（for-each）或条件(condition)属性（while）",

        # === dataflow ===
        "Loop collection variable \"{var}\" not produced by prior steps":
            "loop 遍历集合变量 \"{var}\" 在前序步骤中未产出",
        "Input variable \"{var}\" not produced by prior steps":
            "输入变量 \"{var}\" 在前序步骤中未产出（可能是外部输入，需在输入定义中声明）",

        # === verifier ===
        "LLM step \"{name}\" has no explicit verify strategy (default: reverse)":
            "LLM 步骤 \"{name}\" 未显式声明核验策略（默认逆向核验）",

        # === naming ===
        "step_name \"{name}\" is not snake_case":
            "step_name \"{name}\" 不符合 snake_case 格式",
        "step_name \"{name}\" duplicates step {other}":
            "step_name \"{name}\" 与步骤 {other} 重复",

        # === generator ===
        "Failed to generate valid Spec after {n} attempts. Last errors: {errors}":
            "经过 {n} 次尝试仍无法生成有效 Spec。最后的错误: {errors}",
    },
}


def set_lang(lang: str) -> None:
    """设置当前线程/协程的语言"""
    _state.lang = lang


def get_lang() -> str:
    """获取当前语言，默认 en"""
    return getattr(_state, "lang", "en")


def _(msgid: str) -> str:
    """翻译函数 — gettext 兼容签名

    传入英文 msgid，返回当前语言的翻译。
    未找到翻译时 fallback 到 msgid 本身（英文原文）。
    """
    lang = get_lang()
    if lang == "en":
        return msgid
    return MESSAGES.get(lang, {}).get(msgid, msgid)
```

### 4.2 调用点示例

```python
from hop_engine.jit.i18n import _

# spec_validator.py 中
errors.append(ValidationError(
    check="structure",
    step_id="",
    message=_("Missing required sections: {missing}").format(
        missing=", ".join(sorted(missing))
    ),
))

# 之前的中文写法:
# message=f'缺少必选章节: {", ".join(sorted(missing))}'
```

### 4.3 迁移到 gettext

未来消息量超过 200 条或引入第三语言时，只改 `i18n.py` 的实现：

```python
import gettext as _gettext

_translations: dict[str, _gettext.GNUTranslations] = {}

def set_lang(lang: str) -> None:
    _state.lang = lang
    if lang not in _translations:
        _translations[lang] = _gettext.translation(
            "hop_jit", localedir="locale", languages=[lang], fallback=True,
        )

def _(msgid: str) -> str:
    lang = get_lang()
    t = _translations.get(lang)
    return t.gettext(msgid) if t else msgid
```

所有 `_("...")` 调用点**零改动**。

### 4.4 完整性测试

```python
def test_i18n_message_completeness():
    """确保每种语言的消息表覆盖所有 key"""
    from hop_engine.jit.i18n import MESSAGES
    for lang, table in MESSAGES.items():
        # 收集代码中所有 _() 调用的 msgid（由 CI 脚本或手动维护）
        assert isinstance(table, dict)
        # 关键：zh 表的 key 集合应与实际使用的 msgid 一致

def test_i18n_no_missing_format_keys():
    """确保翻译字符串的 {key} 占位符与原文一致"""
    import re
    from hop_engine.jit.i18n import MESSAGES
    fmt_re = re.compile(r"\{(\w+)\}")
    for lang, table in MESSAGES.items():
        for msgid, msgstr in table.items():
            en_keys = set(fmt_re.findall(msgid))
            tr_keys = set(fmt_re.findall(msgstr))
            assert en_keys == tr_keys, (
                f"[{lang}] Format key mismatch: {msgid!r} has {en_keys}, "
                f"translation has {tr_keys}"
            )
```

---

## 五、LLM 交互层：Prompt 模板

spec_generator 和 spec_executor 的 code 步骤需要向 LLM 发送 prompt。prompt 语言影响生成质量，独立于 DSL 语法和用户消息管理。

### 5.1 Generator Prompt

`spec_generator.py` 中 `_build_generation_prompt` 按语言切换模板：

```python
def _build_generation_prompt(task_description, ..., grammar: SpecGrammar):
    parts = []

    # 章节标题用目标语言
    section_names = grammar.section_names
    parts.append(
        f"Output a complete HopSpec markdown with these 6 sections:\n"
        f"1. ## {section_names['overview']}\n"
        f"2. ## {section_names['input_def']}\n"
        f"3. ## {section_names['constraints']}\n"
        f"4. ## {section_names['execution']}\n"
        f"5. ## {section_names['output_format']}\n"
        f"6. ## {section_names['input_example']}\n\n"
        f"{grammar.attr_lang_instruction}"
    )
    ...
```

### 5.2 速查文档

LLM 生成 Spec 时注入的格式参考需要对应语言版本：

- 中文：`Terms/HopSpec JIT模式速查.md`（现有）
- 英文：`Terms/HopSpec JIT Quick Reference.md`（新建）

`HopJIT` 初始化时按 lang 选择：

```python
class HopJIT:
    def __init__(self, hop_proc, lang=SpecLang.ZH, spec_reference=""):
        self.lang = lang
        self.grammar = get_grammar(lang)
        # 如果未指定 spec_reference，按语言加载默认速查
        if not spec_reference:
            spec_reference = _load_default_reference(lang)
        self.spec_reference = spec_reference
```

### 5.3 Executor code 步骤 Prompt

```python
# 之前：硬编码中文
task = f"将以下自然语言逻辑翻译为一段 Python 代码片段。\n逻辑：{step.description}\n..."

# 之后：按语言切换
if self.lang == SpecLang.ZH:
    task = f"将以下自然语言逻辑翻译为一段 Python 代码片段。\n逻辑：{step.description}\n..."
else:
    task = f"Translate the following logic into a Python code snippet.\nLogic: {step.description}\n..."
```

这里不用消息表——prompt 不是用户消息，而是 LLM 指令，需要按 LLM 能力精调，不适合自动翻译。

---

## 六、英文 HopSpec 示例

中文版（现有）：

```markdown
## 任务概述
对大模型输出进行事实落地性检查。

## 输入定义
- `context_window`: 原始上下文
- `model_output`: 模型生成文本

## 硬性约束
- 每条原子陈述必须独立核验。

## 执行流程

#### 步骤1: extract_facts
- 类型：LLM
- 任务：将模型输出拆解为原子事实陈述
- 输入：model_output
- 输出：atomic_claims
- 输出格式：{"claims": List[str]}
- 核验：无

#### 步骤2: check_grounding（loop）
- 类型：loop
- 遍历集合：atomic_claims
- 元素变量：claim
- 输出：grounding_errors

  #### 步骤2.1: judge_source
  - 类型：LLM
  - 任务：判断该陈述是否有上下文支撑
  - 输入：context_window, claim
  - 输出：verdict
  - 核验：逆向

#### 步骤3: output_report
- 类型：flow
- 动作：exit
- 输出：grounding_errors

## 输出格式
{"grounding_errors": List[dict]}

## 输入日志示例
{"context_window": "...", "model_output": "..."}
```

英文版（对等）：

```markdown
## Overview
Check model output for factual grounding.

## Input Definition
- `context_window`: Original context
- `model_output`: Model generated text

## Constraints
- Each atomic claim must be independently verified.

## Execution Flow

#### Step 1: extract_facts
- Type: LLM
- Task: Decompose model output into atomic factual claims
- Input: model_output
- Output: atomic_claims
- Output Format: {"claims": List[str]}
- Verify: none

#### Step 2: check_grounding (loop)
- Type: loop
- Collection: atomic_claims
- Element Var: claim
- Output: grounding_errors

  #### Step 2.1: judge_source
  - Type: LLM
  - Task: Judge if claim is grounded in context
  - Input: context_window, claim
  - Output: verdict
  - Verify: reverse

#### Step 3: output_report
- Type: flow
- Action: exit
- Output: grounding_errors

## Output Format
{"grounding_errors": List[dict]}

## Input Example
{"context_window": "...", "model_output": "..."}
```

---

## 七、models.py 变更

```python
class SpecLang(str, Enum):
    """Spec 文档语言"""
    ZH = "zh"
    EN = "en"
```

`SpecMode`（AOT/JIT）和 `SpecLang`（ZH/EN）是正交维度：

|  | AOT | JIT |
|--|-----|-----|
| ZH | 中文 Spec + 人类审计 | 中文 Spec + LLM 生成 |
| EN | 英文 Spec + 人类审计 | 英文 Spec + LLM 生成 |

---

## 八、API 设计

### 8.1 HopJIT

```python
# 中文 JIT（现有行为，完全兼容）
jit = HopJIT(hop_proc)
result = await jit.run(task_description="...", input_data={...})

# 英文 JIT
jit = HopJIT(hop_proc, lang=SpecLang.EN)
result = await jit.run(task_description="...", input_data={...})

# 预编译 Spec 执行（自动检测语言）
result = await jit.run_spec(spec_markdown=english_spec, input_data={...})
```

### 8.2 底层 API

```python
from hop_engine.jit.grammar import get_grammar, detect_lang, ZH_GRAMMAR, EN_GRAMMAR

# 显式指定语法解析
steps = parse_spec(spec_md, grammar=EN_GRAMMAR)

# 自动检测
lang = detect_lang(spec_md)
grammar = get_grammar(lang)
steps = parse_spec(spec_md, grammar=grammar)

# 验证（grammar 控制章节名，i18n 控制错误消息语言）
errors = validate_spec(steps, sections, grammar=grammar, mode=SpecMode.JIT)
```

### 8.3 向后兼容

所有 `grammar` 参数默认值为 `ZH_GRAMMAR`，**现有代码零改动**：

```python
# 这些调用继续正常工作，无需传 grammar
steps = parse_spec(spec_md)                          # 默认中文
errors = validate_spec(steps, sections)               # 默认中文
result = await jit.run(task_description="...", ...)   # 默认中文
```

---

## 九、不改的部分

| 内容 | 原因 |
|------|------|
| Python 日志消息 (`self.log.info(...)`) | 内部调试信息，不影响功能，保持中文 |
| docstring / 代码注释 | 不影响运行，保持中文 |
| 现有中文 HopSpec 文件 | 完全兼容，零改动 |
| 测试中的中文用例 | 保留，新增英文用例 |

---

## 十、文件清单

### 新建文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `hop_engine/jit/grammar.py` | ~120 | SpecGrammar 定义 + ZH/EN 语法 + detect_lang |
| `hop_engine/jit/i18n.py` | ~80 | `_()` 函数 + MESSAGES 消息表 |
| `Terms/HopSpec JIT模式速查.md` | ~150 | 英文速查文档（generator 注入用） |

### 修改文件

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `models.py` | +5 行 | 加 SpecLang 枚举 |
| `spec_parser.py` | ~30 行 | 正则/映射/章节名从 grammar 读取；`parse_spec`/`parse_full_spec` 加 `grammar` 参数 |
| `spec_validator.py` | ~60 行 | 章节名从 grammar 读取；错误消息改为 `_(...).format(...)` |
| `spec_executor.py` | ~20 行 | `_resolve_verifier` 用 `grammar.verifier_map`；code prompt 按 lang 切换 |
| `spec_generator.py` | ~25 行 | prompt 模板按 grammar 生成章节名和属性语言指示 |
| `hop_jit.py` | ~15 行 | 接受 `lang` 参数；`run_spec` 自动检测语言 |
| `__init__.py` | +2 行 | 导出 SpecLang |

### 测试文件

| 文件 | 改动 |
|------|------|
| `test_jit_parser.py` | 新增英文 Spec 解析用例；部分用例 `@pytest.mark.parametrize("grammar", [ZH_GRAMMAR, EN_GRAMMAR])` |
| `test_jit_validator.py` | 新增英文章节名验证；错误消息断言改为匹配 key 而非中文全文 |
| `test_jit_executor.py` | 新增英文核验值测试 |
| `test_jit_generator.py` | 新增英文 Spec 生成测试 |
| `test_i18n.py`（新建） | 消息完整性测试 + format key 一致性测试 |

---

## 十一、实现顺序

```
1. models.py          — 加 SpecLang 枚举
2. grammar.py         — SpecGrammar + ZH/EN 定义 + detect_lang
3. i18n.py            — _() + MESSAGES 消息表
4. spec_parser.py     — grammar 参数化
5. spec_validator.py  — grammar 参数化 + 错误消息 _() 化
6. spec_executor.py   — verifier_map + code prompt 双语
7. spec_generator.py  — prompt 模板双语化
8. hop_jit.py         — lang 参数透传 + run_spec 自动检测
9. __init__.py        — 导出 SpecLang
10. 英文速查文档       — Terms/HopSpec JIT Quick Reference.md
11. 测试              — 英文用例 + 参数化 + i18n 完整性测试
```

每步完成后运行 `cd hoplogic && uv run pytest test/ -v` 确认现有测试不破。

---

## 十二、验证

```bash
# 全量测试（确保中文兼容性不破）
cd hoplogic && uv run pytest test/ -v

# 双语测试
cd hoplogic && uv run pytest test/ -k "grammar or i18n or english or EN" -v

# 消息完整性
cd hoplogic && uv run pytest test/test_i18n.py -v
```

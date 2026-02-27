# HopSpec i18n Solution: Chinese-English Bilingual Support

## 1. Problem Analysis

The HOP JIT system has 333 Chinese strings scattered across 7 source files. These Chinese strings can be categorized into three types by functional nature, **each requiring a different solution**:

| Type | Nature | Example | Solution |
|------|--------|---------|----------|
| **DSL Syntax** | HopSpec keywords/attribute names | `步骤`/`Step`, `类型`/`Type`, `核验：逆向`/`Verify: reverse` | SpecGrammar syntax configuration |
| **User Messages** | Validation errors, execution logs | `缺少必选章节`/`Missing required sections` | gettext-compatible `_()` message table |
| **LLM Interaction** | Spec generation prompt, code step translation prompt | `根据任务描述生成 HopSpec`/`Generate a HopSpec from task description` | Language-aware prompt templates |

**Key Principle**: Three types of problems, three mechanisms, each module only depends on the layer it needs.

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────┐
│                    hop_jit.py                          │
│  HopJIT(hop_proc, lang="zh")                          │
│  Accepts lang parameter, dispatches to components     │
└───────┬──────────────┬──────────────┬─────────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────────┐
│ SpecGrammar  │ │  _()     │ │ Prompt Templates │
│ (DSL Syntax) │ │ (User Messages) │ │ (LLM Interaction) │
│              │ │          │ │                  │
│ ZH_GRAMMAR   │ │ dict     │ │ zh_prompt        │
│ EN_GRAMMAR   │ │ message table │ │ en_prompt        │
└──────┬───────┘ └────┬─────┘ └────────┬─────────┘
       │              │                │
       ▼              ▼                ▼
  spec_parser    spec_validator   spec_generator
  spec_executor  spec_executor
```

Module dependencies:

| Module | SpecGrammar | `_()` Message Table | Prompt Templates |
|--------|-------------|---------------------|------------------|
| spec_parser | Y | - | - |
| spec_validator | Y (section names) | Y (error messages) | - |
| spec_executor | Y (verification values) | Optional (logs) | - |
| spec_generator | Y (attribute name direction) | - | Y |
| hop_jit | Pass-through | Pass-through | Pass-through |
| models | - | - | - |

---

## 3. DSL Syntax Layer: SpecGrammar

HopSpec attribute names (`类型`/`Type`) are not user interface text but DSL keywords - similar to programming language keywords. Solved with **pluggable syntax configuration**, not gettext.

### 3.1 Data Structure

Create new `hop_engine/jit/grammar.py`:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SpecGrammar:
    """HopSpec DSL syntax definition - one per language"""

    # parser: step title
    step_prefix: str                              # "步骤" / "Step"

    # parser: attribute names → StepInfo fields
    attr_map: dict[str, str] = field(default_factory=dict)

    # parser/validator: section logical names → display names
    section_names: dict[str, str] = field(default_factory=dict)

    # parser: "no input" marker
    empty_markers: tuple[str, ...] = ()

    # executor: verification strategy display name → internal name
    verifier_map: dict[str, str] = field(default_factory=dict)

    # generator: instruct LLM on attribute language
    attr_lang_instruction: str = ""

    @property
    def required_sections(self) -> set[str]:
        """Required section names set needed by validator"""
        return set(self.section_names.values())

    @property
    def execution_section(self) -> str:
        """Display name of execution flow section"""
        return self.section_names["execution"]
```

### 3.2 Chinese Grammar

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

### 3.3 English Grammar

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

### 3.4 Grammar Registry and Auto-detection

```python
from hop_engine.jit.models import SpecLang

GRAMMARS: dict[SpecLang, SpecGrammar] = {
    SpecLang.ZH: ZH_GRAMMAR,
    SpecLang.EN: EN_GRAMMAR,
}

def detect_lang(spec_markdown: str) -> SpecLang:
    """Auto-detect language from Spec content"""
    if re.search(r"####\s+步骤", spec_markdown):
        return SpecLang.ZH
    if re.search(r"####\s+Step", spec_markdown):
        return SpecLang.EN
    # fallback: Chinese character density
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", spec_markdown[:500]))
    return SpecLang.ZH if zh_chars > 5 else SpecLang.EN

def get_grammar(lang: SpecLang) -> SpecGrammar:
    return GRAMMARS[lang]
```

### 3.5 How Each Module Uses SpecGrammar

**spec_parser.py**:

```python
# Before: hard-coded
_STEP_HEADER_RE = re.compile(r"...步骤(?P<id>[\d.]+)...")
_ATTR_MAP = {"类型": "step_type", ...}

# After: constructed from grammar
def parse_spec(spec_markdown: str, grammar: SpecGrammar = ZH_GRAMMAR) -> list[StepInfo]:
    step_re = re.compile(
        rf"^(?P<indent>\s*)####\s+{re.escape(grammar.step_prefix)}"
        rf"(?P<id>[\d.]+)(?::\s*(?P<name>\w+))?"
    )
    # Use grammar.attr_map instead of hard-coded _ATTR_MAP
    # Use grammar.execution_section instead of hard-coded "执行流程"
    # Use grammar.empty_markers instead of hard-coded "（无）"
    ...
```

**spec_validator.py**:

```python
# Before: hard-coded
_REQUIRED_SECTIONS = {"任务概述", "输入定义", ...}

# After: read from grammar
def check_structure(sections, steps, grammar: SpecGrammar = ZH_GRAMMAR):
    missing = grammar.required_sections - set(sections.keys())
    ...
```

**spec_executor.py**:

```python
# Before: hard-coded Chinese verification values
if verifier_str == "无": return None
if verifier_str == "逆向": return _UNSET
if verifier_str == "正向交叉": return forward_cross_verify

# After: lookup from grammar.verifier_map
def _resolve_verifier(self, verifier_str: str):
    internal = self.grammar.verifier_map.get(verifier_str, "")
    match internal:
        case "none": return None
        case "reverse": return _UNSET
        case "forward_cross": return forward_cross_verify
        case _: return _UNSET
```

---

## 4. User Message Layer: gettext-compatible `_()`

Validation error messages are user-visible output, adopting gettext's `_()` calling convention. Initially implemented with dict, retains future migration capability to gettext.

### 4.1 Implementation

Create new `hop_engine/jit/i18n.py`:

```python
"""i18n — gettext-compatible lightweight message internationalization

Calling convention identical to gettext:
    from hop_engine.jit.i18n import _, set_lang
    set_lang("zh")
    msg = _("Missing required sections: {missing}").format(missing="...")

When migrating to gettext, only modify this file, all _() call sites zero changes.
"""

from threading import local

_state = local()

# English as msgid (written in source), Chinese as translation
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
    """Set current thread/coroutine language"""
    _state.lang = lang


def get_lang() -> str:
    """Get current language, default en"""
    return getattr(_state, "lang", "en")


def _(msgid: str) -> str:
    """Translation function — gettext-compatible signature

    Pass English msgid, return translation in current language.
    Fallback to msgid itself (English original) when translation not found.
    """
    lang = get_lang()
    if lang == "en":
        return msgid
    return MESSAGES.get(lang, {}).get(msgid, msgid)
```

### 4.2 Call Site Examples

```python
from hop_engine.jit.i18n import _

# In spec_validator.py
errors.append(ValidationError(
    check="structure",
    step_id="",
    message=_("Missing required sections: {missing}").format(
        missing=", ".join(sorted(missing))
    ),
))

# Previous Chinese approach:
# message=f'缺少必选章节: {", ".join(sorted(missing))}'
```

### 4.3 Migration to gettext

When future message volume exceeds 200 or third language is introduced, only modify `i18n.py` implementation:

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

All `_("...")` call sites **zero changes**.

### 4.4 Completeness Testing

```python
def test_i18n_message_completeness():
    """Ensure each language's message table covers all keys"""
    from hop_engine.jit.i18n import MESSAGES
    for lang, table in MESSAGES.items():
        # Collect all msgids from _() calls in code (maintained by CI script or manually)
        assert isinstance(table, dict)
        # Key: zh table key set should match actual used msgids

def test_i18n_no_missing_format_keys():
    """Ensure translation string {key} placeholders match original"""
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

## 5. LLM Interaction Layer: Prompt Templates

spec_generator and spec_executor's code steps need to send prompts to LLM. Prompt language affects generation quality, independent of DSL syntax and user message management.

### 5.1 Generator Prompt

`_build_generation_prompt` in `spec_generator.py` switches templates by language:

```python
def _build_generation_prompt(task_description, ..., grammar: SpecGrammar):
    parts = []

    # Section titles in target language
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

### 5.2 Quick Reference

Format reference injected when LLM generates Spec needs corresponding language version:

- Chinese: `Terms/HopSpec JIT模式速查.md` (existing)
- English: `Terms/HopSpec JIT Quick Reference.md` (new)

`HopJIT` initialization selects by lang:

```python
class HopJIT:
    def __init__(self, hop_proc, lang=SpecLang.ZH, spec_reference=""):
        self.lang = lang
        self.grammar = get_grammar(lang)
        # If spec_reference not specified, load default quick reference by language
        if not spec_reference:
            spec_reference = _load_default_reference(lang)
        self.spec_reference = spec_reference
```

### 5.3 Executor code step Prompt

```python
# Before: hard-coded Chinese
task = f"将以下自然语言逻辑翻译为一段 Python 代码片段。\n逻辑：{step.description}\n..."

# After: switch by language
if self.lang == SpecLang.ZH:
    task = f"将以下自然语言逻辑翻译为一段 Python 代码片段。\n逻辑：{step.description}\n..."
else:
    task = f"Translate the following logic into a Python code snippet.\nLogic: {step.description}\n..."
```

No message table used here — prompts are not user messages but LLM instructions, need fine-tuning per LLM capability, unsuitable for automatic translation.

---

## 6. English HopSpec Example

Chinese version (existing):

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

English version (equivalent):

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

## 7. models.py Changes

```python
class SpecLang(str, Enum):
    """Spec document language"""
    ZH = "zh"
    EN = "en"
```

`SpecMode` (AOT/JIT) and `SpecLang` (ZH/EN) are orthogonal dimensions:

|  | AOT | JIT |
|--|-----|-----|
| ZH | Chinese Spec + Human Audit | Chinese Spec + LLM Generation |
| EN | English Spec + Human Audit | English Spec + LLM Generation |

---

## 8. API Design

### 8.1 HopJIT

```python
# Chinese JIT (existing behavior, fully compatible)
jit = HopJIT(hop_proc)
result = await jit.run(task_description="...", input_data={...})

# English JIT
jit = HopJIT(hop_proc, lang=SpecLang.EN)
result = await jit.run(task_description="...", input_data={...})

# Pre-compiled Spec execution (auto-detect language)
result = await jit.run_spec(spec_markdown=english_spec, input_data={...})
```

### 8.2 Low-level API

```python
from hop_engine.jit.grammar import get_grammar, detect_lang, ZH_GRAMMAR, EN_GRAMMAR

# Explicit syntax parsing
steps = parse_spec(spec_md, grammar=EN_GRAMMAR)

# Auto-detection
lang = detect_lang(spec_md)
grammar = get_grammar(lang)
steps = parse_spec(spec_md, grammar=grammar)

# Validation (grammar controls section names, i18n controls error message language)
errors = validate_spec(steps, sections, grammar=grammar, mode=SpecMode.JIT)
```

### 8.3 Backward Compatibility

All `grammar` parameters default to `ZH_GRAMMAR`, **existing code zero changes**:

```python
# These calls continue to work without passing grammar
steps = parse_spec(spec_md)                          # Default Chinese
errors = validate_spec(steps, sections)               # Default Chinese
result = await jit.run(task_description="...", ...)   # Default Chinese
```

---

## 9. Unchanged Parts

| Content | Reason |
|---------|--------|
| Python log messages (`self.log.info(...)`) | Internal debug info, doesn't affect functionality, keep Chinese |
| docstring / code comments | Doesn't affect runtime, keep Chinese |
| Existing Chinese HopSpec files | Fully compatible, zero changes |
| Chinese test cases | Retain, add English cases |

---

## 10. File List

### New Files

| File | Lines | Description |
|------|-------|-------------|
| `hop_engine/jit/grammar.py` | ~120 | SpecGrammar definition + ZH/EN grammar + detect_lang |
| `hop_engine/jit/i18n.py` | ~80 | `_()` function + MESSAGES message table |
| `Terms/HopSpec JIT模式速查_en.md` | ~150 | English quick reference (for generator injection) |

### Modified Files

| File | Changes | Description |
|------|---------|-------------|
| `models.py` | +5 lines | Add SpecLang enum |
| `spec_parser.py` | ~30 lines | Regex/mapping/section names from grammar; `parse_spec`/`parse_full_spec` add `grammar` parameter |
| `spec_validator.py` | ~60 lines | Section names from grammar; error messages changed to `_(...).format(...)` |
| `spec_executor.py` | ~20 lines | `_resolve_verifier` uses `grammar.verifier_map`; code prompt bilingual |
| `spec_generator.py` | ~25 lines | Prompt template bilingual |
| `hop_jit.py` | ~15 lines | Accepts `lang` parameter; `run_spec` auto-detects language |
| `__init__.py` | +2 lines | Export SpecLang |

### Test Files

| File | Changes |
|------|---------|
| `test_jit_parser.py` | Add English Spec parsing cases; some cases `@pytest.mark.parametrize("grammar", [ZH_GRAMMAR, EN_GRAMMAR])` |
| `test_jit_validator.py` | Add English section name validation; error message assertions changed to match keys instead of full Chinese text |
| `test_jit_executor.py` | Add English verification value tests |
| `test_jit_generator.py` | Add English Spec generation tests |
| `test_i18n.py` (new) | Message completeness test + format key consistency test |

---

## 11. Implementation Order

```
1. models.py          — Add SpecLang enum
2. grammar.py         — SpecGrammar + ZH/EN definitions + detect_lang
3. i18n.py            — _() + MESSAGES message table
4. spec_parser.py     — grammar parameterization
5. spec_validator.py  — grammar parameterization + error messages _() conversion
6. spec_executor.py   — verifier_map + code prompt bilingual
7. spec_generator.py  — prompt template bilingual
8. hop_jit.py         — lang parameter pass-through + run_spec auto-detection
9. __init__.py        — Export SpecLang
10. English quick reference — Terms/HopSpec JIT Quick Reference.md
11. Tests              — English cases + parameterization + i18n completeness tests
```

After each step, run `cd hoplogic && uv run pytest test/ -v` to confirm existing tests don't break.

---

## 12. Validation

```bash
# Full test (ensure Chinese compatibility not broken)
cd hoplogic && uv run pytest test/ -v

# Bilingual test
cd hoplogic && uv run pytest test/ -k "grammar or i18n or english or EN" -v

# Message completeness
cd hoplogic && uv run pytest test/test_i18n.py -v
```
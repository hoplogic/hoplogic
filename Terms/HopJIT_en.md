# HOP JIT: LLM-Generated HopSpec + Runtime Interpretation

## Motivation: AOT vs JIT

The current HOP uses **AOT (Ahead-of-Time)** mode:

```
Human writes Task.md → /task2spec generates HopSpec.md → /spec2code generates Hop.py → Execute
```

This pipeline works well for **fixed, repeatedly executed tasks** (like phishing detection, fact-checking), but is too heavy for **immediate, one-time tasks**.

**JIT (Just-in-Time)** mode upgrades HOP from a "programming framework" to a "metaprogramming framework":

```
User task description → LLM generates HopSpec → Deterministic validation → Engine interprets and executes
```

LLM "programs" within a constrained DSL (6 atomic types, tree structure), and the engine interprets and executes the generated program at runtime. Each LLM step still maintains verification loops.

## Architecture

```
User task description
    │
    ▼
┌─────────────────────────┐
│ Spec Generator           │  LLM generates HopSpec (1 LLM call)
│ Input: Task + HopSpec    │  Input context injects reference docs as format guide
└─────────────────────────┘
    │ HopSpec markdown
    ▼
┌─────────────────────────┐
│ Spec Parser              │  Parse markdown → StepInfo tree (pure Python)
└─────────────────────────┘
    │ List[StepInfo]
    ▼
┌─────────────────────────┐
│ Spec Validator           │  6 structural audits (pure Python, zero LLM cost)
│ ✗ → Return error, regenerate │
└─────────────────────────┘
    │ validated List[StepInfo]
    ▼
┌─────────────────────────┐
│ Spec Executor            │  Traverse StepInfo tree, dispatch by type to HopSession operators
│ LLM → hop_get/hop_judge  │  Each step with verification
│ code → LLM translation + exec │
│ loop/branch → control flow dispatch │
└─────────────────────────┘
    │
    ▼
  Structured result JSON
```

## Dual-Layer Verification Design

JIT mode has **two layers** of verification:

### Layer 1: Spec Level (Deterministic)

Spec Validator performs 6 pure Python validations on LLM-generated HopSpec:

1. **Structural Integrity** — All 6 sections present, ends with flow:exit
2. **Type Correctness** — Valid types, flow continue/break within loops
3. **Tree Structure Compliance** — No jumps, container attributes complete
4. **Data Flow Connectivity** — Every input has preceding output
5. **Verification Policy Coverage** — LLM step verification declarations (warning level)
6. **Naming Conventions** — snake_case, unique step_name

If validation fails, returns error info for LLM regeneration. Zero LLM cost, pure structural audit.

### Layer 2: Execution Level (LLM Verification)

When SpecExecutor executes each LLM step, it still uses HopSession's verification loop (reverse verification/forward cross/tool verification). This is HOP engine's original verification capability, fully reused by JIT.

## File Structure

```
hoplogic/hop_engine/jit/
├── __init__.py              # Export public API
├── models.py                # StepInfo, ValidationError, ContinueSignal, BreakSignal
├── spec_parser.py           # HopSpec markdown → StepInfo tree
├── spec_validator.py        # 6 deterministic validations
├── spec_executor.py         # Interpret and execute StepInfo tree
├── spec_generator.py        # LLM generates HopSpec
└── hop_jit.py               # Top-level orchestration
```

## API Usage Examples

### Full Auto JIT (Dynamic Generation + Execution)

```python
from hop_engine.processors.hop_processor import HopProc
from hop_engine.config.model_config import ModelConfig
from hop_engine.jit import HopJIT

hop_proc = HopProc(
    run_model_config=ModelConfig.from_yaml("settings.yaml", "system_model_config"),
    verify_model_config=ModelConfig.from_yaml("settings.yaml", "verify_model_config"),
)

# spec_reference automatically loads from embedded resources (Chinese/English by i18n)
# Can also explicitly pass custom content to override defaults
jit = HopJIT(hop_proc)

result = await jit.run(
    task_description="Perform three-stage audit of LLM output: factuality, logical entailment, self-consistency",
    input_data={"context_window": "...", "model_output": "..."},
    output_schema='{"reliability_score": int, "errors": list, "verification_summary": str}',
)

print(result["result"])   # Structured execution result
print(result["spec"])     # Generated HopSpec (auditable, savable)
print(result["stats"])    # Operator statistics
```

### Pre-compiled Spec Execution (Existing HopSpec)

```python
spec_md = open("Tasks/Verify/Hoplet/HopSpec.md").read()

result = await jit.run_spec(
    spec_markdown=spec_md,
    input_data={"context_window": "...", "model_output": "..."},
)
```

### Parse + Validate Only (No Execution)

```python
from hop_engine.jit import parse_full_spec, validate_spec

parsed = parse_full_spec(open("Tasks/Verify/Hoplet/HopSpec.md").read())
errors = validate_spec(parsed["steps"], parsed["sections"])

for e in errors:
    print(f"[{e.check}] Step {e.step_id}: {e.message}")
```

## Comparison with Pure Agent

| Dimension | Pure Agent (AutoGPT style) | HOP JIT |
|-----------|---------------------------|---------|
| Planning | LLM free planning | LLM plans within DSL constraints |
| Validation | No structural validation | 6 deterministic Spec validations |
| Execution | LLM autonomous decisions | Engine schedules by tree structure |
| Verification | None/manual | Automatic verification per step |
| Auditable | Log level | Spec level (readable/savable/replayable) |
| Repeatable | Low | High (deterministic execution with same Spec) |

Core difference: Agent's "brain" is in LLM's next-step decision; JIT's "brain" is in deterministic tree traversal. LLM only fills content for each node, doesn't determine execution order.

## code Step Execution Strategy

The `description` (logic field) of `code` steps is natural language description. JIT uses LLM to translate it into Python code snippets, then executes in a restricted environment.

Restricted environment only exposes:
- Input variables + safe built-in functions (len, sum, max, min, range, zip, etc.)
- json module
- No dangerous modules like os, sys, subprocess

Each code step consumes 1 lightweight LLM call (no verification). Future versions may achieve zero LLM cost through template matching for common patterns (merge lists, filter, assemble dict).

## Limitations

1. **code steps require LLM translation**: Current implementation consumes LLM calls for code steps
2. **hoplet/MCP calls not implemented**: call steps currently only support tool calls
3. **Limited error recovery**: When a step fails, can only continue with subsequent steps, cannot rollback
4. **Concurrency not optimized**: loop steps currently execute sequentially, doesn't utilize asyncio.gather
5. **Spec caching not implemented**: Same task description regenerates Spec every time

## Relationship with AOT

JIT doesn't replace AOT, but complements it:

- **AOT**: Suitable for fixed tasks, human-tuned Spec and Code, optimal quality
- **JIT**: Suitable for immediate tasks, rapid prototyping, or automated Spec generation in AOT pipeline

JIT-generated Spec can be saved and enter AOT pipeline for further refinement:

```
JIT generates Spec → Save as HopSpec.md → /verifyspec → /spec2code → Enter AOT iteration
```
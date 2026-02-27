# HopSpec JIT Mode Quick Reference (LLM Generated Reference)

> In JIT mode, `loop` supports **for-each** (iterating over collections) and **while** (conditional loops, must set `max_iterations > 0`, engine automatically injects iteration limit protection). step_name can be omitted.

## Core Rules

- Execution flow is a **structured tree**: sequential execution, no jumps, nested expressions
- After `loop`/`branch` completes, automatically proceeds to the next sibling step, no jump declaration needed
- Step title: `#### Step N: step_name` (step_name can be omitted, auto-generated when omitted), step_name is snake_case English (2-4 words), unique within Spec

## 6 Atomic Types

| Type     | Meaning                        | Node Nature |
| -------- | ------------------------------ | ----------- |
| `LLM`    | LLM execution (with verification) | Leaf        |
| `call`   | External call (tool/Hoplet/MCP)   | Leaf        |
| `loop`   | Iterate collection (for-each), child steps indented nested | Container   |
| `branch` | Conditional branch, child steps indented nested | Container   |
| `code`   | Pure Python calculation (no LLM) | Leaf        |
| `flow`   | Flow control (exit/continue/break) | Leaf        |

**Type Selection**: Use `LLM` for LLM tasks, `code` for pure calculations, `call` for external calls. The distinction between get/judge within `LLM` is inferred by AI from task description, not distinguished at Spec level.

## Node Properties Quick Reference

### LLM

```markdown
#### Step N: step_name
- Type: LLM
- Task: <LLM task description>
- Input: <variable name list>
- Output: <variable name>
- Output Format: <JSON structure>          # Optional
- Verification: reverse/positive cross/none        # Optional, default reverse
- Notes: <execution points>              # Optional
```

### call

```markdown
#### Step N: step_name
- Type: call
- Call Target: tool/hoplet/mcp    # Required
- Task: <call target description>
- Input: <variable name list>
- Output: <variable name>
- Tool Domain: <domain identifier>              # Required for tool
- Hoplet Path: <path>            # Required for hoplet
- MCP Service: <service identifier>           # Required for mcp
```

### loop (for-each only)

```markdown
#### Step N: step_name (loop)
- Type: loop
- Iterate Collection: <collection variable name>
- Element Variable: <loop variable name>
- Output: <result collection variable name>        # Optional

  #### Step N.1: child_step
  - Type: ...
```

### branch

```markdown
#### Step N: step_name (branch)
- Type: branch
- Condition: <Python boolean expression>

  #### Step N.1: child_step
  - Type: ...
```

For multiple conditions, use sequential branch (if A → if B), no else.

### code

```markdown
#### Step N: step_name
- Type: code
- Logic: <natural language calculation description>
- Input: <variable name list>
- Output: <variable name>
```

### flow

```markdown
#### Step N: step_name          # exit: terminate flow
- Type: flow
- Action: exit
- Output: <return variable name>
- Exit ID: <EXIT_ID>          # Optional

#### Step N: step_name          # continue/break: must be inside loop
- Type: flow
- Action: continue/break
- Target Loop: <step_name of the loop>
```

## Writing Conventions

- Use **Chinese** for property names, **English snake_case** for variable names
- Input lists comma-separated: `Input: context, claim`
- Output format uses JSON Schema style: `{"claims": List[str]}`
- Conditions use Python syntax: `Condition: status == "FAIL"`
- When verification is omitted, use default (LLM default reverse), write `Verification: none` to explicitly skip
- step_name can be omitted (when omitted, engine auto-generates `stepN` format name)

## Document Structure

```markdown
## Task Overview
<one-sentence goal>

## Input Definition
- `var`: description

## Hard Constraints
- <non-violable rules>

## Execution Flow
#### Step 1: ...
...
#### Step N: output
- Type: flow
- Action: exit
- Output: final_result

## Output Format
<JSON structure description>

## Input Log Example
<example JSON>
```

## Compact Example

```
Step 1: extract_facts        LLM     → atomic_claims
Step 2: check_grounding      loop(atomic_claims → claim)
 └ Step 2.1: judge_source    LLM     → verdict → grounding_errors
Step 3: check_logic          LLM     → logic_errors
Step 4: check_consistency    LLM     → is_consistent
Step 5: handle_inconsistency branch(is_consistent == False)
 └ Step 5.1: list_conflicts  LLM     → consistency_errors
Step 6: merge_errors         code    → all_errors
Step 7: score_reliability    LLM     → report
Step 8: assemble_report      code    → final_report
Step 9: output_report        flow:exit → final_report
```
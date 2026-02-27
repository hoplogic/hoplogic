# HopSpec Format Specification

## Design Motivation

### Current Problems

Current common Spec formats use free-text markdown with two main issues:

1. **Lack of structured atomic types**. Common SPEC's `WHEN...THEN` only describes linear transitions between tasks, unable to express patterns like "iterate over a collection" (loop) or "execute different sub-processes after conditional branching" (branch). These patterns exist extensively in actual logic but are hidden in free-text "execution points" at the Spec level.

2. **Ambiguous mapping from Spec to code**. Free-text requires AI to guess loop structures and branch conditions. After atomization, **structural** level mapping becomes deterministic. LLM invocation semantics (extraction vs judgment) can be inferred by AI from task descriptions without explicit distinction at the Spec level.

### Inspiration Source

Oracle [Open Agent Specification](https://github.com/oracle/agent-spec) defines a set of atomic node types (AgentNode, ToolNode, MapNode, BranchingNode, etc.) for declaratively describing Agent workflows. HopSpec borrows its **component typology** concept but maintains markdown format (instead of YAML) and adds HOP-specific verification semantics.

### Theoretical Foundation

HopSpec's tree structure inherits from **structured programming** paradigm (Böhm-Jacopini 1966 proved three control structures are computationally complete; Dijkstra 1968 argued goto makes programs hard to reason about). When the executor changes from reliable CPU to hallucinating LLM, the need for structural constraints becomes even stronger—this is the fundamental reason HopSpec chooses nested trees over DAG/cyclic graphs, and the core divergence from graph-based workflow frameworks like LangGraph, CrewAI, Dify. See `Terms/HOP 2.0 Technical Positioning.md` § HopSpec Design Philosophy.

---

## Core Rules: Structured Tree, No Jumps

HopSpec's execution flow is a **structured tree** following these rules:

1. **Sequential execution**: Same-level steps execute top-to-bottom in order
2. **No jumps**: Any step cannot reference step numbers of non-child steps (no goto)
3. **Scope closure**: `loop` and `branch` can only contain their own child steps, automatically returning to parent after child steps complete
4. **Nested expression**: Complex control flow expressed through nesting (stepN → stepN.M → stepN.M.K), not through jumps

### Step Identification: Number + Semantic Name

Each step title format is `#### StepN: step_name`, containing two parts:

| Part | Purpose | Example | Stability |
|------|---------|---------|-----------|
| **StepN** (number) | Reading order, sequentially numbered top-to-bottom | Step1, Step2, Step2.1 | Renumbered on insert/delete |
| **step_name** (semantic name) | Identity for Spec↔Code alignment | extract_atomic_facts | Unchanged with renumbering |

**step_name naming rules**:
- snake_case English, derived from task description
- Concise (2-4 words), e.g. `extract_atomic_facts`, `check_grounding`, `merge_errors`
- Unique within same Spec
- Child steps of container nodes independently named (no parent prefix needed)

**Why need both parts**: Numbers facilitate human reading ("Step3 follows Step2") but get reordered on insertion. step_name is stable anchor, `/specdiff`, `/specsync`, `/code2spec` align Spec with Code through it, unaffected by renumbering.

This directly corresponds to Python block structure:

```
HopSpec Tree                                    Python Code
──────────                                    ──────────
Step1: extract_info                           # Step1: extract_info — LLM
Step2: process_items (loop)                    # Step2: process_items — loop
  Step2.1: analyze_item                           # Step2.1: analyze_item — LLM
  Step2.2: check_condition (branch)               # Step2.2: check_condition — branch
    Step2.2.1: handle_special                          # Step2.2.1: handle_special — LLM
Step3: summarize                              # Step3: summarize — LLM
```

After `loop` and `branch` complete, control flow **automatically** falls to next sibling step. No need to declare "jump to StepX after completion".

---

## Atomic Step Types

Each HopSpec step must declare an atomic type. All 7 types:

| Atomic Type | Meaning | Corresponding Code | Node Nature |
|-------------|---------|-------------------|-------------|
| `LLM` | LLM execution (with verification) | `await s.hop_get(...)` or `await s.hop_judge(...)` | Leaf |
| `call` | External call (tool/Hoplet/MCP) | `await s.hop_tool_use(...)` / function call / MCP | Leaf |
| `loop` | Loop (for-each collection iteration / while condition loop) | for: `for item in collection:` / while: `while condition:` | Container |
| `branch` | Conditional branch | `if condition:` | Container |
| `code` | Pure Python computation (no LLM) | Regular Python code | Leaf |
| `flow` | Flow control (exit/continue/break) | `return` / `continue` / `break` | Leaf |
| `subtask` | Subtask block (static/dynamic/think) (historical alias `seq_think` remains compatible) | Predefined sub-steps / JIT generation / six-stage structured thinking | Container |

### What Needs Formalization, What Doesn't

HopSpec design principle: **Only formalize what AI easily guesses wrong, rest use natural language**.

**Needs formalization** (7 atomic types):

- Whether to call LLM (`LLM` vs `code`)—AI might delegate pure computation to LLM
- External calls (`call`)—need to declare call target (tool/Hoplet/MCP) and corresponding parameters
- Loop structures (`loop`)—define tree nesting levels
- Branch structures (`branch`)—define tree nesting levels
- Flow control (`flow`)—change control flow (exit/continue/break), `continue`/`break` need verification scope is within `loop`
- Subtask blocks (`subtask`)—declare expansion mode (static/dynamic/think), static has predefined sub-steps, dynamic/think generate at runtime

**Doesn't need formalization, natural language suffices**:

| Natural Language | Code Mapping | Reason |
|------------------|--------------|--------|
| "extract/analyze/decompose" | `hop_get` | Verb semantics unambiguous |
| "judge/verify/check" | `hop_judge` | Verb semantics unambiguous |
| "concurrent processing per element" | `asyncio.gather` | Python basic syntax |

These are Python basic concepts, LLM inference when generating code is unambiguous. Inventing formal symbols for them at Spec level is over-engineering.

### Sub-process: Hoplet Composition

HopSpec doesn't support Agent Spec's FlowNode (sub-process nesting). Complex task decomposition achieved through **Hoplet composition**: Each Hoplet is an independent executable unit (with its own HopSpec + Hop.py), Hoplets call each other through `call` node declarations.

```python
# Main flow Hop.py calls sub Hoplet
from Tasks.SubTask.Hoplet.Hop import run as sub_run

async with hop_proc.session() as s:
    status, result = await s.hop_get(task="Main task first step", ...)
    # Call sub Hoplet
    sub_result = await sub_run(hop_proc, input_data=result)
    status, final = await s.hop_get(task="Continue based on subtask result", context=sub_result)
```

At Spec level, sub-process calls use `call` + `call target: hoplet`:

```markdown
#### StepN: call_subtask
- Type: call
- Call target: hoplet
- Task: Call SubTask Hoplet to process intermediate results
- Hoplet path: Tasks/SubTask/Hoplet/Hop.py
- Input: intermediate_result
- Output: sub_result
```

This continues HOP's core concept: **Python is control flow**. Sub-process orchestration doesn't need framework-level abstraction, Python's function calls are the best composition mechanism. `call` nodes make call relationships visible and auditable at Spec level.

---

## Node Attribute Specifications

### LLM (LLM Execution Node)

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `LLM` |
| Task | **Yes** | Task for LLM to execute, natural language description |
| Input | **Yes** | Data source, reference previous step output variables |
| Output | **Yes** | Variable name produced by this step |
| Output format | No | Structured output format description, maps to `return_format` |
| Verification | No | Verification strategy: `reverse` (default) / `positive_cross` / `none` / `<custom verifier name>` |
| Description | No | Execution points, constraints, domain knowledge. Supports natural language description of control flow details (e.g. "skip if condition not met") |
| Data tags | No | XML tag mapping for input variables in LLM prompt. Tag names at least two words, snake_case, avoid engine reserved words. E.g. `model_output → <model_output>` `context → <reference_doc>` |

```markdown
#### StepN: step_name
- Type: LLM
- Task: <LLM task description using XML tags to reference data, e.g. "analyze content in <model_output>">
- Input: <variable name list>
- Output: <variable name>
- Output format: <structure description>
- Verification: reverse
- Data tags: variable_name → <xml_tag_name> (when variable name itself unsuitable as tag)
- Description: <execution points>
```

### call (External Call Node)

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `call` |
| Call target | **Yes** | `tool` / `hoplet` / `mcp` / `rag` |
| Task | **Yes** | Target description for the call |
| Input | **Yes** | Data source |
| Output | **Yes** | Variable name produced by this step |
| Tool domain | Conditional | Required when `tool`, tool domain identifier (e.g. `all`, `security`) |
| Hoplet path | Conditional | Required when `hoplet`, e.g. `Tasks/SubTask/Hoplet/Hop.py` |
| MCP service | Conditional | Required when `mcp`, MCP service identifier |
| RAG collection | Conditional | Optional when `rag`, knowledge base name (default `default`) |
| Verification | No | Verification strategy (`tool` defaults to `tool_use_verifier`) |
| Description | No | Call constraints |

```markdown
#### StepN: step_name (tool call)
- Type: call
- Call target: tool
- Task: <tool call target>
- Tool domain: <domain identifier>
- Input: <variable name list>
- Output: <variable name>

#### StepN: step_name (sub Hoplet call)
- Type: call
- Call target: hoplet
- Task: <sub-process target description>
- Hoplet path: <Tasks/.../Hoplet/Hop.py>
- Input: <variable name list>
- Output: <variable name>

#### StepN: step_name (MCP service call)
- Type: call
- Call target: mcp
- Task: <tool_name: call description>
- MCP service: <server identifier name, corresponding to key in mcp.servers in settings.yaml>
- Input: <variable name list>
- Output: <variable name>

> **Task format convention**: `tool_name: natural language description`. Before colon is MCP tool name (exact match with registered tool on server), after colon is context description for LLM (JIT mode LLM can reference). Can also omit colon and use tool name directly.

#### StepN: step_name (RAG retrieval)
- Type: call
- Call target: rag
- Task: Retrieve domain knowledge related to <query_variable>
- RAG collection: <collection_name>
- Input: <variable name list>
- Output: <variable name>
```

### loop (Loop Container Node)

loop supports two modes: **for-each** (iterate collection) and **while** (condition loop).

#### for-each mode

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `loop` |
| Iterate collection | **Yes** | Collection variable name to iterate |
| Element variable | **Yes** | Loop variable name, child steps reference current element through this |
| Output | No | Collection variable name to collect child step results |
| Description | No | Natural language explanation (for domain experts) |

```markdown
#### StepN: step_name (loop)
- Type: loop
- Iterate collection: <collection variable name>
- Element variable: <loop variable name>
- Output: <result collection variable name>

  #### StepN.1: child_step_name
  - Type: ...
```

**Semantics**: For each element in `iterate collection`, execute all child steps in order. Child steps can only reference `element variable` and outer existing variables. After completion, automatically continue to Step N+1.

**Applicable scope**: Both AOT and JIT modes available.

#### while mode

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `loop` |
| Condition | **Yes** | Python boolean expression, continue loop when true |
| Max iterations | No | Safety limit to prevent infinite loops |
| Output | No | Collection variable name to collect child step results |
| Description | No | Natural language explanation (for domain experts) |

```markdown
#### StepN: step_name (loop)
- Type: loop
- Condition: <Python boolean expression>
- Max iterations: <optional safety limit>
- Output: <result collection variable name>

  #### StepN.1: child_step_name
  - Type: ...
```

**Semantics**: When condition is true, repeat executing child steps. Re-evaluate condition after each round. Force terminate when reaching max iterations.

**Applicable scope**: Both AOT and JIT modes available. In JIT mode while loop must set `max iterations > 0` (engine automatically injects loop iteration limit protection to prevent infinite loop thread leaks).

**Attribute mutual exclusion**: `iterate collection` and `condition` are mutually exclusive. With `iterate collection` → for-each mode; with `condition` without `iterate collection` → while mode.

### branch (Conditional Branch Container Node)

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `branch` |
| Condition | **Yes** | Boolean expression, execute child steps when true |

```markdown
#### StepN: step_name (branch)
- Type: branch
- Condition: <boolean expression>

  #### StepN.1: child_step_name
  - Type: ...

  #### StepN.2: another_child
  - Type: ...
```

**Semantics**: When condition is true, execute child steps in order; when false, skip all child steps. After completion (whether entering branch or not), automatically continue to Step N+1.

Multiple conditional branches expressed through **sequential branch**:

```markdown
#### StepN: handle_fail (branch)
- Type: branch
- Condition: status == "FAIL"

  #### StepN.1: exit_fail
  - Type: flow
  - Action: exit
  - Output: error_result
  - Exit identifier: EXIT_FAIL

#### StepN+1: handle_uncertain (branch)
- Type: branch
- Condition: status == "UNCERTAIN"

  #### Step(N+1).1: supplementary_check
  - Type: LLM
  - Task: supplementary verification
  - ...
```

Equivalent to Python:

```python
if status == "FAIL":
    return error_result
if status == "UNCERTAIN":
    result = await s.hop_get(task="supplementary verification", ...)
```

### code (Pure Computation Node)

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `code` |
| Logic | **Yes** | Natural language description of pure computation logic (no LLM calls) |
| Input | **Yes** | Variables used |
| Output | **Yes** | Produced variable |

```markdown
#### StepN: step_name
- Type: code
- Logic: <natural language computation description>
- Input: <variable name list>
- Output: <variable name>
```

### flow (Flow Control Node)

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `flow` |
| Action | **Yes** | `exit` / `continue` / `break` |
| Output | Conditional | Required for `exit` (return variable name), not needed for `continue`/`break` |
| Exit identifier | No | Optional for `exit`, used for `hop_exit` tracking |
| Target loop | Conditional | Required for `continue`/`break`, reference step_name of `loop` containing this step |

```markdown
#### StepN: step_name (exit)
- Type: flow
- Action: exit
- Output: <variable name>
- Exit identifier: <EXIT_ID>

#### StepN: step_name (skip current element)
- Type: flow
- Action: continue
- Target loop: <step_name of loop containing this step>

#### StepN: step_name (interrupt iteration)
- Type: flow
- Action: break
- Target loop: <step_name of loop containing this step>
```

**Scope rules**:
- `exit`: Can appear anywhere, terminate entire flow
- `continue`: Must be in child step (including nested) of some `loop`, skip current element continue next
- `break`: Must be in child step (including nested) of some `loop`, prematurely end entire iteration

### subtask (Subtask Container Node)

subtask supports three expansion modes: **static** (predefined sub-steps), **dynamic** (JIT runtime generation or load solidified path), **think** (six-stage structured thinking).

#### Common attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| Type | **Yes** | Fixed value `subtask` |
| Expansion | **Yes** | `static` / `dynamic` / `think` |
| Input | No | Input variable list |
| Output | Conditional | Required for dynamic/think |
| Max depth | No | Maximum nesting depth (default 0 → effective value 3; 1=leaf prohibits nesting; N=allows N-1 layers of child subtasks) |

#### static mode

| Attribute | Required | Description |
|-----------|----------|-------------|
| Sub-steps | **Yes** | Predefined sub-steps (indented nesting) |

```markdown
#### StepN: step_name (subtask)
- Type: subtask
- Expansion: static
- Input: <variable name list>
- Output: <variable name>

  #### StepN.1: child_step_name
  - Type: LLM
  - ...

  #### StepN.2: another_child
  - Type: code
  - ...
```

**Semantics**: Sequentially execute predefined sub-steps, collect output after completion. Equivalent to encapsulation of logically related steps.

#### dynamic mode

| Attribute | Required | Description |
|-----------|----------|-------------|
| Task | **Yes** | Natural language description of subtask |
| Output | **Yes** | Output variable list |
| Max steps | No | Upper limit for generated sub-steps (default 10, must > 0) |
| Constraints | No | Allowed sub-step types (comma separated, default `LLM,code,call,branch`) |
| Solidified path | No | `.spec.md` file path, preferentially loaded when exists |
| Sub-steps | Prohibited | dynamic should not have predefined sub-steps |

```markdown
#### StepN: step_name (subtask)
- Type: subtask
- Expansion: dynamic
- Task: <subtask description>
- Input: <variable name list>
- Output: <variable name>
- Max steps: 10
- Constraints: LLM,code,call,branch
- Solidified path: <path/to/solidified.spec.md>
```

**Semantics**: Runtime generation of execution plan by LLM and execution. If solidified path exists, preferentially load verified step sequence.

#### think (Structured Thinking) mode

| Attribute | Required | Description |
|-----------|----------|-------------|
| Task | **Yes** | Natural language description of subtask |
| Output | **Yes** | Output variable list |
| Max steps | No | Upper limit for sub-steps generated per round (default 10, must > 0) |
| Max iterations | No | Upper limit for iteration rounds (default 5, must > 0) |
| Constraints | No | Allowed sub-step types (comma separated, default `LLM,code,call,branch`) |
| Sub-steps | Prohibited | think should not have predefined sub-steps |

```markdown
#### StepN: step_name (subtask)
- Type: subtask
- Expansion: think
- Task: <subtask description>
- Input: <variable name list>
- Output: <variable name>
- Max steps: 10
- Max iterations: 5
- Constraints: LLM,code,call,branch
```

**Semantics**: Six-stage structured thinking (Decompose -> Plan -> Execute+Monitor -> Reflect -> Revise -> Synthesize), after each round of reflection judge convergence, if not converged revise plan and retry. Throw external interaction signal on continuous failure.

**Nesting constraints**: subtask supports limited depth nesting, controlled through `max depth` attribute (default 3 layers). When effective depth ≤ 1, `subtask` in `constraints` attribute is automatically removed. Child subtask effective depth must be less than parent.

**Progressive path**: think's successful path can be solidified into `.spec.md` file, loaded by dynamic mode; after human review can be converted to static mode predefined sub-steps.

See `hoplogic/docs/hop_subtask.md` for details.

---

## Attribute Writing Conventions

1. **Step title format**: `#### StepN: step_name` or `#### StepN: step_name (type annotation)`. step_name uses snake_case English, derived from task description, unique within same Spec
2. **Attribute names use natural language**, consistent with natural language Spec style. AI maps to corresponding parameter names during code generation
3. **Variable names use lowercase English + underscore** (snake_case), consistent with Python variable naming
4. **Boolean expressions** (branch conditions) use Python syntax for direct mapping
5. **Input variable lists** comma separated: `Input: context_window, claim`
6. **Output format** described in JSON Schema style: `{"claims": List[str]}`
7. **Verification strategy** uses default when omitted (`LLM` defaults to reverse verification). Explicitly write `Verification: none` to skip semantic verification (e.g. reverse verification, positive cross verification), but format verification (`format_verifier`) always automatically applied to all LLM steps as pre-check for all verifications. When semantic verifier specified, execution order is `format_verifier` -> semantic verifier, format check failure directly triggers retry. Format verification detects "serialization residue" in structured output—any level that should be dict/list but was stringified by LLM triggers retry. Format verification doesn't call LLM, zero additional overhead
8. **Description field** is free text, can contain supplementary constraints and domain knowledge
9. **LLM step data reference tags**: When `LLM` step task description needs to reference input data, use descriptive XML tags to wrap data, tag names at least two words, snake_case, avoid engine reserved words (`context`, `input`, `output`). E.g. `<model_output>`, `<reference_doc>`, `<claim_list>`. Prohibit generic single-word tags like `<context>`, `<text>`, `<data>`. This ensures LLM accurately associates references in task description with actual data
10. **flow node actions**: `exit` (exit), `continue` (skip current element), `break` (interrupt iteration). `continue`/`break` must reference step_name of `loop` containing this step through `target loop` attribute
11. **call node call targets**: `tool` (tool call), `hoplet` (sub Hoplet call), `mcp` (MCP service call), `rag` (RAG knowledge base retrieval). Different targets require different conditional attributes (tool domain/Hoplet path/MCP service/RAG collection)

---

## Complete Example: Verify Task

```markdown
## Task Overview

Perform three-stage logical verification audit on LLM-generated reasoning output, quantitatively assess hallucination, output structured report.

## Input Definition

- `context_window`: Context/reference document
- `model_output`: LLM-generated reasoning or answer

## Hard Constraints

- Even for widely accepted facts, if not mentioned in context_window, must mark as external knowledge leakage
- Any step not strictly derivable from premises must mark as derivation incoherence

## Execution Flow

#### Step1: extract_atomic_facts
- Type: LLM
- Task: Decompose model output into independent atomic fact statements, each containing only one knowledge point
- Input: model_output
- Output: atomic_claims
- Output format: {"claims": List[str]}
- Verification: none

#### Step2: check_grounding (loop)
- Type: loop
- Iterate collection: atomic_claims
- Element variable: claim
- Output: grounding_errors

  #### Step2.1: judge_claim_source
  - Type: LLM
  - Task: Determine source type of atomic statement (Pass/External/Fabrication), find evidence in context_window
  - Input: context_window, claim
  - Output: verdict
  - Output format: {"verdict": str, "location": str, "evidence": str}
  - Description:
    • Pass = explicit original text support in context
    • External = not mentioned in context, external knowledge leakage
    • Fabrication = pure fabrication
    • When verdict not Pass, record in grounding_errors

#### Step3: check_logic
- Type: LLM
- Task: Analyze derivation relationships between reasoning steps, detect implication breaks, probability jumps, concept drift, sycophancy
- Input: context_window, model_output
- Output: logic_errors
- Output format: {"errors": List[str], "locations": List[str], "evidences": List[str], "severities": List[str]}

#### Step4: check_consistency
- Type: LLM
- Task: Verify reasoning self-consistency—counterfactual interference test + internal conflict detection
- Input: context_window, model_output
- Output: is_consistent

#### Step5: handle_inconsistency (branch)
- Type: branch
- Condition: is_consistent == False

  #### Step5.1: list_conflicts
  - Type: LLM
  - Task: List internal conflicts and counterfactual insensitivity issues in reasoning
  - Input: context_window, model_output
  - Output: consistency_errors
  - Output format: {"conflicts": List[str], "evidences": List[str]}

#### Step6: merge_errors
- Type: code
- Logic: Merge grounding_errors + logic_errors + consistency_errors into all_errors
- Input: grounding_errors, logic_errors, consistency_errors
- Output: all_errors

#### Step7: score_reliability
- Type: LLM
- Task: Comprehensive reliability score (0-100) based on three-stage audit results and generate one-sentence summary
- Input: all_errors
- Output: report
- Output format: {"reliability_score": int, "verification_summary": str}
- Verification: none

#### Step8: assemble_report
- Type: code
- Logic: Assemble final report (reliability_score, hallucination_detected, errors, verification_summary)
- Input: report, all_errors
- Output: final_report

#### Step9: output_report
- Type: flow
- Action: exit
- Output: final_report

## Output Format

{
  "reliability_score": 0-100,
  "hallucination_detected": true/false,
  "errors": [{"type": str, "location": str, "evidence": str, "severity": str}],
  "verification_summary": str
}

## Input Log Example

{
  "context_window": "According to 2023 annual report, Company A's annual revenue was 12 billion...",
  "model_output": "Company A's 2023 revenue was 12 billion, growth 15%..."
}
```

---

## Tree Structure Visualization

The Verify example's structure tree:

```
Step1: extract_atomic_facts     LLM        → atomic_claims
Step2: check_grounding          loop(atomic_claims)
 └ Step2.1: judge_claim_source  LLM        → verdict → grounding_errors
Step3: check_logic              LLM        → logic_errors
Step4: check_consistency        LLM        → is_consistent
Step5: handle_inconsistency     branch(is_consistent == False)
 └ Step5.1: list_conflicts      LLM        → consistency_errors
Step6: merge_errors             code       → all_errors
Step7: score_reliability        LLM        → report
Step8: assemble_report          code       → final_report
Step9: output_report            flow:exit(final_report)
```

Note:

- Step5 (branch) doesn't reference Step6. After Step5 completes, automatically falls to Step6.
- Step2 (loop) doesn't reference Step3. After child steps in loop execute for each element, automatically falls to Step3.
- No step references non-child step numbers. Control flow completely determined by **hierarchical nesting + sequential execution**.

---

## Why Prohibit Jumps

### 1. Consistent with Python Block Structure

Python has no goto. `for`/`if`/`while` are all blocks—enter block, execute content, exit block, continue next line. HopSpec's loop/branch directly correspond to this model. Jumps are graph concepts (Burr, Agent Spec), not Python concepts.

### 2. More Reliable AI Code Generation

Jumps mean AI needs to understand global topology—"Step5 jumps to Step8" implies "Step6,7 are skipped". Nested structure is local—each branch only needs to see its own child steps, doesn't need to understand entire tree. Locality makes AI generate code with fewer errors.

### 3. Spec Review Doesn't Need Diagrams

With jumps, reviewers need to draw control flow graphs in mind to understand flow. After prohibiting jumps, reading top-to-bottom is execution order, encountering indentation means nested blocks.

### 4. flow is the Only "Break Out"

`flow` nodes contain three actions: `exit` (equivalent to `return`) terminates entire flow, `continue` skips current loop element, `break` interrupts entire loop. None are "jump to some step"—`exit` terminates flow, `continue`/`break` change behavior of nearest `loop`. These are structured programming's allowed non-sequential control flows, scope constrained by `target loop` attribute.

---

## Spec ↔ Code Mapping

### Deterministic Mapping (Structure Layer)

Each step's step_name maps to code comment anchor: `# StepN: step_name — type — task`

| Spec Type | Python Code |
|-----------|-------------|
| `LLM` + `output format` | `# StepN: step_name — LLM` + `await s.hop_get(task=..., return_format=...)` |
| `LLM` (task description is judgment semantics) | `# StepN: step_name — LLM` + `await s.hop_judge(task=...)` |
| `call` + `call target: tool` | `# StepN: step_name — call` + `await s.hop_tool_use(task=..., tool_domain=...)` |
| `call` + `call target: hoplet` | `# StepN: step_name — call` + `from <path> import <func>; result = await <func>(...)` |
| `call` + `call target: mcp` | `# StepN: step_name — call` + `result = await mcp_client.call(...)` |
| `loop` + child steps | `# StepN: step_name — loop` + `for item in collection:` / `while condition:` + indented block |
| `branch` + child steps | `# StepN: step_name — branch` + `if condition:` + indented block |
| `code` | `# StepN: step_name — code` + pure Python assignment/computation |
| `flow` + `action: exit` | `# StepN: step_name — flow` + `session.hop_exit(...)` + `return` |
| `flow` + `action: continue` | `# StepN: step_name — flow` + `continue` |
| `flow` + `action: break` | `# StepN: step_name — flow` + `break` |
| `subtask` (static) | `# StepN: step_name — subtask` + child step sequential execution block |
| `subtask` (dynamic) | `# StepN: step_name — subtask` + JIT generation or load solidified spec then execute |
| `subtask` (think) | `# StepN: step_name — subtask` + six-stage structured thinking |

### AI Inference Mapping (Semantic Layer)

| Spec Natural Language | Python Code | Inference Basis |
|-----------------------|-------------|-----------------|
| Task description "extract/analyze/decompose" | `hop_get` | Verb semantics |
| Task description "judge/verify/check" | `hop_judge` | Verb semantics |

Structure layer mapping is deterministic (Spec type → code structure one-to-one). Semantic layer mapping inferred by AI from natural language, inference basis unambiguous.

### `/verifyspec` Audit Capability

HopSpec's structured design enables `/verifyspec` to automatically audit Spec in 6 aspects:

1. **Structure completeness**: Whether 6 sections (task overview, input definition, hard constraints, execution flow, output format, input log example) are complete, whether execution flow ends with `flow` (action: exit)
2. **Atomic type correctness**: Whether each step declares type, whether LLM/code/call distinctions are correct, whether `continue`/`break` in `flow` are within `loop`
3. **Tree structure compliance**: No jump references, whether `loop`/`branch` child steps are correctly indented, whether `branch` conditions are deterministic Python expressions
4. **Data flow tracking**: Whether each input variable has preceding step output, whether each output variable is consumed by subsequent steps, whether `loop` child steps reference element variables
5. **Verification strategy review**: Mark steps without explicit verification strategy declaration, suggest stronger verification for high-risk steps. Domain experts can decide verification strategy (reverse/positive/tool/none/custom) during Spec review phase, no need to wait until after code generation
6. **Attribute and naming conventions**: Required attributes complete, variable names snake_case, step numbers continuous, step_name unique and correctly formatted

---

## AOT/JIT Dual Mode

HopSpec supports two execution modes, declared through `mode` attribute in Spec header:

| Mode | Meaning | Applicable Scenario |
|------|---------|---------------------|
| **AOT** (Ahead-Of-Time) | Complete predefined flow, all steps determined before execution | Fixed flow, high auditability requirement tasks |
| **JIT** (Just-In-Time) | Runtime dynamic decision of next step, LLM selects steps based on current state | Exploratory tasks, conversational interaction, tasks with uncertain step count |

### Mode Constraints on Atomic Types

| Atomic Type | AOT | JIT | Description |
|-------------|-----|-----|-------------|
| `LLM` | Available | Available | Both modes supported |
| `call` | Available | Available | Both modes supported |
| `loop` (for-each) | Available | Available | Iterate bounded collection, both modes safe |
| `loop` (while) | Available | Available | JIT mode must set `max iterations > 0` (automatic iteration protection injection) |
| `branch` | Available | Available | Both modes supported |
| `code` | Available | Available | Both modes supported |
| `flow` | Available | Available | Both modes supported |
| `subtask` (static) | Available | Available | Predefined sub-steps, both modes supported |
| `subtask` (dynamic) | Available | Available | JIT generation or load solidified path |
| `subtask` (think) | Available | Available | Six-stage structured thinking, interactive mode supports external interaction signals |

### Default Mode

When `mode` attribute not declared, defaults to **AOT** mode.

---

## Interactive/Batch Dual Mode

Hoplet supports two run modes, declared through `run mode` attribute in metainfo.md:

| Mode | Meaning | Applicable Scenario |
|------|---------|---------------------|
| **Interactive** (default) | Pause on LACK_OF_INFO/UNCERTAIN, wait for external feedback for next steps | CLI single execution, View UI execution |
| **Batch** | Return directly on LACK_OF_INFO/UNCERTAIN without waiting for feedback | Batch testing, automation pipeline |

### Main Function Return Convention

Main function `main_hop_func` returns `(HopStatus, str)` tuple, consistent with operator return pattern:

| status | Meaning | Interactive Mode Behavior | Batch Mode Behavior |
|--------|---------|--------------------------|---------------------|
| OK | Normal completion | Output result | Output result |
| LACK_OF_INFO | LLM reasoning layer insufficient info | CLI/UI prompts for supplementary info, retry after add_feedback | Return directly |
| UNCERTAIN | LLM uncertain | CLI/UI displays suggestions, retry after add_feedback | Return directly |
| FAIL | Failure (transport/verification/capability) | Output error, no feedback loop | Output error |

> **FAIL vs LACK_OF_INFO boundary**: Pre-pipeline failures (RAG retrieval no results, data source unreachable, etc.) should return `FAIL` before calling LLM operator. `LACK_OF_INFO` only for LLM operator self-reported reasoning layer information deficiency—`add_feedback` only affects LLM conversation history, cannot fix pipeline layer issues. On FAIL should call `hop_exit` to close session; on LACK_OF_INFO/UNCERTAIN do not call `hop_exit`, keep session active waiting for feedback.

### Interactive Mode Code Mapping

Interactive mode manifests as CLI feedback loop in Hop.py's `main()` entry:
- Check main_hop_func returned status
- FAIL → directly output error, no feedback loop (pre-pipeline failure or LLM transport/verification failure)
- LACK_OF_INFO → print missing_info, wait for user input supplementary info
- UNCERTAIN → print suggestions, wait for user choice direction
- Inject feedback through `session.add_feedback()`, re-invoke main_hop_func

In View mode, Transport layer (app.py/web.py) maps feedback loop to UI interaction (display feedback form, re-execute after submission). FAIL results do not display feedback forms.

---

## Relationship with Agent Spec

| Agent Spec Concept | HopSpec Equivalent | Differences |
|--------------------|--------------------|-------------|
| AgentNode | LLM | HOP has built-in verification; get/judge inferred by AI |
| ToolNode | call (call target: tool) | HOP has built-in tool verification |
| MapNode | loop | Same concept; HopSpec uses indented nesting instead of edge references |
| BranchingNode | branch | Same concept; HopSpec child steps embedded, prohibit jumping to external nodes |
| FlowNode (sub-process) | call (call target: hoplet) / subtask | HOP declares Hoplet calls through `call`, `subtask` supports dynamic sub-process generation |
| StartNode / EndNode | implicit / flow (action: exit) | First step is start |
| ControlFlowEdge | prohibited | HopSpec uses hierarchical nesting instead of explicit edges |
| Serialization format | Markdown | Agent Spec uses YAML/JSON; HOP uses Markdown |
| Verification declaration | yes | Agent Spec has no this concept |

**Core difference**: Agent Spec is a **graph** (nodes + edges), HopSpec is a **tree** (hierarchical nesting + sequential execution). Graphs need jumps (edges), trees don't. Trees directly map to Python's indented block structure, embodying HOP's "Python is control flow" concept at Spec level.
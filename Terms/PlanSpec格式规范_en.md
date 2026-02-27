# PlanSpec Format Specification

> JIT Component Version: v0.12.0

## Design Motivation

### Current Problems

In long-running tasks, the executor (LLM agent / HOP engine) experiences working memory decay, leading to:

- **Goal drift**: Gradually deviating from original requirements
- **Constraint forgetting**: Losing hard constraints when context window scrolls
- **Repetitive work**: Forgetting completed steps and re-executing them
- **Inability to resume**: Cannot continue from breakpoint after interruption

HopSpec's tree structure naturally solves these problems (observable progress, constraint binding, resumable execution), but HopSpec is too heavy—7 atomic step types, 25+ attributes, strict verification semantics—not suitable for rapid planning scenarios.

### PlanSpec Positioning

PlanSpec is a **lightweight subset** of HopSpec, supporting complete planning and think mode dynamic structured thinking:

| Dimension | HopSpec | PlanSpec |
|-----------|---------|----------|
| Step Types | 7 types (LLM/call/loop/branch/code/flow/subtask) | 4 types (reason/act/decide/subtask) |
| Step Attributes | 25+ (return_format, verifier, call_target, ...) | ~10 (description, outputs, detail, inputs, result, status, ...) |
| Data Flow | inputs/outputs required | `→ outputs` summary line recommended, `← inputs` detail section optional |
| Verification Semantics | Mandatory (reverse/forward cross/tool verification) | None (result records actual completion) |
| Progress Tracking | None (static specification) | Built-in (status + progress) |
| Node Details | Multi-line heading + attribute list | `>` node body (collapsible) |
| Generation Cost | High (LLM needs to understand complex format) | Low (LLM can quickly generate) |
| Use Cases | Executable agent programs | Task planning, progress tracking, structured thinking |

Core principle: **PlanSpec is the planning view of HopSpec, with bidirectional conversion between them**.

PlanSpec is designed for LLM generation and consumption, not for human writing. Therefore, format design prioritizes **compactness** (saving tokens) and **machine parsability** over human editing friendliness.

---

## PlanSpec Format Definition (LLM Prompt Ready)

PlanSpec is a compact text representation of structured planning trees. Used for task planning, progress tracking, and structured thinking.

**Document Structure**:

```
# Plan: <title>                              # Optional, planning title
Goal: <one-sentence goal>                    # Required
> <additional explanation>                   # Goal continuation line (optional)
Constraints:                                 # Optional, constraint list
- <constraint 1>
- <constraint 2>
## Steps                                    # Required, step tree
1. [x] [reason] Analyze input data quality issues → data_profile
  > ← raw_data                              # Node body: input declaration (optional)
  > Output missing rates per column, outlier proportions  # Node body: constraints/hints (optional)
2. [x] [act] Clean data → cleaned | completed      # [x]=done, | followed by result
3. [>] [subtask] Iterate training until reach the target threshold → model    # Typical structured thinking loop
  3.1. [x] [act] Train model and cross-validate → cv_metrics | Gini=0.35
  3.2. [x] [reason] Diagnose model weaknesses, suggest adjustments → adjustments
  3.3. [>] [decide] Whether reach the target threshold                 # Container: children are branch conditions
    3.3.1. [act]Reach the target threshold → output final model
    3.3.2. [act] Not reach the target threshold → apply adjustments, continue next round
4. [act] Generate report → report
```

**Summary Line** (one line per step):
- `N.` — Numbering, supports multi-level nesting (`1.`, `2.1.`, `2.1.3.`)
- `[status]` — Status markers: `[ ]` pending / `[x]` done / `[>]` active / `[!]` blocked / `[~]` skipped, omitted equals pending
- `[type]` — Step type, 4 types:
  - `reason` — Reasoning/analysis (leaf)
  - `act` — Execute action/computation (leaf)
  - `decide` — Conditional decision, children are branches (example step 3.3 above)
  - `subtask` — Subtask decomposition, children are sub-step sequences (example step 3: iteration loop)
- `description` — LLM-oriented task description (80-130 chars, semantically complete, know what to do from one line)
- `→ outputs` — Output variable declaration, comma-separated (`→ var1, var2`)
- `| result` — Actual completion status (filled after execution)
- `| Progress: N/M` — Iteration progress (done/total), only for loop-type subtasks

Among these, status, result, Progress are optional; outputs are recommended for each step (ensures complete data flow).

**Node Body** (`>` lines): After summary line, before next step, lines starting with `>` provide execution details, constraints, format requirements. `> ← inputs` declares input variables (optional, explicitly overrides data flow derivation).

**Tree structure encoded by step ID**: `2.1` is a child of `2`, `2.1.3` is a child of `2.1`. Indentation is only visual aid, parser builds tree based on step ID hierarchy.

**Prompt Architecture** (four stages):

| Stage | LLM Received Context | LLM Task |
|-------|---------------------|----------|
| **Generation** (plan generation) | Task description + PlanSpec format template | Generate complete PlanSpec document |
| **Step Execution** (step execution) | Step's own task/inputs/outputs + run_history | Execute current step (history provides implicit reflection context) |
| **Step Reflection** (step reflection) | status + result + plan_state + can_interact | Triggered when `status != OK`, decide retry/skip/adjust/report |
| **End-of-round Re-planning** (re-plan) | Current plan state + structural command list (ADD/REVISE/REPLAN) | When round doesn't converge, structurally adjust plan |

Engine automatically manages step status (DONE/BLOCKED/SKIP). LLM modifies plan structure through `PLAN_CMD:` commands during step reflection and re-planning stages. See [Think Reflection Protocol](#think-reflection-protocol) and [Command Protocol (PLAN_CMD)](#command-protocol-plan_cmd) sections.

---

## Document Structure

A complete PlanSpec document contains four sections:

```
# Plan: <title>
Goal: <one-sentence goal>
> <additional explanation>
Constraints:
- <constraint 1>
- <constraint 2>
## Steps
1. [x] [type] description → outputs | actual result
  > ← inputs (optional)
  > detail line (node body)
2. [>] [type] description → outputs
  2.1. [type] description → outputs
```

| Section | Required | Description |
|---------|----------|-------------|
| `# Plan: <title>` | No | Planning title, `# Plan:` prefix optional |
| `Goal: <goal>` | **Yes** (validation requirement) | One-sentence description of planning goal |
| `> <additional explanation>` | No | Goal continuation line, provides additional context |
| `Constraints:` | No | Constraint list, each starting with `- ` |
| `## Steps` | **Yes** (validation requirement) | Step tree, at least one step |

Parser compatible with `**Goal**:` and `## Constraints` syntax (backward compatible), but canonical format is `Goal:` and `Constraints:`.

---

## Step Types

PlanSpec defines 4 step types, each corresponding to a cognitive action category:

| Type | Meaning | Typical Verbs | Can Have Children |
|------|---------|---------------|:-----------------:|
| `reason` | Reasoning/analysis | analyze, infer, extract, summarize, verify | No |
| `act` | Execute action | compute, filter, call, write | No |
| `decide` | Conditional decision | judge, select, branch | **Yes** |
| `subtask` | Subtask decomposition | decompose, traverse, iterate | **Yes** |

### Container Constraints

Only `subtask` and `decide` can contain sub-steps (children). `reason`, `act` are leaf nodes.

This aligns with HopSpec's structural rules: container nodes (loop/branch/subtask) can nest, leaf nodes (LLM/code/call/flow) cannot.

### Type Selection Guide

```
Need LLM reasoning/analysis/verification?
  ├─ Yes → reason
  └─ No → Is it deterministic computation/action?
           ├─ Yes → act
           └─ No → Has multiple branch paths?
                    ├─ Yes → decide (children = each branch)
                    └─ No → subtask (children = sub-steps)
```

---

## Step Format

### Summary Line

Each step's summary occupies one line, format:

```
N. [status] [type] description → outputs | result | Progress: N/M
```

| Part | Required | Description |
|------|----------|-------------|
| `N.` | **Yes** | Step numbering, supports multi-level (`1.`, `2.1.`, `2.1.3.`) |
| `[status]` | No | Status marker, omitted means pending |
| `step_name` | No | Unique identifier, omitted in LLM generation, external tools can inject (e.g., 8hex) |
| `[type]` | **Yes** | Step type, enclosed in brackets |
| `description` | No | LLM-oriented descriptive task description (80-130 chars, semantically complete) |
| `→ outputs` | Recommended | Output variable declaration, comma-separated (`→ var1, var2`) |
| `| result` | No | Actual completion status filled after execution (no label) |
| `| Progress: N/M` | No | Iteration progress (done_count/total_count) |

**description design**: Oriented for LLM consumption, not human scanning 3-5 word labels. LLM should know what to do and how from one summary line.

**`→ outputs` design**: Output variables declared at end of summary line (before `|` separator). These are data produced by this step, downstream steps can reference. Encourage declaring outputs for each step to ensure complete data flow during PlanSpec → HopSpec conversion.

**step_name design**: LLM doesn't need to name steps when generating PlanSpec (reduces generation load), external tools (e.g., HOP engine) can later inject unique identifiers (e.g., 8-digit hex) as anchors. Named step format: `N. [status] step_name [type] description`.

### Node Body (> detail)

After summary line, can follow multiple lines starting with `>` providing execution details:

```
1. [reason] Analyze data distribution and quality issues → data_profile, clean_suggestions
  > ← synthetic_data
  > Output data_profile includes missing rates per column, distribution types, outlier proportions
  > clean_suggestions as action list, each with column, strategy, params
```

| Element | Format | Description |
|---------|--------|-------------|
| `← inputs` | `> ← var1, var2` | Input variable declaration (optional, explicitly overrides data flow derivation) |
| detail | `> <any text>` | Constraints, format requirements, execution hints, acceptance criteria |

**`← inputs` design**: Placed in node body rather than summary line, keeping summary line compact. Lines starting with `← ` in `>` are parsed as input declarations, removed from detail after parsing. inputs are optional—engine can automatically derive data flow from previous steps' outputs. But **encourage declaring inputs during planning** to ensure no gaps during PlanSpec → HopSpec conversion.

**Node body uses**:
- Execution constraints and acceptance criteria
- Output format descriptions (field structure, types)
- LLM execution hints (analysis dimensions, focus points)
- Input declarations (`← inputs`)

### Status Markers

| Marker | Status | Meaning |
|--------|--------|---------|
| `[ ]` | pending | Pending execution (omitted in serialization) |
| `[x]` | done | Completed |
| `[>]` | active | In progress |
| `[!]` | blocked | Blocked |
| `[~]` | skipped | Skipped |

Pending status omits marker in serialized output, i.e., `1. [type]` equivalent to `1. [ ] [type]`.

### Tree Structure

**Nesting levels encoded by step ID**, not heading level. `2.1` is child of `2`, `2.1.3` is child of `2.1`. Indentation (2 spaces/level) is only visual aid, parser doesn't depend on indentation:

```
1. [subtask] Process all items → results
  1.1. [act] Process item A → item_a_result
    1.1.1. [reason] Verify item A → verification
```

Nesting depth has no hard limit (no longer constrained by markdown heading level).

### Inline Attributes

After `→ outputs` in summary line, can append optional attributes separated by `|`:

```
1. [x] [reason] Break output into claims → claims | Extracted 12 atomic claims
2. [subtask] Process all items → results | Progress: 3/5
3. [x] [reason] Check results → verdicts | All 10 checks passed | Progress: 10/10
```

| Attribute | Format | Description |
|-----------|--------|-------------|
| outputs | `→ var1, var2` | Step output variables (before `|`) |
| result | `| <actual completion>` | Completion status filled after execution (no label) |
| Progress | `| Progress: N/M` or `| Progress: N` | Iteration progress (done_count/total_count) |

All attributes are optional. Segments after `|` not starting with `Progress:` are treated as result.

### Comparison with HopSpec Attributes

| HopSpec Attribute | PlanSpec Equivalent | Status |
|-------------------|---------------------|--------|
| Type | `[type]` (summary line) | Simplified |
| Task | description (summary line) | Simplified |
| Inputs | `← inputs` (node body, optional) | Simplified (optional declaration in detail section) |
| Outputs | `→ outputs` (summary line) | **Explicit declaration** |
| Output Format | Node body detail | Simplified (natural language description) |
| Verification | — | Omitted (result records actual outcome) |
| Description | Node body detail | Expanded (multi-line detail expansion) |
| Call Target | — | Omitted |
| Traversal Collection / Element Variables | — | Omitted |
| Condition | description (merged) | Simplified |
| Expansion Mode | — | Omitted |

---

## Folding Rules

PlanSpec supports **collapse/expand** of node bodies, which is a **rendering behavior** (detail always exists in file, renderer decides display depth based on status).

### Status-based Folding (Default Rules)

| Status | Summary Line | `>` Node Body | children | `| result` |
|--------|--------------|---------------|----------|-------------|
| `[x]` done | Show | **Collapse** | Show | Show |
| `[>]` active | Show | **Expand** | Show | — |
| `[ ]` pending | Show | **Collapse** | Show | — |
| `[!]` blocked | Show | **Expand** | Show | — |
| `[~]` skipped | Show | **Collapse** | Show | — |

Under default rules, children are always visible (maintaining tree structure overview), only `> detail` folds based on status.

### Explicit Expand/Collapse (EXPAND / COLLAPSE)

Users or tools (e.g., `/showplan`) can explicitly override default folding rules via API for context window management:

| API | Effect | Use Case |
|-----|--------|----------|
| `expand_step(plan, step_id)` | Force show detail + children | Want to see detailed content of a folded node |
| `collapse_step(plan, step_id)` | Force hide detail + children | Release context space |

**Priority**: Explicit flags > status default rules.

| expanded flag | `>` node body | children |
|---------------|---------------|----------|
| `True` (EXPAND) | **Show** | **Show** |
| `False` (COLLAPSE) | **Hide** | **Hide** |
| `None` (default) | Follow status rules | Always show |

`expanded` is a transient rendering flag, not involved in serialization/parsing (not written to plan file). Effective when `serialize_plan(fold=True)`, ignored when `fold=False` (default).

**Typical Scenarios**:
- In large plans focusing only on step 5, COLLAPSE 1-4 and 6-7 to save context
- After completed subtask COLLAPSED, entire subtree collapses to one line
- Want to see execution details of a done step, EXPAND temporarily

**Design Rationale**:
- **done collapse**: Completed steps only need to see results, details no longer important
- **active expand**: Currently executing steps need complete context
- **pending collapse**: Not yet executed steps only need to know intent, details expand during execution
- **blocked expand**: Blocked steps need to see details to diagnose issues

### Folding Example

Complete file content:
```
1. [x] [act] Generate synthetic policy data → synthetic_data | Generated 10K rows
  > Fields: policy_no, vehicle_age, driver_age
  > claim_flag positive rate ~15%
2. [>] [reason] Analyze data quality → data_profile, suggestions
  > ← synthetic_data
  > Analysis dimensions: missing rate, distribution type, outlier proportion
3. [subtask] Clean data based on LLM profile → cleaned_data
  > ← data_profile, suggestions
  > Execute cleaning strategy per LLM recommendations
```

Folded rendering (/showplan output):
```
1  [x]  [ACT]      Generate synthetic policy data → synthetic_data | Generated 10K rows
2  [>]  [REASON]   Analyze data quality → data_profile, suggestions
                   > ← synthetic_data
                   > Analysis dimensions: missing rate, distribution type, outlier proportion
3  [ ]  [SUBTASK]  Clean data based on LLM profile → cleaned_data
```

---

## Think Reflection Protocol

PlanSpec drives iterative reasoning in think mode (`subtask(think)`). Reflection is not an independent phase—it is embedded in each step's execution.

### Design Principle

LLM API is stateless, each call resends complete context. `hop_get` carries previous steps' execution records through session's `run_history`, so LLM already has **implicit reflection capability** when executing each step—it can see what was done before and the results.

Engine's responsibility is not "reflect for LLM", but:
1. **Ensure context availability** (run_history already does this)
2. **Intervene when failure signals appear** (rather than blindly continue)
3. **Provide structured plan view** (history has raw execution records, but lacks global plan state)

### Reflection Trigger

After each step execution, engine checks operator's returned `HopStatus`:

| HopStatus | Triggers Reflection | Meaning |
|-----------|:-------------------:|---------|
| `OK` | No | Normal completion, continue to next step |
| `FAIL` | **Yes** | Execution failure (transmission/verification/tool) |
| `UNCERTAIN` | **Yes** | Uncertain result |
| `LACK_OF_INFO` | **Yes** | Insufficient information |

Trigger condition: `status != OK`.

### Reflection Input

Context received by LLM during reflection:

| Input | Source | Description |
|-------|--------|-------------|
| `status` | Operator return | FAIL / UNCERTAIN / LACK_OF_INFO |
| `result` | Operator return | Specific error message or uncertain content |
| `plan_state` | `serialize_plan(fold=True)` | Current plan progress (folded version) |
| `can_interact` | Run mode (metainfo) | Environment: can ask user questions |

### Reflection Output

LLM makes autonomous decisions based on context. Decisions fall into two categories:

**Engine Actions** (LLM indicates engine execution through structured returns):

| Decision | Meaning | Use Case |
|----------|---------|----------|
| RETRY | Re-execute current step | FAIL + transient error, UNCERTAIN + strong downstream dependency |
| ACCEPT | Accept current result, continue | UNCERTAIN + downstream insensitive |
| INTERACT | Report to user requesting input | LACK_OF_INFO + interactive |

**PLAN_CMD Commands** (modify plan structure):

| Command | Meaning | Use Case |
|---------|---------|----------|
| SKIP | Skip current step | FAIL + unrecoverable |
| REVISE | Revise subsequent steps to adapt | Previous step failed/skipped, downstream needs adjustment |
| ADD | Insert remedial/alternative steps | LACK_OF_INFO + batch mode, need alternative path |

**Key Design**: Decisions judged by LLM in plan context, not hard-coded by engine. Engine only detects signals, provides context, executes decisions/commands.

### Step Reflection vs End-of-round Re-planning

| Mechanism | Trigger Timing | Scope | Role |
|-----------|----------------|-------|------|
| **Step Reflection** | `status != OK` (after each step) | Current step + subsequent adjustment | Immediate response to failure |
| **End-of-round re-plan** | After all steps in round executed, not converged | Entire plan | Structural adjustment fallback |

Step reflection handles local issues (immediate response to single step failure), re-planning handles global issues (overall direction drift, multi-step chain failures). They complement, not replace.

---

## Data Model

### PlanStatus

```python
class PlanStatus(str, Enum):
    PENDING = "pending"     # Pending execution
    ACTIVE = "active"       # In progress
    DONE = "done"           # Completed
    BLOCKED = "blocked"     # Blocked
    SKIPPED = "skipped"     # Skipped
```

### PlanStep

```python
@dataclass
class PlanStep:
    step_id: str                              # "1", "2.1"
    step_name: str = ""                       # Optional unique identifier (omitted in LLM generation, external tools can inject)
    step_type: str = ""                       # reason/act/decide/subtask
    description: str = ""                     # LLM-oriented descriptive task description
    inputs: list[str] = field(default_factory=list)   # ← input variables (node body declaration)
    outputs: list[str] = field(default_factory=list)  # → output variables (summary line declaration)
    detail: list[str] = field(default_factory=list)   # > node body expansion details
    result: str = ""                          # Actual completion status (filled after execution)
    status: PlanStatus = PlanStatus.PENDING
    expanded: bool | None = None              # Rendering control (transient, not serialized/parsed)
    done_count: int = 0                       # Completed iterations
    total_count: int | None = None            # Total iterations (None=non-loop)
    children: list[PlanStep] = field(default_factory=list)
```

### PlanSpec

```python
@dataclass
class PlanSpec:
    title: str = ""
    goal: str = ""
    goal_detail: list[str] = field(default_factory=list)  # > continuation (Goal additional explanation)
    constraints: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)

    @property
    def progress(self) -> dict[str, int]:
        """Returns {"total": N, "done": N, "active": N, "blocked": N, "pending": N, "skipped": N}"""

    @property
    def is_converged(self) -> bool:
        """Step status convergence: no PENDING or ACTIVE steps"""
```

`progress` recursively calculates status statistics for all steps (including nested children).

`is_converged` relaxes convergence conditions: BLOCKED steps are considered processed (re-plan attempted but unresolved), convergence achieved as long as no pending or active steps. Engine layer also needs to check output convergence—whether parent_step's necessary outputs have been produced.

---

## API

All functions located in `hop_engine.jit.plan_spec` module, exported from `hop_engine.jit` top level.

### parse_plan

```python
def parse_plan(text: str) -> PlanSpec
```

Parses PlanSpec compact format text into `PlanSpec` instance.

- Empty string returns empty `PlanSpec()`
- **Step ID encodes tree structure**: `2.1` automatically becomes child of `2` (doesn't depend on indentation or heading level)
- Status markers optional, defaults to `PENDING`
- `→ outputs` extracted from end of description to `outputs` field
- `> ← inputs` extracted from node body to `inputs` field (and removed from detail)
- `>` lines collected to `detail` field
- `|` separates result and Progress

### serialize_plan

```python
def serialize_plan(plan: PlanSpec, *, fold: bool = False) -> str
```

Serializes `PlanSpec` instance to compact format text.

- `fold=False` (default): Complete output, inverse operation of `parse_plan` (roundtrip fidelity)
- `fold=True`: Controls detail/children visibility based on `expanded` flags + status rules (for LLM context injection)

```python
plan == parse_plan(serialize_plan(plan))  # roundtrip (fold=False)
```

Serialization rules:
- `PENDING` status omits marker
- `→ outputs` appended after description, before `|`
- `← inputs` serialized as first node body line `> ← var1, var2`
- `detail` serialized as `> line` lines (after `← inputs`)
- Omit `result` when empty
- Omit Progress when `done_count == 0` and `total_count is None`
- Child steps indented 2 spaces/level (visual aid)
- Result ends with newline

`fold=True` folding rules:
- `expanded=False`: Summary line visible, detail + children all hidden
- `expanded=True`: detail + children all shown
- `expanded=None`: Follow status default rules (active/blocked expand detail, others collapse; children always shown)

### validate_plan

```python
def validate_plan(plan: PlanSpec) -> list[str]
```

6 checks, returns list of error/warning messages (empty list means passed):

| # | Check Item | Level | Example Message |
|---|------------|-------|-----------------|
| 1 | Steps non-empty | Error | `plan has no steps` |
| 2 | Step type valid | Error | `step 1 (foo): invalid type 'LLM'` |
| 3 | Step name globally unique (empty names skipped) | Error | `step 2 (bar): duplicate name, first seen at step 1` |
| 4 | Container constraints | Error | `step 1 (foo): type 'reason' cannot have children` |
| 5 | Goal non-empty | Error | `plan has no goal` |
| 6 | Structural integrity (subtask/decide should have children) | Warning | `warn: step 1 (foo): type 'subtask' has no children` |

Warnings prefixed with `warn:`, don't affect validity judgment. Name uniqueness, container constraints, and structural integrity all recursively check all nesting levels.

### expand_step / collapse_step

```python
def expand_step(plan: PlanSpec, step_id: str) -> str
def collapse_step(plan: PlanSpec, step_id: str) -> str
```

Explicitly control step's collapse/expand status, overriding default status rules. Returns empty string for success, non-empty for error message.

- `expand_step`: Sets `expanded=True`, forces showing detail + children
- `collapse_step`: Sets `expanded=False`, forces hiding detail + children

`expanded` is a transient flag, doesn't affect plan data, not involved in serialization/parsing. Only effective in `serialize_plan(fold=True)`.

EXPAND/COLLAPSE are **view operations** (for human users and tools), not triggered through LLM command protocol. LLM only uses structural commands (ADD/REVISE/REPLAN) during step reflection and end-of-round re-planning.

### replace_children

```python
def replace_children(plan: PlanSpec, step_id: str, new_children: list[PlanStep]) -> str
```

Replace specified container step's child step list. Used for subtree REPLAN phase 2: after engine generates new child steps, replace into target container.

- Target step must be `subtask` or `decide` type
- After replacement, target step status set to `ACTIVE`
- Uses list copy, no shared references

### Command Protocol (PLAN_CMD)

PlanSpec modification operations divided into **three layers** by responsibility, each with clear trigger and timing:

| Layer | Responsibility | Trigger | Operation |
|-------|----------------|---------|-----------|
| **Engine Layer** | Step status management | HOP engine automatic | DONE / BLOCKED / SKIP |
| **LLM Layer** | Plan structure revision | LLM during step reflection / end-of-round re-planning | ADD / REVISE / REPLAN |
| **View Layer** | Collapse/expand control | User or tool (`/showplan`) | EXPAND / COLLAPSE |

#### Engine Layer—Status Management (Automatic)

Engine automatically manages status transitions during step execution, LLM doesn't need to issue these commands:

```
PLAN_CMD: DONE <step_id> | <result summary>
  — After step execution succeeds, engine automatically marks as done

PLAN_CMD: BLOCKED <step_id> | <block reason>
  — When step execution fails or prerequisite dependencies not met, engine automatically marks as blocked

PLAN_CMD: SKIP <step_id> | <skip reason>
  — When step is skipped (e.g., branch condition not met), engine automatically marks as skipped
```

#### LLM Layer—Structure Revision (Step Reflection + End-of-round Re-planning)

Engine calls LLM to revise plan at two timings: **step reflection** (triggered immediately when `status != OK`) and **end-of-round re-planning** (triggered when round doesn't converge). Both phases inject current plan state + available command list into prompt, LLM revises plan structure through `PLAN_CMD:` line commands, engine executes deterministically. Commands identified by `PLAN_CMD:` prefix, one per line, engine ignores non-`PLAN_CMD:` lines (LLM reasoning text doesn't affect parsing).

```
PLAN_CMD: ADD 2.3 [reason] Verify cleaned data has no nulls and row count ≥ original 95%
> ← cleaned_data, raw_data
> Check null rate < 0.1%, row retention rate >= 95%
  — Insert new step at position 2.3, [type] specifies step type, followed by complete description.
    When task info exceeds single line, immediately follow with > continuation lines as node body (detail),
    providing constraints, input declarations, execution hints

PLAN_CMD: REVISE 3.1 [reason] Analyze feature correlation matrix, identify redundant features → feature_analysis
> ← feature_matrix
> Output redundant feature list and suggested removal reasons
  — Replace step's type, description, and node body (whole line replacement).
    Immediately follow with > continuation lines to replace target step's detail; without > continuation lines, preserve original detail

PLAN_CMD: REPLAN 4 | Model iteration strategy ineffective, need to re-decompose sub-steps
  — Clear all child steps of container step 4, engine will regenerate. Only for subtask/decide containers

PLAN_CMD: REPLAN ALL | Goal understanding deviation, need to re-plan from scratch
  — Discard entire plan, engine completely regenerates. Must write ALL, bare REPLAN will be ignored
```

**Safety Design**: Global REPLAN requires explicit `ALL` keyword to avoid accidental operations. Bare `REPLAN` (no step_id nor ALL) is silently skipped and logged as debug.

#### View Layer—Collapse/Expand (User/Tool)

EXPAND/COLLAPSE are **view operations**, called by users or tools (e.g., `/showplan`) via API, controlling detail/children visibility during rendering. Not triggered through LLM command protocol.

```python
expand_step(plan, "4")    # Expand step 4's node body and child steps
collapse_step(plan, "3")  # Collapse step 3, hide detail and children
```

See [Folding Rules](#folding-rules) and [expand_step / collapse_step](#expand_step--collapse_step) API.

### PlanCommand

```python
@dataclass
class PlanCommand:
    op: str              # DONE/BLOCKED/SKIP/ADD/REVISE/REPLAN/EXPAND/COLLAPSE
    step_id: str = ""    # Target step ID (can be "ALL" for REPLAN)
    step_type: str = ""  # Step type (for ADD/REVISE)
    description: str = ""  # Description (for ADD/REVISE)
    result: str = ""     # Result/reason (for DONE/BLOCKED/SKIP/REPLAN)
    detail: list[str] = field(default_factory=list)  # > continuation node body (for ADD/REVISE)
```

Parsed command data model. `op` is one of 8 valid operations, divided into three groups by responsibility:

| Group | Operations | Trigger | Use |
|-------|------------|---------|-----|
| Engine Layer | DONE / BLOCKED / SKIP | Engine automatic | Step status management |
| LLM Layer | ADD / REVISE / REPLAN | LLM step reflection / end-of-round re-planning | Plan structure revision |
| View Layer | EXPAND / COLLAPSE | User/tool | Collapse/expand control |

### parse_plan_commands

```python
def parse_plan_commands(text: str) -> list[PlanCommand]
```

Extracts `PLAN_CMD:` prefixed line commands from LLM output text, ignores other text (LLM reasoning content).

- Only recognizes lines starting with `PLAN_CMD:`
- Invalid operation verbs silently skipped
- `ALL` keyword in `REPLAN ALL` case-insensitive

### apply_command / apply_commands

```python
def apply_command(plan: PlanSpec, cmd: PlanCommand) -> str
def apply_commands(plan: PlanSpec, commands: list[PlanCommand]) -> list[str]
```

Deterministically executes single or batch commands. Modifies `plan` instance in place.

- Return value: empty string/empty list for success, non-empty for error message
- Global `REPLAN` (no step_id or step_id="ALL") not executed here—returns empty string, coordinated by engine layer for regeneration
- Subtree `REPLAN <step_id>`: Clears target container's children, resets status to PENDING

### plan_to_steps

```python
def plan_to_steps(plan: PlanSpec) -> list[StepInfo]
```

Converts PlanSpec to HopSpec's `StepInfo` list for HopSpec interoperability.

**Conversion Rules**:

| PlanStep type | → StepInfo type | Conversion Logic |
|---------------|-----------------|------------------|
| `reason` | `LLM` | `task=description`, `verifier=""` |
| `act` | `code` | `description=description` |
| `decide` | `branch` | `condition=description`, children recursively |
| `subtask` | `subtask` | `expand_mode="static"`, children recursively |

**Data flow transfer**: `inputs` and `outputs` directly passed to StepInfo corresponding fields.

Unnamed steps auto-generate `step_name`: `step_1`, `step_2_1`, etc. (`.` in step_id replaced with `_`).

Automatically appends `flow:exit` (`EXIT_OK`) at end if last step is not `flow` type.

### steps_to_plan

```python
def steps_to_plan(
    steps: list[StepInfo],
    title: str = "",
    goal: str = "",
    constraints: list[str] | None = None,
) -> PlanSpec
```

Converts HopSpec's `StepInfo` list to PlanSpec, generating HopSpec's simplified planning view.

**Conversion Rules**:

| StepInfo type | → PlanStep type | Conversion Logic |
|---------------|-----------------|------------------|
| `LLM` | `reason` | `description=task` (verification strategy is implementation detail, not distinguished) |
| `code` | `act` | `description=description` |
| `call` | `act` | `description=task` |
| `branch` | `decide` | `description=condition` |
| `loop` | `subtask` | `description` contains traversal/condition info |
| `subtask` | `subtask` | `description=description` |
| `flow` | **Skip** | Flow control is structural, not planning content |

**Data flow preserved**: `inputs` and `outputs` from StepInfo directly passed to PlanStep.

---

## Loop Handling Strategy

PlanSpec has no `loop` type. Loop scenarios handled in two ways:

### Option A: Expand to Concrete Sub-steps (Preferred)

Expand loop into `subtask` + concrete children, each sub-step independently tracks status:

```
1. [subtask] Process each item in batch → results
  1.1. [x] [act] Process item A → item_a
  1.2. [x] [act] Process item B → item_b
  1.3. [act] Process item C → item_c
```

Suitable for scenarios with known iteration counts, each iteration has different semantics.

### Option B: Iteration Counting

When iteration count unknown or sub-steps homogeneous, use `done_count` / `total_count` to track progress:

```
1. [subtask] Process each item in batch → results | Progress: 3/5
```

- `done_count`: Completed iterations
- `total_count`: Total iterations (`None` means unknown)
- Serialized as `| Progress: N/M` (known total_count) or `| Progress: N` (unknown)

---

## Relationship with HopSpec

### Bidirectional Conversion

```
PlanSpec ──plan_to_steps()──→ StepInfo[] (HopSpec)
PlanSpec ←──steps_to_plan()── StepInfo[] (HopSpec)
```

Conversion loses information:
- **Plan → Hop**: Loses status, result, progress, detail (HopSpec doesn't track execution status)
- **Hop → Plan**: Loses return_format, verifier details, call_target, flow steps (PlanSpec doesn't care about implementation details)

Bidirectional conversion preserves **core structure** (step hierarchy, type mapping, inputs/outputs).

### Progressive Solidification Path

```
PlanSpec (complete planning)
    ↓ plan_to_steps() + manual attribute supplementation
HopSpec (executable specification)
    ↓ /spec2code
Hop.py (executable code)
```

Reverse direction for observation:

```
Hop.py / HopSpec
    ↓ steps_to_plan()
PlanSpec (progress view)
    ↓ /showplan
Terminal visualization
```

---

## Complete Example

```
# Plan: Auto Insurance Claim Rate Prediction
Goal: Build claim prediction model through XGBoost + LLM iterative optimization based on synthetic insurance data
Constraints:
- Synthetic data built-in generation, no external file dependency
- polars for DataFrame processing, XGBoost for binary classification
- Maximum 5 iterations, target Gini ≥ 0.40
## Steps
1. [x] [act] Generate 10K synthetic policy data with 5% missing values and outlier noise → synthetic_data | Generation complete
  > Fields: policy_no, vehicle_age, driver_age, vehicle_value, annual_mileage,
  >   region(5 categories), vehicle_type(3 categories), driver_gender, years_licensed,
  >   previous_claims, premium, claim_flag, claim_amount
  > claim_flag positive rate ~15%, claim_amount follows log-normal
2. [>] [reason] Analyze data distribution and quality issues, provide cleaning strategy and feature engineering suggestions → data_profile, clean_suggestions, feature_suggestions
  > ← synthetic_data
  > Output data_profile includes: missing rates per column, distribution types, outlier proportions
  > clean_suggestions as action list, feature_suggestions as transform list
3. [subtask] Clean raw data based on LLM profile → cleaned_data
  3.1. [reason] Determine specific cleaning rules (missing imputation strategy, outlier truncation thresholds, type corrections) → cleaning_plan
    > ← data_profile, clean_suggestions
  3.2. [act] Execute cleaning plan on synthetic_data, verify row count and null rate → cleaned_data
4. [subtask] Construct prediction features based on cleaned data → feature_matrix
  4.1. [reason] Propose feature transformation scheme (interaction terms, binning, encoding) → feature_plan
    > ← cleaned_data, feature_suggestions
  4.2. [act] Construct feature matrix per scheme, output polars DataFrame → feature_matrix
5. [subtask] Iteratively train XGBoost until Gini ≥ 0.40 or 5 rounds completed → cv_metrics, feature_importance
  5.1. [x] [act] Train XGBoost binary classifier, 5-fold stratified cross-validation → cv_metrics | Gini=0.38, AUC=0.69
  5.2. [x] [act] Calculate Gini coefficient, AUC, A/E ratio, extract feature importance ranking → gini, auc, ae_ratio, feature_importance
  5.3. [>] [reason] Diagnose model weaknesses from CV metrics and feature importance, suggest parameter and feature adjustment scheme → diagnosis, param_adjustments
    > ← cv_metrics, feature_importance
    > Analysis: overfitting (train/val gap), feature redundancy, class imbalance
    > Suggestions: learning_rate/max_depth/reg_lambda adjustments + feature add/remove
    > Output adjustments[], each with param, current, suggested, reason
  5.4. [decide] Check if Gini reaches target threshold
    5.4.1. [act] Gini ≥ target → exit iteration to report
    5.4.2. [act] Not reach the target threshold → apply parameter adjustment scheme, continue next iteration
6. [act] Generate actuarial analysis report covering model performance, feature insights, and business recommendations → report
  > ← cv_metrics, feature_importance, data_profile, cleaning_plan, feature_plan
  > Report structure: executive_summary + model_performance + feature_analysis
  >   + iteration_history + recommendations
  > Markdown format, with tables and key metrics highlighted
7. [act] Assemble final output and exit → final_output
```

Corresponding progress:

```
total: 14, done: 2, active: 2, blocked: 0, pending: 10, skipped: 0
```

---

## Validation Rules Quick Reference

| # | Rule | Level | Violation Example |
|---|------|-------|-------------------|
| 1 | At least one step | Error | `steps: []` |
| 2 | Type must be reason/act/decide/subtask | Error | `step_type: "LLM"` |
| 3 | step_name globally unique (including nested, empty names skipped) | Error | Two named steps both called `analyze` |
| 4 | Only subtask/decide can have children | Error | `reason` with children |
| 5 | Goal non-empty | Error | `goal: ""` |
| 6 | subtask/decide should have children | Warning | childless `subtask` (`warn:` prefix) |

---

## Command Line Tools

### Storage Convention

PlanSpec files stored under project root `planspec/` directory (.gitignore protected, pure local workspace). Each plan one `.md` file, filename in snake_case (e.g., `implement_auth.md`). Completed plans can be archived to `planspec/archive/`.

`Tasks/<name>/plan.md` used for Task-level plans (bound to Task lifecycle), not managed by `planspec/`. Both coexist without conflict.

### /planspec

```
/planspec <description>          # Create new plan (confirm first, then generate)
/planspec <name>                 # Continue/view existing plan
```

When creating, writes to `planspec/<name>.md`. When viewing, loads from `planspec/` matching filename.

### /listplan

```
/listplan                        # List all plans in planspec/ directory overview
```

Scans `planspec/*.md`, parses each file's title, goal, progress, outputs compact list.

### /archiveplan

```
/archiveplan <name>              # Archive completed plan
```

Moves `planspec/<name>.md` to `planspec/archive/<name>.md`.

### /showplan

```
/showplan <name_or_path>
```

Displays PlanSpec in terminal as cascading tree structure, reusing `/showspec` visualization style. Search path priority: `planspec/<name>.md` → `Tasks/<name>/plan.md` → load directly as file path.

Type badge mapping:

| step_type | badge |
|-----------|-------|
| reason | `[REASON]` |
| act | `[ACT]` |
| decide | `[DECIDE]` |
| subtask | `[SUBTASK]` |

**Folding Rules**: Renders node bodies folded by status (see "Folding Rules" section). `→ outputs` always shown in summary line.

Output example:

```
═══ PlanSpec: Auto Insurance Claim Rate Prediction ═══

Goal: Build claim prediction model through XGBoost + LLM iterative optimization based on synthetic insurance data

Constraints:
  - Synthetic data built-in generation
  - polars + XGBoost

Progress: 2/14 (14%)

1  [x]  [ACT]      Generate 10K synthetic policy data → synthetic_data | Generation complete
2  [>]  [REASON]   Analyze data distribution and quality issues → data_profile, clean_suggestions, feature_suggestions
                   > ← synthetic_data
                   > Output data_profile includes: missing rates per column, distribution types, outlier proportions
3  [ ]  [SUBTASK]  Clean raw data based on LLM profile → cleaned_data
├─ 3.1  [ ]  [REASON]   Determine specific cleaning rules → cleaning_plan
└─ 3.2  [ ]  [ACT]      Execute cleaning plan on synthetic_data → cleaned_data
...

───
Steps: 14 | reason: 4 | act: 6 | decide: 1 | subtask: 3
Progress: 2/14 (14%)
```
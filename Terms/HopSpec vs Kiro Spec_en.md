# HopSpec vs Kiro Spec: Two Design Paths for Spec-Driven Development

## Introduction

[Kiro](https://kiro.dev/) is an AI IDE launched by Amazon, whose core feature is **Spec-Driven Development** - using structured requirements/design/tasks files to replace traditional chat-driven development. HopSpec is the task specification format of the HOP framework, using a structured tree composed of 7 atomic step types to describe LLM reasoning processes, driving code generation and bidirectional synchronization.

Both oppose "chatting with AI to write code" and advocate using structured specifications to improve AI programming quality. But fundamentally, they answer different questions:

- **Kiro Spec**: How does AI understand my requirements and correctly write code?
- **HopSpec**: How can we ensure each step of LLM reasoning is trustworthy and reliable?

This article systematically compares the design differences and complementary relationships between the two Specs.

---

## 1. Positioning Differences

### 1.1 Kiro Spec: AI Automation for Software Requirements Management

Kiro's starting point is traditional software engineering's SDLC (Software Development Life Cycle). It observes that the core bottleneck of AI programming assistants is not code generation capability, but **ambiguity in requirement understanding** - developers describe requirements in chat, AI guesses and writes, resulting in deviations from expectations.

Kiro's solution is to establish structured requirement contracts before AI writes code:

```
User idea → requirements.md → design.md → tasks.md → code
```

Each stage has clear format constraints (EARS notation, architecture diagrams, checkbox task lists), AI's output at each stage is reviewable documentation rather than direct code.

### 1.2 HopSpec: Execution Specification for LLM Reasoning Processes

HopSpec's starting point is not the software development process, but **LLM hallucination problems**. In professional scenarios like finance and healthcare, LLM reasoning outputs must achieve 99%+ reliability. Prompt engineering alone cannot guarantee this - we need program-level verification loops for each LLM reasoning node.

HopSpec's solution is to use structured program skeletons to constrain LLM reasoning processes:

```
Task description → HopSpec.md (7 atomic steps + verification strategies) → Hop.py (async coroutines) → execution + step-by-step verification
```

The Spec describes not only "what to do" but also "how to verify if LLM is correct".

---

## 2. File Structure Comparison

### 2.1 Kiro: Three-file Separation + Steering Context

```
.kiro/
├── specs/
│   └── <feature>/
│       ├── requirements.md    # User stories + EARS acceptance criteria
│       ├── design.md          # Architecture design + error handling + test strategy
│       └── tasks.md           # Flat checkbox task list
├── steering/
│   ├── structure.md           # Code architecture analysis
│   ├── tech.md                # Tech stack and patterns
│   └── product.md             # Business context
```

The three spec files correspond to three stages (requirements→design→tasks), with clear separation of concerns. Steering documents are automatically generated code base understanding by Kiro, serving as AI background context.

### 2.2 HopSpec: Single File Six Sections + Metadata Contract

```
Tasks/<TaskName>/Hoplet/
├── HopSpec.md         # Single file: task overview + input definitions + hard constraints + execution flow + output format + examples
├── metainfo.md        # Metadata contract (input/output schema, run mode, test metrics)
├── SKILL.md           # AgentSkills.io interoperability description
└── Hop.py             # Executable code generated from HopSpec
```

HopSpec aggregates all information in one Markdown file. It focuses not on "who does what" but on "how LLM reasons at which node and how to verify". `metainfo.md` plays a similar contract role to Kiro's `requirements.md`, but focuses more on data schema than user stories.

---

## 3. Requirement Description Methods

### 3.1 Kiro: User Stories + EARS Acceptance Criteria

Kiro uses traditional software engineering user story format, with acceptance criteria using EARS (Easy Approach to Requirements Syntax) notation:

```markdown
### Requirement 1: Product Search
**User Story:** As a shopper, I want to search for products by name,
so that I can quickly find items I'm looking for.

**Acceptance Criteria:**
- WHEN user enters a search term THE SYSTEM SHALL return matching products
- GIVEN no matching products WHEN search completes THEN display "No results found"
- WHEN search results exceed 20 items THE SYSTEM SHALL paginate results
```

EARS's WHEN/THEN structure is oriented toward **user-observable behavior** - describing system external behavior without involving internal implementation.

### 3.2 HopSpec: Domain Constraints + Data Contracts

HopSpec doesn't use user stories, but directly declares domain constraints and data boundaries:

```markdown
## Input Definitions
- `context_window`: context/reference documents
- `model_output`: reasoning or answers generated by large model

## Hard Constraints
- Even for recognized facts, if not mentioned in context_window, must be marked as external knowledge leakage
- Any steps that cannot be strictly derived from premises must be marked as derivation incoherence

## Output Format
{"reliability_score": int, "hallucination_detected": bool, "errors": [...]}
```

HopSpec's constraints are oriented toward **LLM reasoning behavior** - constraining not system external behavior, but rules that LLM must follow during reasoning. These constraints are injected into LLM prompts as hard boundaries.

### 3.3 Essential Differences

| Dimension | Kiro EARS | HopSpec Constraints |
|-----------|-----------|---------------------|
| Constraint Object | System behavior (user perspective) | LLM reasoning (operator perspective) |
| Verification Timing | After the fact (testing) | Runtime (verification loop) |
| Expression Granularity | Feature level ("search returns results") | Reasoning level ("facts not appearing in context must be marked") |
| Consumers | AI programming assistant + human reviewers | HOP engine + LLM prompt |

---

## 4. Execution Flow Expression

This is the most fundamental difference between the two.

### 4.1 Kiro tasks.md: Flat Checklist

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

tasks.md is a **Work Breakdown Structure** (WBS). Each entry is a development task, AI executes them one by one, checking off when complete. Task dependencies are implicit in order, with no explicit control flow.

### 4.2 HopSpec Execution Flow: Structured Step Tree

```markdown
#### Step1: extract_atomic_facts
- Type: LLM
- Task: Break down model output into independent atomic fact statements
- Output Format: {"claims": List[str]}
- Verification: None

#### Step2: check_grounding (loop)
- Type: loop
- Iterate Collection: atomic_claims
- Output: grounding_errors

  #### Step2.1: judge_claim_source
  - Type: LLM
  - Task: Determine the source type of this atomic statement
  - Output Format: {"verdict": str, "evidence": str}

#### Step3: check_logic
- Type: LLM
- Task: Analyze derivation relationships between reasoning steps

#### Step4: handle_inconsistency (branch)
- Type: branch
- Condition: is_consistent == False

  #### Step4.1: list_conflicts
  - Type: LLM
  - Task: List internal conflicts in reasoning

#### Step5: merge_errors
- Type: code
- Logic: Merge all error collections
```

HopSpec execution flow is a **control flow tree**. 7 atomic step types (LLM / call / loop / branch / code / flow / subtask) correspond to basic program constructs - sequence, loop, branch, subroutine calls. The tree structure directly maps to Python indentation blocks, prohibiting any form of jumps (goto).

### 4.3 Core Differences

| Dimension | Kiro tasks.md | HopSpec Execution Flow |
|-----------|---------------|------------------------|
| **Structure** | Flat list (no nesting) | Structured tree (loop/branch nesting at any depth) |
| **Step Types** | No type distinction | 7 atomic types, each with fixed attribute set |
| **Control Flow** | Implicit sequence | Explicit: for-each / while / if / exit / continue / break |
| **Variable Tracking** | None (depends on natural language description) | Explicit: each step declares input/output variables, data flow can be statically audited |
| **Verification Declaration** | None | Each LLM step can declare verification strategy |
| **Code Mapping** | AI free inference | Deterministic mapping (LLM→hop_get, loop→for, branch→if) |
| **Theoretical Foundation** | Work Breakdown Structure (WBS) | Structured Program Theorem (Bohm-Jacopini) |

**Analogy**: Kiro tasks.md is like a **task list** for a construction crew ("pour foundation on day 1, build walls on day 2"), HopSpec is like **architectural blueprints** ("here's the load-bearing wall, there's the pipe routing, what's the strength standard for each rebar").

---

## 5. Verification and Reliability Assurance

### 5.1 Kiro: Post-hoc Testing

Kiro includes test strategies in `design.md`, but verification occurs after code generation:

```
AI generates code → run tests → discover issues → modify Spec → regenerate
```

Kiro's Spec is AI's "context reference" - AI reads Spec to understand requirements, but Spec itself doesn't participate in runtime verification. Code quality depends on AI's code generation capability and test coverage.

### 5.2 HopSpec: Runtime Step-by-step Verification

HopSpec's verification is **declared in Spec and executed at runtime**:

```markdown
#### Step3: check_logic
- Type: LLM
- Task: Analyze derivation relationships between reasoning steps
- Verification: reverse verification
```

This line `Verification: reverse verification` means:

1. Execute LLM (run_llm) to generate reasoning results
2. Format verifier detects serialization residue (pure local, zero LLM overhead)
3. Independent verification LLM (verify_llm) reverse-verifies result correctness
4. Verification failure → inject feedback → auto-retry (up to hop_retry times)
5. LLM self-reports confidence (OK / LACK_OF_INFO / UNCERTAIN), low confidence triggers feedback loop

```
LLM generates result → format_verifier → semantic verification → failure → inject feedback → retry
                                           → success → continue to next step
```

Verification is not "post-hoc testing" but **built-in quality gates for each LLM reasoning node**.

### 5.3 Comparison

| Dimension | Kiro | HopSpec |
|-----------|------|---------|
| Verification Timing | After code generation (test phase) | At each LLM call (runtime) |
| Verification Object | Whether generated code meets acceptance criteria | Whether each LLM step output is correct |
| Verification Method | Unit tests / integration tests | Reverse verification / positive cross-verification / tool verification / format verification |
| Failure Handling | Modify Spec and regenerate | Auto-retry + feedback injection |
| Confidence Mechanism | None | OK / LACK_OF_INFO / UNCERTAIN three-level self-report |
| Hallucination Defense | Depends on test coverage | Structured output + serialization residue detection + semantic verification |

---

## 6. Code Generation and Bidirectional Synchronization

### 6.1 Kiro: Task-driven Free Generation

Kiro's code generation is a **AI free inference** process. AI reads checkbox descriptions in tasks.md, combines with steering documents (code architecture, tech stack) to generate implementation code. There's no structured mapping between generated code and Spec - Spec is "guidance", not "blueprint".

Iteration method: modify requirements.md → click "Refine" → Kiro automatically updates design.md and tasks.md → re-execute tasks. This is **unidirectional refinement** - information flow from Spec to code is one-way.

### 6.2 HopSpec: Deterministic Mapping + Bidirectional Synchronization

Each step type in HopSpec has precise code pattern mapping:

| Spec Step Type | Python Code |
|----------------|-------------|
| `LLM` (extract/analyze semantics) | `await s.hop_get(task=..., return_format=...)` |
| `LLM` (judge/verify semantics) | `await s.hop_judge(task=...)` |
| `call` (tool call) | `await s.hop_tool_use(task=..., tool_domain=...)` |
| `loop` (iteration) | `for item in collection:` |
| `branch` (condition) | `if condition:` |
| `code` (pure computation) | Python assignment/computation |
| `flow: exit` | `session.hop_exit(...); return` |

Step's `step_name` serves as anchor comments in code: `# StepN: step_name -- type -- task`. This enables **bidirectional synchronization** between Spec and Code:

```
HopSpec.md ──/specsync──→ Hop.py     # Spec changes incrementally sync to Code
HopSpec.md ←──/code2spec── Hop.py     # Code changes reverse sync to Spec
HopSpec.md ←─/specdiff──→ Hop.py     # Compare differences (read-only)
```

Bidirectional synchronization means developers can either modify Spec first then sync code, or modify code during debugging then write back to Spec. `/verifyspec` also provides 6 automatic audits (structural integrity, data flow tracking, verification strategy review, etc.), discovering issues at the Spec level.

---

## 7. Execution Modes

| Dimension | Kiro | HopSpec |
|-----------|------|---------|
| AOT/JIT | Only AOT (predefined task list) | AOT + JIT dual modes |
| Subtasks | None | subtask 3 expansion types: static / dynamic / think (historical alias `seq_think` maintains compatibility) |
| Run Modes | Single (development execution) | Interactive / batch dual modes |
| Progressive Solidification | None | think success path → dynamic solidification → static predefined |

HopSpec's JIT mode allows runtime dynamic determination of next steps - LLM selects step type and parameters based on current state. think's six-stage structured thinking (decompose→plan→execute+monitor→reflect→revise→synthesize) provides an execution framework for exploratory tasks, with successful paths gradually solidifying into deterministic processes.

This progressive solidification (JIT → AOT) embodies HOP's "more certain and reliable with use" philosophy at the Spec level. Kiro has no similar mechanism.

---

## 8. Theoretical Foundations

### 8.1 Kiro: Software Engineering Best Practices

Kiro's design is rooted in traditional software engineering methodologies:

- **User Stories** from agile development
- **EARS notation** (Easy Approach to Requirements Syntax) from requirements engineering
- **Architecture documents** from SAD (Software Architecture Document) tradition
- **Task decomposition** from WBS (Work Breakdown Structure)

Kiro uses AI to automate these proven engineering practices, letting AI programming assistants work under structured requirement constraints rather than free play.

### 8.2 HopSpec: Structured Program Theorem

HopSpec's design is rooted in computer science fundamentals:

- **Bohm-Jacopini theorem**: Any computable function can be expressed with sequence, loop, and branch structures, without goto
- **7 atomic steps** = sequential execution + loop (iteration) + branch (condition) + flow (control transfer) + LLM/call/code (atomic operations) + subtask (subroutine)
- **No jumps**: Consistent with Python block structure, control flow is completely determined by hierarchical nesting + sequential execution

This means HopSpec's expressiveness is equivalent to Python - any Python program's control flow can be expressed in HopSpec, and vice versa. This is not coincidental but by design: HopSpec is the Markdown representation of Python control flow.

In contrast, Kiro's tasks.md is merely an ordered list, lacking control flow expression capability. Concepts like loops, conditions, subroutine calls cannot be expressed in tasks.md - they are deferred to the code generation phase for AI free inference.

---

## 9. Complementary Relationship

Kiro Spec and HopSpec solve **different level** problems:

```
Kiro layer: requirement understanding → architecture design → task decomposition
                                    ↓
HopSpec layer:               LLM reasoning process → verification strategy → executable code
```

An entry in Kiro tasks.md could perfectly be:

```markdown
- [ ] 5. Implement hallucination detection using HOP framework
    - Create HopSpec for 3-stage verification (grounding + logic + consistency)
    - Generate Hop.py with /spec2code
    - Run batch tests with /batchhoptest
    - _Requirements: 3.1, 3.2, 3.3_
```

Kiro manages "how AI understands requirements in the development process", HopSpec manages "how to ensure reliable LLM reasoning at runtime". The former is development phase quality control, the latter is runtime quality control.

### Summary

| Dimension | Kiro Spec | HopSpec |
|-----------|-----------|---------|
| **One sentence** | Use structured requirements to replace AI chat | Use structured program skeletons to constrain LLM reasoning |
| **Essence** | Requirements management framework | Execution specification |
| **Granularity** | Feature level ("create search API") | Reasoning level ("extract atomic facts → verify each → score") |
| **Control Flow** | None (flat checklist) | Structured tree (7 atomic step types) |
| **Verification** | Post-hoc testing | Runtime step-by-step verification |
| **Trust Model** | Trust AI generated code | Don't trust LLM output |
| **Code Mapping** | AI free inference | Deterministic mapping + bidirectional sync |
| **Iteration** | Unidirectional refinement (Spec → Code) | Bidirectional sync (Spec ↔ Code) |
| **Theoretical Foundation** | Software engineering best practices | Structured program theorem |
| **Applicable Layer** | Full software development lifecycle | LLM reasoning process orchestration |

---

## References

- [Kiro Specs Documentation](https://kiro.dev/docs/specs/)
- [Kiro Best Practices](https://kiro.dev/docs/specs/best-practices/)
- [From Chat to Specs: A Deep Dive — Kiro Blog](https://kiro.dev/blog/from-chat-to-specs-deep-dive/)
- [Understanding Spec-Driven Development — Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [HopSpec Format Specification](HopSpec格式规范.md)
- [HOP High-order Program](HOP高阶程序.md)
- [HOP vs Burr](HOP%20vs%20Burr.md)
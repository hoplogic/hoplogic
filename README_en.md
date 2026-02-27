# HOP 2.0 Studio

**HOP (High-Order Program)** is a trustworthy agent programming paradigm for large language models - **controllable, reliable, and continuously evolving**.

By constraining LLM intelligence through structured program skeletons, eliminating hallucinations through operator-level verification loops, and achieving continuous evolution through progressive solidification, LLMs can achieve 99%+ reliability in professional scenarios like finance and healthcare.

HOP 2.0 Studio is the specification and engine development environment for HOP, providing a complete toolchain from natural language task descriptions to executable agents.

> **Technical Positioning**: Human-defined intent constraints, AI trustworthy implementation, code-intelligence dual-state fusion, continuous intellectual asset accumulation.

---

## Core Philosophy

| Principle | Description |
|-----------|-------------|
| **Controllable** | HopSpec inherits structured programming paradigms (Bohm-Jacopini / Dijkstra), with 7 atomic step types covering sequence, selection, loop + LLM reasoning + external calls + task decomposition + flow control, execution paths are predictable and auditable |
| **Reliable** | Deterministic skeleton isolates LLM non-determinism (hallucinations don't spread), three built-in operators have multi-layer verification (reverse/forward cross/tool/format), automatic retry with feedback on verification failure |
| **Continuously Evolving** | subtasks evolve from exploration (think ordered thinking) to progressive solidification into deterministic processes, Spec-Code bidirectional synchronization stays connected, Bad Cases transform into knowledge or skill improvements through residual analysis |

### Code-Intelligence Dual-State Fusion

```
               loop (deterministic: iterate collection)
              /    \
         LLM         branch (deterministic: Python expression evaluation)
       (non-deterministic)      /      \
                    LLM       flow:continue
                 (non-deterministic)    (deterministic)
```

**Control flow is completely deterministic, non-determinism is strictly isolated to leaf nodes.** Hallucinations in individual nodes won't cause disorder propagation at the control flow level.

---

## Architecture

### Three-Layer Execution Architecture

```
User code (Hop.py / examples)
    |
HopSession  -- execution boundary: conversation history, HopState, ExecutionStats, persistence(StateStore)
    |
HopProc     -- operator abstraction: hop_get / hop_judge / hop_tool_use (stateless, shareable)
    |
LLM         -- transport layer: connection reuse, multi-engine adaptation, structured output
```

### Three Core Operators (all async)

| Operator | Purpose | Default Verification |
|----------|---------|---------------------|
| `hop_get()` | Information retrieval / knowledge extraction | Reverse verification |
| `hop_judge()` | Truth judgment / condition evaluation | Reverse verification |
| `hop_tool_use()` | Tool selection and invocation | Tool verification |

### Verification System

| Verifier | Method | Cost |
|----------|--------|------|
| `format_verifier` | Serialization residue detection (pure local) | Zero LLM overhead |
| `reverse_verify` | Independent LLM reverse verification | 1 LLM call |
| `forward_cross_verify` | 3-way concurrent majority voting | 3 LLM calls |
| `tool_use_verifier` | Legality + parameters + cross verification | Depends on tool |

### AOT / JIT Dual Mode

- **AOT (Ahead-of-Time)**: Human writes SOP -> HopSpec -> code generation -> execution. Suitable for solidified, repeatedly executed tasks.
- **JIT (Just-in-Time)**: User task description -> LLM dynamically generates HopSpec -> deterministic verification -> engine interpretation execution. Suitable for immediate, exploratory tasks.
- **Progressive Solidification**: think (ordered thinking) -> dynamic (load solidified path) -> static (predefined steps). More deterministic and reliable with use.

---

## Project Structure

```
.
├── Tasks/                          # HOP task directory (5 tasks)
│   └── <TaskName>/
│       ├── Task.md                 # Echo-written task description (read-only)
│       ├── Hoplet/                 # Executable agent unit
│       │   ├── metainfo.md         # Metadata contract (input/output/run mode/test metrics)
│       │   ├── SKILL.md            # AgentSkills.io interoperability description
│       │   ├── HopSpec.md          # Standardized task specification document
│       │   └── Hop.py              # Executable code
│       ├── TestCases/              # Test cases and results
│       └── View/                   # Observation UI (SSR architecture, desktop + web dual mode)
│           ├── ViewSpec/           # UI specification (Zone-per-file structure)
│           ├── config.py           # ViewConfig declaration
│           ├── app.py / web.py     # Transport thin launcher
│           ├── index.html          # Frontend (SSR rendering)
│           └── test/               # Integration tests
├── HopLib/                         # Reusable skill library (4 skills)
│   ├── ConfigManager/              # Configuration management tool (uv run hop config)
│   ├── Chart/                      # Chart generation
│   ├── OCR/                        # Text recognition
│   └── WebSearch/                  # Web search
├── Terms/                          # Terminology definitions and specification documents (16 docs)
├── hoplogic/                       # HOP Engine core code
│   ├── hop_engine/                 # Engine package (8 components)
│   │   ├── config/                 #   Configuration and constants (HopStatus, ModelConfig)
│   │   ├── utils/                  #   Shared utilities (JSON parsing, format fixing)
│   │   ├── llm/                    #   LLM transport layer (multi-engine adaptation)
│   │   ├── prompts/                #   Prompt templates and strategies
│   │   ├── tools/                  #   Tool registration
│   │   ├── validators/             #   Verifiers
│   │   ├── core/                   #   Core engine (HopProc, HopSession, StateStore)
│   │   └── jit/                    #   JIT engine (Spec parsing/validation/execution/subtask)
│   ├── hop_view/                   # View shared library (SSR rendering, config-driven)
│   ├── hop_rag/                    # RAG component (DuckDB VSS, knowledge base retrieval enhancement)
│   ├── hop_mcp/                    # MCP Client (tool connection and invocation)
│   ├── hop_mcp_server/             # MCP Server (HOP skills exposed as MCP services)
│   ├── hop_skill/                  # Skill component (skill discovery, registration, adaptation)
│   ├── code_template/              # Hop.py code templates
│   ├── examples/                   # Example applications (5 examples)
│   ├── docs/                       # API documentation (35 docs)
│   └── test/                       # Unit test suite
├── .claude/commands/               # Claude Code slash commands (16 commands)
├── .roo/commands/                  # Roo Code commands (sync)
├── pyproject.toml                  # Project metadata (Python >= 3.14)
└── uv.lock                         # Dependency lock file
```

---

## Installation

**Environment Requirements**: Python >= 3.14, package management using [uv](https://docs.astral.sh/uv/).

```bash
# Clone repository
git clone <repo-url> && cd hop_spec_ide

# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev
```

---

## Quick Start

### Running Hoplet

```bash
# Recommended: execute via uv run task command (no cd needed)
uv run task <TaskName>

# Launch observation UI (desktop mode)
uv run view <TaskName>

# Launch observation UI (web mode)
uv run view <TaskName> --web
```

### Configuration Management

```bash
# Graphical configuration editor (desktop mode)
uv run hop config

# Web mode
uv run hop config --web

# List all skills
uv run hop list

# Execute skill by name
uv run hop run <skill_name> '<json_input>'
```

### Running Examples

```bash
# Configure LLM API (edit hoplogic/settings.yaml and .env)
cd hoplogic

# Phishing email detection
uv run python -m examples.phishing.phishing

# Integration tests (requires LLM API)
uv run python test.py
```

### Running Unit Tests

```bash
# All tests (~1500+ tests, pure mock, no LLM API needed)
cd hoplogic && uv run pytest test/ -v

# Component tests
cd hoplogic && uv run pytest hop_view/test/ -v
cd hoplogic && uv run pytest hop_skill/test/ -v
cd hoplogic && uv run pytest hop_rag/test/ -v
cd hoplogic && uv run pytest hop_mcp/test/ -v
```

---

## Bidirectional Iteration Pipeline

```
Task.md ──→ HopSpec.md ⇄ Hop.py + metainfo.md ──→ Execution/Testing
 Echo writes   /task2spec  │    ↑                    /hoprun
                         │    │
           /specsync ────┘    └──── /code2spec
           (Spec→Code incremental)         (Code→Spec reverse)

                 /specdiff (compare differences, no file modification)

 metainfo.md + HopSpec.md ──→ ViewSpec/ ⇄ View/
   (data contract)   (execution logic)       │           ↑
                   │             │           │
         /code2viewspec    /code2view ──┘    └── /view2spec
```

### Typical Workflow

```bash
# Complete pipeline (using VerifyFast task as example)
/task2spec VerifyFast       # Task.md -> HopSpec.md
/verifyspec VerifyFast      # Audit HopSpec (optional)
/spec2code VerifyFast       # HopSpec -> Hop.py (full generation)
/hoprun VerifyFast          # Execute and debug

# Batch testing (automatically includes result analysis)
/batchhoptest VerifyFast test_data.jsonl --workers 10

# Iteration A: Write back to Spec after debugging
/hoprun VerifyFast          # Run, AI fixes code
/specdiff VerifyFast        # See what Code changed
/code2spec VerifyFast       # Write changes back to Spec

# Iteration B: Incrementally sync Code after modifying Spec
/specsync VerifyFast        # Incrementally update Code
/hoprun VerifyFast          # Verify execution

# Generate observation UI
/code2viewspec VerifyFast   # Initial ViewSpec generation
/code2view VerifyFast       # ViewSpec -> View code
```

---

## Slash Commands Overview

| Command | Purpose | Direction |
|---------|---------|-----------|
| `/task2spec <task>` | Task.md -> HopSpec | Task.md -> HopSpec.md |
| `/verifyspec <task>` | Audit and modify HopSpec | HopSpec.md -> HopSpec.md |
| `/showspec <task>` | CLI visualization of HopSpec tree structure | HopSpec.md (read-only) |
| `/spec2code <task>` | HopSpec -> code (full generation) | HopSpec.md -> Hop.py + metainfo.md + SKILL.md |
| `/specsync <task>` | Spec -> Code incremental sync | HopSpec.md -> Hop.py |
| `/code2spec <task>` | Code -> Spec reverse sync | Hop.py -> HopSpec.md |
| `/specdiff <task>` | Compare differences (read-only) | HopSpec.md + Hop.py |
| `/solidify <task>` | Review and confirm solidification path | think -> dynamic |
| `/hoprun <task>` | Execute and debug | Hop.py |
| `/batchhoptest <task> <file>` | Batch testing + automatic analysis | Hop.py -> TestCases/ |
| `/batchanalysis <task>` | Analyze historical test results | TestCases/ |
| `/diagnose <task>` | Diagnose and fix test failures | TestCases/ -> Hop.py |
| `/code2viewspec <task>` | Initial ViewSpec generation | metainfo.md -> ViewSpec/ |
| `/code2view <task>` | Generate observation UI | ViewSpec/ -> View/ |
| `/view2spec <task>` | View -> ViewSpec reverse sync | View/ -> ViewSpec/ |
| `/rag-index` | Build/update Terms/ RAG index | Terms/ -> index |

---

## HopSpec: 7 Atomic Step Types

HopSpec uses a structured tree composed of 7 atomic step types to describe LLM reasoning processes, with theoretical foundation in the Bohm-Jacopini structured program theorem:

| Type | Purpose | Code Mapping |
|------|---------|--------------|
| **LLM** | LLM reasoning (extraction/analysis/judgment) | `hop_get()` / `hop_judge()` |
| **call** | Tool invocation | `hop_tool_use()` |
| **loop** | Loop (for-each / while) | `for item in collection:` / `while cond:` |
| **branch** | Conditional branching | `if condition:` |
| **code** | Pure Python computation | assignment / computation |
| **flow** | Flow control | `return` / `continue` / `break` |
| **subtask** | Subtask (static/dynamic/think) | subfunction / JIT expansion |

---

## Scenario Validation

| Scenario | Model | Baseline Accuracy | HOP Completion Rate | HOP Accuracy |
|----------|-------|-------------------|---------------------|--------------|
| 8-digit large number multiplication | Qwen3-235B-A22B | 30.33% | 100.00% | 97.30% |
| Phishing email detection | Qwen3-32B | 84.32% | 97.56% | 99.01% |
| Medical duplicate diagnosis | Qwen3-235B-A22B | 76.00% | 100.00% | 99.00% |

**Metric Definitions**:
- **HOP Completion Rate** = Number of samples passing verification / Total sample count
- **HOP Accuracy** = Number of samples passing verification and correct / Number of samples passing verification

---

## Technology Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.14** | Full async/await coroutines |
| **openai** (AsyncClient) | LLM calls, compatible with vllm / siliconflow / bailian / ollama / sglang etc. |
| **pydantic** | Structured outputs (Structured Outputs) |
| **pyyaml** | Configuration file parsing |
| **DuckDB VSS** | RAG vector storage |
| **Jinja2** | View SSR rendering |
| **HTMX** | Frontend interaction (no JS framework) |
| **pywebview** | Desktop application container |
| **uv** | Package management |

---

## Configuration

### settings.yaml (three-section format)

```yaml
defaults:                          # Global default parameters
  max_tokens: 4000
  temperature: 0.1

llms:                              # LLM endpoint definitions
  kimi-k2:
    base_url: "https://..."
    model: "Kimi-K2-Instruct-0905"
    protocol: "aistudio-vllm"
  qwen3-235b:
    base_url: "https://..."
    model: "Qwen3-235B-A22B"

profiles:                          # LLM combinations (first is default)
  kimi-full:
    run: kimi-k2
    verify: kimi-k2
  cross-verify:
    run: kimi-k2
    verify: qwen3-235b
```

### .env Key Configuration

```env
HOP_KEY_kimi_k2=sk-xxx
HOP_KEY_qwen3_235b=sk-xxx
```

LLM names and `.env` variable names are normalized by converting `-.` to `_` + uppercase on both sides.

---

## Documentation

### Engine API Documentation (`hoplogic/docs/`, 35 docs)

| Document | Content |
|----------|---------|
| [hop.md](hoplogic/docs/hop.md) | Three core operator APIs (entry document) |
| [hop_session.md](hoplogic/docs/hop_session.md) | HopSession session management |
| [hop_processor.md](hoplogic/docs/hop_processor.md) | HopProc internal methods |
| [hop_validators.md](hoplogic/docs/hop_validators.md) | Verifier details |
| [hop_config.md](hoplogic/docs/hop_config.md) | Configuration and constants |
| [hop_settings.md](hoplogic/docs/hop_settings.md) | Settings configuration guide |
| [hop_engineering.md](hoplogic/docs/hop_engineering.md) | Engineering specification overview |
| [hop_view.md](hoplogic/docs/hop_view.md) | View shared library API |
| [hop_skill.md](hoplogic/docs/hop_skill.md) | Skill component API |
| [hop_rag.md](hoplogic/docs/hop_rag.md) | RAG component API |
| [hop_mcp.md](hoplogic/docs/hop_mcp.md) | MCP Client API |
| [hop_subtask.md](hoplogic/docs/hop_subtask.md) | subtask and progressive solidification |
| [hop_batch_runner.md](hoplogic/docs/hop_batch_runner.md) | Batch testing CLI |
| [hop_testing.md](hoplogic/docs/hop_testing.md) | Unit testing instructions |
| [getting_started.md](hoplogic/docs/getting_started.md) | Quick start guide |

### Terminology and Specification Documents (`Terms/`, 16 docs)

| Document | Content |
|----------|---------|
| [HOP高阶程序_en.md](Terms/HOP高阶程序_en.md) | HOP overall definition and design philosophy |
| [HOP核心算子_en.md](Terms/HOP核心算子_en.md) | Core operator invocation instructions |
| [HOP 2.0 技术定位_en.md](Terms/HOP%202.0%20技术定位_en.md) | Technical positioning and design philosophy |
| [HopSpec格式规范_en.md](Terms/HopSpec格式规范_en.md) | 7 atomic step type format specifications |
| [ViewSpec格式规范_en.md](Terms/ViewSpec格式规范_en.md) | Three-layer UI specifications |
| [HopletView架构规范_en.md](Terms/HopletView架构规范_en.md) | View five-layer architecture specifications |
| [HopLib规范_en.md](Terms/HopLib规范_en.md) | Skill library specifications |
| [HopSpec vs Kiro Spec_en.md](Terms/HopSpec%20vs%20Kiro%20Spec_en.md) | Comparison analysis with Kiro Spec |
| [HOP vs Burr_en.md](Terms/HOP%20vs%20Burr_en.md) | Comparison analysis with Burr framework |
| [HopJIT_en.md](Terms/HopJIT_en.md) | JIT mode architecture and API |
| [ChatFlow组件规范_en.md](Terms/ChatFlow组件规范_en.md) | Interactive dialogue flow component specifications |
| [批量测试数据格式规范_en.md](Terms/批量测试数据格式规范_en.md) | Batch testing JSONL format specifications |

---

## License

[Mozilla Public License Version 2.0](LEGAL.md)

## Disclaimer

Non-release versions of HOP are prohibited from use in any production environment, and may contain vulnerabilities, insufficient functionality, security issues, or other problems.



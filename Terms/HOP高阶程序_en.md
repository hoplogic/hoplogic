# HOP High-Order Program

This document serves as a comprehensive definition and key points guide for HOP high-order programs, designed for Claude Code (or any AI programming assistant). This explanation aims to help AI understand the essence, design principles, and key workflows of HOP.

#### **I. What is HOP? A Core Definition**

**High-Order Program (HOP)** is a **trusted control program** designed for large language models (LLMs) to execute professional domain tasks. It is not a regular script, but an engineering asset that integrates **precise program logic**, **domain knowledge definitions**, and **multi-layer verification mechanisms**.

You can understand it as **"the machine-executable version of standard operating procedures (SOP) in the era of large models"**. Its core objective is to address the reliability issues caused by LLM "hallucinations," enabling them to achieve 99%+ reliability thresholds in professional scenarios like finance and healthcare.

As a concrete implementation for human-AI interactive iteration, HOP can be implemented as a Python program using HOP operators in HopEngine (see "HOP Core Operators"). Currently, implementation using Python 3.14 coroutine async mechanisms is recommended.

#### **II. Core Design Philosophy: Controllable, Reliable, Iterative**

1.  **Controllable**: Through clear structures (Task, Term, HopLib) and specifications (HopSpec), define the behavior boundaries of intelligent agents, ensuring predictable and manageable processes. HopSpec inherits structured programming paradigms (Böhm-Jacopini 1966 / Dijkstra 1968) - control flow is expressed as nested trees rather than jump graphs, with 7 atomic types covering the three primitives of sequence, selection, and loop + LLM inference + external calls + task decomposition + flow control. The tree structure makes execution paths predictable and statically verifiable, which is the fundamental design choice that distinguishes HOP from DAG/graph-based workflow frameworks (LangGraph, CrewAI, Dify, etc.) (see `Terms/HOP 2.0 Technical Positioning.md` § HopSpec Design Philosophy).

2.  **Reliable**: Reliability comes from two layers of assurance. **Architecture layer** - the structured logic skeleton (loop/branch/code/subtask) is controlled by deterministic programs, LLM's non-deterministic intelligence is strictly isolated in leaf nodes (LLM/call) and controlled subtask containers (subtask), without invading control flow; even if an LLM step hallucinates, the impact is confined within that node and won't spread to the entire process. **Operator layer** - the three major operators (hop_get/hop_judge/hop_tool_use) have built-in multi-level verification mechanisms (format validation, reverse verification, forward cross-verification, tool verification), with automatic retry and feedback on verification failure, ensuring each LLM step's output meets professional precision requirements.

3.  **Iterative**: Iteration occurs at three levels. **HopSpec itself is iterable** - subtasks gradually solidify from an intention (think) (historical alias `seq_think` for compatibility) to predefined steps (static), making the Spec smarter and more efficient through usage. **Bidirectional Spec↔Code iteration** - through step_name anchor points for bidirectional synchronization (`/specsync` Spec→Code increment, `/code2spec` Code→Spec reverse), debug code changes can be written back to Spec, expert Spec changes can incrementally follow code, Spec won't become outdated through iteration. **Data-knowledge dual-driven evolution** - every execution feedback (especially Bad Cases) is attributed through residual analysis to knowledge gaps or skill gaps, transforming into fuel for system optimization, making the intelligent agent a "living system."

#### **III. HOP 2.0 Project Framework: Three Core Components**

An HOP project consists of the following three layered and focused components:

| Component | Directory/Location | Core Responsibility | Responsible Role |
| :--- | :--- | :--- | :--- |
| **Task (Task)** | `./Tasks/<TaskName>/` | Defines an executable business unit. Contains the complete iteration chain from natural language SOP to executable code (Hoplet). | **Echo (Domain Expert)** defines SOP; **Delta (Technical Expert)** implements code. |
| **Term (Terminology)** | `./Terms/` or `./Terms.<Industry>` | Provides unambiguous standardized definitions for professional domain concepts. The foundation for intelligent agents to "understand" the business. | **Echo (Domain Expert)** leads definition and alignment. |
| **HopLib (Skill Library)** | `./HopLib/` or External MCP | Stores verified, reusable Hoplets or external tools (like RAG, OCR interfaces). The "arsenal" of intelligent agents. | **Delta (Technical Expert)** develops, maintains, and integrates. |

**Key Files and Processes (under Tasks/<TaskName> directory):**
1.  `Task.md`: (Written by Echo) Describes task objectives and SOP in natural language.
2.  `Hoplet/HopSpec.md`: (Generated by AI, confirmed by Echo) A normalized, unambiguous task specification document generated based on Task.md and Term.
3.  `Hoplet/Hop.py`: (Generated by AI, optimized by Delta) Complete executable code (like Python) that can be executed by HopEngine.
4.  `Hoplet/metainfo.md`: Task metadata contract, defining input/output contracts, runtime modes (interactive/batch), dependencies, and standardized test metrics (completion rate, accuracy, performance). Automatically generated by `/spec2code`.
5.  `TestCases/`: Stores test cases and results for validating task reliability.

#### **IV. Key Workflow: "Data-Model Unified Approach" Iteration Cycle**

HOP's power relies on a continuous evolution mechanism driven by **business data** and **industry knowledge**.

1.  **Role Collaboration (FDE paradigm reference)**:
    *   **Echo (Domain Expert)**: Responsible for top-level design. Defines SOP, defines Term, and confirms `HopSpec` and `TermSpec`.
    *   **Delta (Technical Expert)**: Responsible for engineering implementation. Generates and optimizes code, maintains HopLib.
    *   **Driving Core**: **Bad Cases** from production environments.

2.  **Residual Analysis Process**:
    When tests fail or Bad Cases are received, conduct structured attribution rather than simple retry.
    *   **Attribution Path A (Knowledge Gap)**: The intelligent agent "doesn't understand." Problems may stem from ambiguous `Term` or unclear `SOP`. **Echo** corrects `TermSpec.md` or `Task.md`.
    *   **Attribution Path B (Skill Gap)**: The intelligent agent "does it wrong." Problems may stem from code logic errors or insufficient `HopLib` capabilities. **Delta** modifies `Hop Code` or expands the skill library.
    *   **Other Attribution**: Insufficient data supply, task scale too large requiring splitting, LLM capability bottlenecks, etc.

3.  **Bidirectional Spec↔Code Synchronization**:
    HopSpec (specification document) and Hop.py (executable code) support bidirectional incremental iteration:
    *   **Code→Spec (`/code2spec`)**: When Delta modifies code logic during debugging or optimization (adding steps, adjusting verification strategies, modifying task descriptions), changes are written back to HopSpec to keep specification documents synchronized with code.
    *   **Spec→Code (`/specsync`)**: When Echo modifies HopSpec (adjusting processes, adding steps, modifying verification strategies), incrementally updates corresponding steps in code while preserving Delta's custom error handling and optimization logic.
    *   **Difference Detection (`/specdiff`)**: Read-only diagnosis, outputs step-level difference reports to help teams understand deviations between Spec and Code before synchronization.
    This ensures that during iteration, Spec remains a faithful description of Code, and Code remains a precise implementation of Spec.

4.  **Evolution Closed Loop**:
    `Analyze(Bad Case) -> Attribute -> Fix(Knowledge/Code) -> Bidirectional Sync(Spec↔Code) -> Regenerate and Test -> Validate and Store`
    Each cycle precipitates new knowledge (Term) or more reliable skills (HopLib), enabling the intelligent agent to continuously evolve toward "more controllable, more reliable."

#### **V. Action Points for Claude Code**

When you (as an AI programming assistant) participate in HOP projects, please remember:

1.  **You are not writing regular code, but "compiling" domain knowledge.** Your outputs (HopSpec, Hop Code) must be precise translations of domain expert (Echo) intentions.
2.  **Strictly adhere to framework structure.** Generate or modify correct files in correct directories, maintaining clear project structure.
3.  **Generated code must be verifiable.** Reserve verification interfaces at key logic points, supporting exception handling and residual iteration.
4.  **Actively utilize HopLib.** Prioritize calling verified skills rather than regenerating logic.
5.  **Pay attention to iteration signals.** When receiving test failure information or Bad Case descriptions, assist developers in attribution analysis and regenerate or correct relevant parts accordingly.

**Ultimate Goal**: Collaborate with human experts to transform unstructured professional knowledge into **executable, testable, evolvable** high-order intelligent agents (Hoplet), making the construction of professional AI applications "within reach."
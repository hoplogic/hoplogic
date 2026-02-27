# ViewSpec Format Specification

## Design Motivation

**ViewSpec organizes and constrains UI interaction logic with a concise format that inherits from HopSpec, making it easy for humans to customize and accurate for AI to implement.**

**HopSpec's core is structured programming, ViewSpec's core is component encapsulation and event-driven architecture.**

**Inheritance**: Just like HopSpec, ViewSpec uses Markdown, numbered steps, and primitive-driven design - if you know HopSpec, you know ViewSpec. HopSpec uses `LLM`/`call`/`branch`/`loop` to describe execution flow, while ViewSpec uses `render`/`call`/`branch`/`emit` to describe interaction flow. The format is identical, the semantics are dual, with no additional learning cost. The design-to-implementation process is equally smooth - first think through how the interface is divided into sections and what data each displays, then define how these sections communicate, and finally detail each specific interaction step. Each layer of granularity is a usable design artifact, with the next layer expanding on the previous, creating no gaps. During implementation, each declaration has a definite code generation target, which AI can map item by item without needing to infer or imagine.

**Human-AI Division of Labor**: Humans focus on design decisions - interface layout, data display, interaction behavior; AI focuses on implementation mechanisms - asynchronous scheduling, state synchronization, style rendering. Each file has decisions first and details later - humans can stop reading after the decisions, while AI reads everything from start to finish.

### Inspiration Sources

| Source | Inspiration |
|--------|-------------|
| [JSON Schema Form](https://rjsf-team.github.io/react-jsonschema-form/) | Data Schema and UI Schema separation |
| [W3C Design Tokens](https://design-tokens.github.io/community-group/format/) | Design variables abstracted as tokens |
| [HopSpec](./HopSpec格式规范.md) | Markdown format, numbered steps, atomic primitives |

---

## Core Concepts

### Design Philosophy

**HopSpec's core is structured programming, ViewSpec's core is component encapsulation and event-driven architecture.**

HopSpec places LLM intelligence at controlled nodes within a deterministic program skeleton, forming structured execution flow through operators, steps, and verification. ViewSpec's dual approach: encapsulate UI components as **mutually isolated interaction zones (Zone)** - each Zone owns its interface elements and state, Zones communicate through **message events**, and direct manipulation of other Zones' internal states is prohibited.

| Paradigm | Core Unit | Composition Mechanism | Constraint Method |
|----------|-----------|----------------------|-------------------|
| HopSpec (Structured Programming) | Atomic steps (LLM/call/loop/...) | Step sequences + control flow | Verification loop (reverse/forward/tool) |
| ViewSpec (Component Encapsulation + Events) | Zone (isolated interaction partition) | Message event passing | Boundary encapsulation (private state, public interface) |

**Three Boundary Rules**:

1. **Zone owns its DOM subtree and state** - external code cannot directly read/write Zone internal elements or variables
2. **Zones communicate through message events** - Zones emit events via `emit` and receive events via `on`. Zone A cannot directly `set Zone B's internal #element`
3. **Zone executes at most one async coroutine at a time** - async `call` is directly embedded in the event step sequence (consistent with HopSpec), Zone guarantees only one coroutine event executes at any moment. During waiting, it can display progress, be aborted, or execute other sync events not blocked by guard

### ViewSpec vs HopSpec Comparison

| Dimension | HopSpec | ViewSpec |
|-----------|---------|----------|
| Description Object | Backend execution logic | Frontend UI interaction |
| Input Source | Task description (original SOP) | Data contract (input/output fields) + execution logic (state branches) |
| Generation Target | Single-file executable code | Multi-file UI project |
| Core Abstraction | 7 atomic step types (structured programming) | Zone + message events (component encapsulation + event-driven) |
| Anchor Mechanism | step_name (Spec↔Code alignment) | zone_id + event_name + field_name |
| Interaction Model | coroutine step tree | Zone tree + event routing |
| Async Handling | async/await coroutines | coroutine events (`call` embedded step sequence, single Zone single coroutine) |

### Directory Structure

```
ViewSpec/
├── index.md           # Overview: Tab list + Zone index + API adapter + common behavior + primitive definitions + file routing table
├── rendering.md       # Rendering mapping: input/output fields + composite components + result normalization + statistical aggregation
├── theme.md           # Layout theme: Design Tokens + layout dimensions + CSS class list + animations
└── tabs/              # Interaction flow: one directory per Tab, one file per Zone
    ├── main/          #   Main function Tab (named by use case, e.g. audit/, solve/, edit/)
    │   ├── _tab.md    #     Tab overview: layout + Zone topology + event routing table
    │   ├── InputForm.md     # Zone: input form
    │   └── ResultArea.md    # Zone: result display
    ├── settings/      #   Settings Tab (example)
    │   ├── _tab.md
    │   └── SettingsForm.md
    └── ...
```

> **HOP Application Example**: In Hoplet projects, ViewSpec is typically placed in `Tasks/<TaskName>/View/ViewSpec/`, with typical Tab combinations being audit/batch/history/stats/perf five Tabs.

**Design Principles**:

- **One Zone per file** - Zone is ViewSpec's core unit, one file per Zone, independently maintained, independently diffed
- **One directory per Tab** - Tab directory contains `_tab.md` declaring layout and inter-Zone routing, other files each represent a Zone
- **Zone files use PascalCase naming** - consistent with component naming in code: `InputForm.md`, `DetailPane.md`
- **rendering.md merges input+output+stats** - they are closely related, separating them increases navigation cost
- **theme.md is independent** - rarely changes across tasks, independent for easy reuse/override
- **index.md is the entry point** - contains meta info header, Tab overview table, Zone index, common behavior and file routing table, AI reads ViewSpec starting here

### Generation Pipeline

```
Data contract + execution logic ──> ViewSpec/ ──> code generation ──> UI project files
                        (can be manually edited)
```

> **HOP Toolchain**: `/code2viewspec` initially generates ViewSpec from metainfo.md + HopSpec.md, `/code2view` generates View code from ViewSpec, `/view2spec` reverse synchronizes.

### ViewSpec's Dual Role

As code maturity increases, ViewSpec serves two roles:

| Role | Applicable Object | ViewSpec Content | Toolchain Behavior |
|------|-------------------|------------------|-------------------|
| **Generation Specification** | generated Zone (code independently generated per task) | Step sequence is prescriptive, defines "what code should do" | `/code2view` reads → generates code |
| **Interface Contract** | shared Zone (fixed code in shared library) | Step sequence is descriptive, records "what code does"; parameterized interface declares customization capability | `/code2view` only extracts config parameters |

The same ViewSpec directory can mix Zones of both roles (see §2.1 Zone implementation sources). This aligns with HOP engine's progressive solidification concept - after code evolves from "generate every time" to "shared library", ViewSpec naturally evolves from generation specification to interface contract.

---

## 1. Overview (Hub Layer) — `index.md`

index.md is the ViewSpec entry point, containing global information, file routing table and file index. Does not contain specific Tab interaction details (those are in `tabs/*.md`).

### 1.1 Meta Information Header

Declares ViewSpec's input sources for traceability of data contract and execution logic:

```markdown
# ViewSpec: <AppName>

> Data Contract: <data contract file path> -- input/output fields
> Execution Logic: <execution logic file path> -- state branches, interaction flow (optional)
```

> **HOP Example**: In Hoplet projects typically `> Data Contract: Hoplet/metainfo.md` + `> Execution Logic: Hoplet/HopSpec.md`.

### 1.2 Tab List

Lists all Tabs in a table, linking to corresponding description files:

```markdown
## Tab List

| # | tab_id | Name | Layout | Description Directory |
|---|--------|------|--------|----------------------|
| 1 | **audit** | Execute [Default] | form + result | [tabs/audit/_tab.md](tabs/audit/_tab.md) |
| 2 | **batch** | Batch | form + progress | [tabs/batch/_tab.md](tabs/batch/_tab.md) |
| 3 | **history** | History | sidebar + detail | [tabs/history/_tab.md](tabs/history/_tab.md) |
| 4 | **stats** | Statistics | grid | [tabs/stats/_tab.md](tabs/stats/_tab.md) |
| 5 | **perf** | Performance | grid + table | [tabs/perf/_tab.md](tabs/perf/_tab.md) |
```

**Layout Modes**:

| Layout | Description | Typical Tab |
|--------|-------------|-------------|
| `form + result` | Top form, bottom result | Execute |
| `form + progress` | Top config, bottom progress | Batch |
| `chat-flow` | Top input + middle scrollable message flow + bottom feedback bar | Interactive solving |
| `sidebar + detail` | Left list (fixed width), right detail | History |
| `grid` | Equal-width grid cards | Statistics |
| `grid + table` | Card grid + data table | Performance |

Can append **on-demand loading** table explaining data request strategy for each Tab switch:

```markdown
| Tab | Trigger on Switch | Cache |
|-----|-------------------|-------|
| audit | none (waits for user action) | none |
| batch | `refreshBatchFiles()` | reload every time |
| history | `loadHistoryFiles()` | reload every time |
| stats | `loadProfileSelector()` + `loadStats()` | Profile list loads once |
| perf | `loadPerf()` | reload every time |
```

### 1.3 API Adapter Layer

Frontend initiates HTTP requests directly through HTMX declarative attributes, server returns HTML fragments. No JS API adapter needed.

```markdown
## API Adapter Layer

Frontend initiates HTTP requests directly through HTMX declarative attributes, server returns HTML fragments. No JS API adapter needed.

**Endpoint Mapping**:

| API Method | Method | Endpoint | Response Type |
|------------|--------|----------|---------------|
| `runTask(input)` | POST | `/api/run` | HTML fragment |
| `listTestFiles()` | GET | `/api/test-files` | HTML fragment |
| `loadResult(name)` | GET | `/api/results/{name}` | HTML fragment |
| `getStats(profile?)` | GET | `/api/stats?profile=` | HTML fragment |
```

### 1.4 Common Behavior

Global behavior declarations applicable to all Tabs:

```markdown
## Common Behavior

- **Error Overlay**: Fixed bottom red panel, captures `window.error` + `unhandledrejection`, auto-dismisses after 8 seconds
- **Error Boundary**: Uncaught exceptions in Zone event handling are caught by Error Overlay, don't affect other Zones
- **Long List Performance**: Scroll containers enable virtual scrolling by default; special needs noted in element table with alternative strategies (pagination/truncation)
- **Loading**: spinner (16x16px rotating circle, border-top accent color)
- **Text Selectable**: body/textarea/result-card/json-block/err-table td/th declare `user-select:text`
- **HTML Escaping**: All user data escaped via `esc()`
```

### 1.5 Interaction Primitives

Defines primitives used in Zone files for event handling. Divided into **step primitives** (Zone internal operations) and **communication primitives** (inter-Zone messages).

```markdown
## Step Primitives (Zone Internal Operations)

| Primitive | Meaning | Example |
|-----------|---------|---------|
| `render` | Render content to this Zone's element | `render .content <- spinner` |
| `set` | Set this Zone's element attributes | `set .btn-run <- disabled, text="Running..."` |
| `code` | Local logic (computation, DOM operations, fire-and-forget calls) | `code pct = round(completed / total * 100)` |
| `branch` | Conditional branch | `branch files empty -> render ..., return` |
| `loop` | Iterate | `loop file in files -> render .file-item(file.name)` |
| `timer` | Start/clear timer | `timer start _pollTimer = setInterval(..., 1000ms)` |

## Communication Primitives (Inter-Zone Message Passing)

| Primitive | Meaning | Example |
|-----------|---------|---------|
| `emit` | Emit event outward (routing table distributes to target Zone) | `emit task_submit(desc, ctx)` |
| `call` | Async API call (await, Zone suspended here) | `call API.runTask({...}) -> r` |
```

**Key Constraint**: `render` and `set` can only operate on **this Zone's** elements. To change other Zones' states, must `emit` events for target Zone to handle.

**render Three Sub-operations**:
- **Replace**: `render .content <- spinner` - clear element content then write new content
- **Append**: `render .chat-flow <- append .msg.msg-user(...)` - append child node at element end
- **Remove**: `render remove .thinking` - remove matching child node from DOM

**code Scope**: `code` includes local logic without API calls - pure computation (`pct = round(...)`), DOM query/manipulation (`scrollToBottom`), state updates (`_retryCount++`). Also used for fire-and-forget async calls - don't wait for return, don't suspend Zone: `code API.cancelTask({...}) (fire-and-forget)`.

**Multi-way branch**: When branches exceed two, use colon to introduce branch list, each branch indented, can contain numbered sub-steps:

```markdown
5. branch r.hop_status:
   - "OK":
     1. render .content <- ConfirmedCard(r)
     2. emit hide_feedback
   - "UNCERTAIN":
     1. render .content <- SolutionCard(r)
     2. emit show_feedback("feedback")
   - "FAIL":
     1. render .content <- ErrorCard(r)
     2. emit show_feedback("retry")
```

Two-way branches can use `->` shorthand: `branch r.error -> render error-card; return`.

**Numbering Convention**: Steps use continuous integer numbering (1, 2, 3...). When manually inserting new steps, use letter suffixes (e.g. `2a`, `2b` between 2 and 3), no need to renumber subsequent steps. AI processing automatically rearranges to clean continuous numbering.

### 1.6 File Index

Lists all files in ViewSpec directory for navigation. Zone files are indexed in each Tab's `_tab.md`.

```markdown
## File Index

- [rendering.md](rendering.md) -- Rendering mapping (input/output fields + composite components + statistical aggregation)
- [theme.md](theme.md) -- Layout theme (Design Tokens + layout dimensions + CSS class list + animations)
- [tabs/audit/_tab.md](tabs/audit/_tab.md) -- Execute Tab (2 Zones: InputForm + ResultArea)
- [tabs/batch/_tab.md](tabs/batch/_tab.md) -- Batch Tab (1 Zone: BatchPanel)
- [tabs/history/_tab.md](tabs/history/_tab.md) -- History Tab (2 Zones: FileList + DetailPane)
- [tabs/stats/_tab.md](tabs/stats/_tab.md) -- Statistics Tab
- [tabs/perf/_tab.md](tabs/perf/_tab.md) -- Performance Tab
```

### 1.7 File Routing Table (Recommended)

When View layer runtime code is distributed across multiple files (shared library templates, task-level configs, snapshot files), adding a **file routing table** in `index.md` effectively prevents editing wrong files.

Table uses "what to change → which file to change" mapping format:

```markdown
## File Routing Table

> Key reference to prevent editing wrong files.

| What to Change | Which File to Change |
|----------------|----------------------|
| JS interaction logic | `hoplogic/hop_view/chatflow/chatflow.js` (shared IIFE) |
| JS config constants injection | `hoplogic/hop_view/templates/base.html` (`{% if interactive %}` block) |
| CSS styles | `hoplogic/hop_view/chatflow/chatflow.css` |
| Result card HTML | `hoplogic/hop_view/templates/fragments/run_result.html` |
| SSE endpoint | `hoplogic/hop_view/transport.py` |
| Task config | `Tasks/<TaskName>/View/config.py` |
| Transport thin launcher | `Tasks/<TaskName>/View/app.py` / `web.py` |
| Snapshots (don't change) | `Tasks/<TaskName>/View/index.html` |
```

**Usage Scenarios**:
- When project uses `hop_view` shared library, runtime logic is in shared templates, not `index.html` snapshots - file routing table clarifies this distinction
- ChatFlow and other interactive components involve JS/CSS/HTML fragments/Transport multiple files, routing table helps AI and humans locate target files directly
- Non-interactive projects (pure HTMX) with fewer files can omit this

---

## 2. Interaction Flow (Interaction Layer) — `tabs/*/`

Each Tab has one directory under `ViewSpec/tabs/`. **Each Zone has one independent file**, `_tab.md` declares Tab layout and inter-Zone event routing.

### 2.1 Zone (Interaction Partition)

Zone is ViewSpec's core structural unit, corresponding to an independent interaction partition on the interface.

**Zone's Four Elements**:

| Element | Description | Example |
|---------|-------------|---------|
| **Elements** | Zone's owned DOM subtree | `textarea`, `button`, `div.content` |
| **State Variables** | Zone's internal runtime variables | `_sessionId`, `_retryCount` |
| **Inbound Events** | Messages Zone receives from outside | `on task_submit(desc, ctx)` |
| **Outbound Events** | Messages Zone emits outward | `emit need_feedback("supplement")` |

**Encapsulation Rules**:
- Zone's `render`/`set` can only operate on its own elements
- To change other Zones' states, must `emit` events for target Zone to handle
- No shared variables between Zones

**Enabled/Disabled States**:
- Each interactive element within Zone (buttons, inputs, etc.) has enabled/disabled state
- Each Zone's event handler has enabled/disabled state (disabled triggers are ignored)
- When event handler is disabled, **propagates reversely along routing table**: triggering elements in other Zones that `emit` to this event are also automatically disabled

#### Zone Implementation Sources

Zone implementation code has two sources, ViewSpec file roles differ accordingly:

| Implementation Source | Code Location | ViewSpec Role | `/code2view` Behavior |
|----------------------|---------------|---------------|----------------------|
| **generated** | Generated by `/code2view` to `Tasks/*/View/` | **Generation Specification** - step sequence is code generation input | Reads ViewSpec → generates code |
| **shared** | Fixed code in shared library (e.g. `hop_view/chatflow/chatflow.js`) | **Interface Contract** - records solidified behavior, declares parameterized interface | Skips code generation, only extracts config parameters → `config.py` |

**generated Zone** (default): ViewSpec's step sequence is prescriptive - AI generates code according to steps, step changes trigger code regeneration. This is ViewSpec's original role.

**shared Zone**: Code is solidified in shared library, runtime customization through parameter injection. In this case:
- **Shared library's ViewSpec** (e.g. `hoplogic/hop_view/chatflow/ViewSpec/`) records complete event flow and behavior as **interface documentation** - it describes "what the code does", not "what the code should do"
- **Task-level Zone file** only declares **customization points** (parameter values, branch details, field mappings), references shared ViewSpec for complete behavior

**Progressive Solidification**: Zone's implementation source is not static. As code matures, Zone can evolve from `generated` to `shared` - code is promoted to shared library, task-level ViewSpec shrinks from generation specification to customization declaration. This aligns with HOP engine's progressive solidification (`think → dynamic → static`) (historical alias `seq_think` remains compatible) projected to View layer.

```
generated Zone                    shared Zone
┌─────────────────────┐          ┌─────────────────────────────────┐
│ Task ViewSpec       │          │ Shared ViewSpec (hop_view/)     │
│ ┌─────────────────┐ │          │ ┌─────────────────────────────┐ │
│ │ Complete Step   │ │   Solid  │ │ Complete Step Sequence      │ │
│ │ Sequence        │ │ ──────→ │ │ (Interface Documentation)   │ │
│ │ (Generation     │ │          │ │ Parameterized Interface     │ │
│ │ Specification)  │ │          │ │ Declaration                 │ │
│ └─────────────────┘ │          │ └─────────────────────────────┘ │
│         ↓           │          │                                 │
│   /code2view        │          │ Task ViewSpec                   │
│   generates         │          │ ┌─────────────────────────────┐ │
│                     │          │ │ References Shared ViewSpec  │ │
│                     │          │ │ Customization Parameters +  │ │
│                     │          │ │ Branch Details               │ │
│                     │          │ └─────────────────────────────┘ │
│                     │          │         ↓                       │
│                     │          │   /code2view only generates   │
│                     │          │   config.py                   │
└─────────────────────┘          └─────────────────────────────────┘
```

### 2.2 File Templates

**`_tab.md` (Tab Overview File)**:

```markdown
# <tab_id> (<tab_name>)

Layout: <layout>

## Zone Topology

```
ZoneA ──event1──► ZoneB
  ▲                 │
  └───event2────────┘
```

## Event Routing

| Source Zone | Event | Target Zone | Trigger Action |
|-------------|-------|-------------|----------------|
| ZoneA | event1(args) | ZoneB | Execute xxx |
| ZoneB | event2(args) | ZoneA | Update xxx |

## Zone Files

- [ZoneA.md](ZoneA.md) -- Responsibility description
- [ZoneB.md](ZoneB.md) -- Responsibility description
```

**`<ZoneName>.md` (generated Zone file)**:

```markdown
# Zone: <ZoneName>

> <Zone responsibility description>

Events: event1[coroutine] | event2[sync] | ...
Internal Procedures: proc1(args), ...   (optional)

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `.xxx` | <type> | <initial> | | <desc> |
| `.btn-foo` | .btn-primary | enabled | → event_name | <desc> |

## State Variables

`_var1 = null`, `_var2 = 0`

## Event: <event_name>  [sync|coroutine]

> <trigger condition>
> guard: <.element>, <event:name>, ...   (coroutine only, declares disabled elements and events during execution)

(numbered step sequence. coroutine events contain `call` steps, suspend waiting at call)

## Internal Procedure: <procedure_name>(params)

> <usage description>

(numbered step sequence. Not an event, cannot be triggered externally, only called by this Zone's events)
```

**`<ZoneName>.md` (shared Zone customization file - task level)**:

When Zone implementation comes from shared library, task-level file only declares customization points:

```markdown
# Zone: <ZoneName> (<TaskName> customization)

> Shared implementation: [`<shared ViewSpec Zone file path>`](...)
> This file only describes customization points. General behavior see shared ViewSpec.

## Customization Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| thinking_steps | ["Analyzing...", "Searching...", ...] | thinking bubble step text |
| max_feedback_rounds | 5 | max feedback rounds |
| retry_quota | None (Infinity) | retry quota |

## <TaskName> Specialized Behavior

(Only describes task-specific branch details, field mappings, etc.
Does not repeat protocol, state machine, general event flow already recorded in shared ViewSpec.)
```

**shared Zone files do not describe** (carried by shared ViewSpec):
- Event step sequences (solidified in shared library code)
- State variable definitions (same as above)
- DOM selectors and element tables (same as above)
- General protocol details (SSE, state machines, etc.)

**shared Zone files only describe**:
- Reference declaration (pointing to shared ViewSpec)
- Customization parameter values
- Task-specific branch details (e.g. card content for each `hop_status`)
- Field normalization mapping (task output field name → template lookup chain)

**Zone File Structure**: Title → responsibility description (`>`) → **event summary line** (one line listing all events and internal procedure names, letting people grasp Zone overview at a glance) → `## Elements` → `## State Variables` → `## Events` (can be multiple) → `## Internal Procedures` (optional, can be multiple). Additional sections (e.g. `## Server-Authoritative State Rules`) go last.

**Element Trigger Column**: Element table's `Trigger` column establishes selector→event mapping, making event full chain traceable: find trigger event from element table → find emit from event steps → find target Zone and event from routing table. Non-interactive elements (containers, display areas) leave empty.

**Internal Procedures**: When multiple events share the same step sequence, extract as internal procedure. Internal procedures are not events - cannot be triggered externally, no guard, not counted in "at most one coroutine at a time" constraint. They are just reusable step blocks called by event steps via `code <procedure_name>(args)`.

**Event Parameter Types**: When events carry parameters, use `>` below trigger condition line to annotate parameter type constraints:

```markdown
## Event: show_feedback(mode)  [sync]

> Receives ChatFlow.show_feedback
> mode: "supplement" | "feedback" | "retry" | "resume"
```

Simple types (string, number) are implied in routing table parameter lists and can omit type annotations. Non-trivial constraints like enum values, union types should be explicitly declared.

**Naming Rules**: Zone filenames use PascalCase (e.g. `InputForm.md`, `DetailPane.md`), corresponding to component/function naming in code. `_tab.md` uses underscore prefix to distinguish from Zone files.

### 2.3 Synchronous Events

Events not involving API calls, complete immediately after triggering. Numbered step sequence.

```markdown
## Event: fill_example  [sync]

> Click "Fill Example"

1. set .inp-task <- example task_description
2. set .inp-context <- example context
```

### 2.4 Coroutine Events (coroutine)

Events containing `call` (API calls). `call` is directly embedded in step sequence, Zone suspends waiting for return when reaching `call`, subsequent steps handle results - consistent with HopSpec's async steps.

**Constraint**: At most one coroutine event executes in a Zone at any time.

**Behavior During Waiting**:
- **Progress Display** - `render` steps before `call` have already switched UI to loading/thinking state
- **Abort** - Users can trigger Zone's `cancel` sync event to interrupt coroutine
- **Other Sync Events** - Zone can still receive and process sync events (e.g. update input values), but implementers must prevent state conflicts with coroutine result processing

**Coroutine Guard (guard)**:

When coroutine event starts execution, must synchronously declare which elements and events enter disabled state to prevent conflicting operations during waiting. When coroutine completes (normal return or cancelled), **automatically restores** to enabled.

Format: Below event trigger condition use `> guard:` declaration, comma-separated:

```markdown
## Event: run_task(data)  [coroutine]

> Receives InputForm.submit
> guard: .btn-run, event:submit_feedback

1. render .content <- ThinkingCard
2. call API.runTask(data) -> r
...
```

Guard list items:
- **Elements** - `.selector`: elements within this Zone set to disabled (buttons grayed, inputs non-editable)
- **Events** - `event:<event_name>`: this Zone's event handlers set to disabled (ignored when triggered)

**Cross-Zone Propagation**: When event handler is disabled, reverse lookup along routing table: triggering elements in source Zones that `emit` to this event are also automatically disabled.

Propagation example (chat-flow mode, ChatFlow + ChatInputBar two Zones):
1. ChatFlow's `task_submit` guard declares `event:submit_feedback, event:retry_task` disabled
2. Routing table: `ChatInputBar | submit_feedback → ChatFlow | submit_feedback`
3. → ChatInputBar's button triggering `submit_feedback` (`.btn-feedback`) automatically disabled
4. Coroutine completes → guard restores → ChatInputBar's button automatically restores enabled

ViewSpec only needs to declare this Zone's disabled items in guard, cross-Zone propagation is automatically derived by code generator based on routing table.

**Format** (complete coroutine event example):

```markdown
## Event: run_task(data)  [coroutine]

> Receives InputForm.submit
> guard: event:submit_feedback

1. render .content <- ThinkingCard
2. call API.runTask(data) -> r
3. render remove ThinkingCard
4. branch r.error -> render .content <- ErrorCard(r.error); emit show_feedback("retry"); return
5. branch r.hop_status:
   - OK → render .content <- ConfirmedCard(r); emit hide_feedback
   - UNCERTAIN → render .content <- SolutionCard(r); emit show_feedback("feedback")
   - FAIL → render .content <- ErrorCard(r); emit show_feedback("retry")
```

**Cancel Handling**: If Zone needs abort support, declare an independent `cancel` sync event:

```markdown
## Event: cancel  [sync]

> User clicks abort button (during coroutine waiting)

1. code abort current coroutine
2. render remove ThinkingCard
3. render .content <- info-card("Interrupted")
4. emit show_feedback("resume")
```

**Cancel and Guard Recovery Timing**: After cancel sync event executes, suspended coroutine is considered terminated, guard immediately restores. Implementation can be AbortController aborting network request, or `_cancelled` flag making coroutine skip subsequent steps after `call` returns. Either way, when cancel event completes, all disabled items declared in guard (including cross-Zone propagation) restore to enabled.

**Guard Completeness Rules (Mandatory)**:

Each coroutine event must explicitly declare the following three guard types in `> guard:` line, ViewSpec missing any item is considered incomplete:

| Guard Type | Format | Description |
|------------|--------|-------------|
| **State Variable Guard** | `> guard: _conversationActive` | Event entry `if (flag) return` prevents reentry |
| **Element Guard** | `> guard: .btn-send` | Buttons/inputs disabled during execution |
| **Event Mutual Exclusion Guard** | `> guard: event:submit_feedback` | Other event handlers disabled during execution |

**Complete guard declaration example**:

```
## Event: task_submit(body)  [coroutine]

> External InputArea emit
> guard: _conversationActive, .btn-send, event:submit_feedback, event:retry_task
```

**Recovery Path**: Elements and events declared in guard restore when session ends (normal return, cancel, error). ViewSpec must declare recovery function name (e.g. `_unlockSend()`), and all terminal paths (OK/FAIL/CONFIRMED/error/cancel) must call this function.

**Test Mapping**: Each guard declaration must have corresponding constraint test in `test_html_builder.py`, verifying generated HTML contains this guard's code pattern.

**Error Handling**: API call failures (network exceptions etc.) are handled via `branch` after `call` returns, consistent with business branches - no separate "rejection" phase needed. To distinguish network vs business errors, use `branch r._network_error`.

**Correspondence with HopSpec**:

| HopSpec | ViewSpec |
|---------|----------|
| `await session.hop_get(...)` | `call API.runTask(...)` |
| `if status != OK: return` | `branch r.error -> ...; return` |
| `session.add_feedback(...)` | `emit show_feedback(...)` |

Async `call` is just a suspension point in step sequence, steps before are preparation (UI loading), steps after handle results. This matches HopSpec's `await` operator pattern exactly.

### 2.5 Inter-Zone Event Routing

Zones emit events via `emit`, target Zones receive via inbound events.

**emit Syntax**: `emit <event_name>(args)` - Zone files only write event name, not target Zone. Routing table maps event names to target Zone's inbound events.

**Event Routing Table** (declared in `_tab.md`):

Routing table has four columns: source Zone, event name (unique identifier in routing table), target Zone, target event name (target Zone's inbound event name). Event names and target event names usually match (direct pass-through), when different routing table provides mapping.

```markdown
## Event Routing

| Source Zone | Event | Target Zone | Target Event |
|-------------|-------|-------------|--------------|
| InputArea | task_submit(desc, ctx) | ChatFlow | task_submit |
| ChatFlow | show_feedback(mode) | FeedbackBar | show_feedback |
| ChatFlow | hide_feedback | FeedbackBar | hide_feedback |
| FeedbackBar | submit_feedback(text) | ChatFlow | submit_feedback |
| FeedbackBar | confirm_solution | ChatFlow | confirm_solution |
| FeedbackBar | retry_task | ChatFlow | retry_task |
```

This table is centrally declared in `_tab.md`, making Zone communication topology clear at a glance, also the core anchor for code review and diff. Each Zone file only needs to handle its own inbound events, no need to understand global routing.

**Authority Rule**: Routing table is the sole authority for event names. Event target names in Zone files' `emit` and inbound event names must match routing table. When routing table and Zone files have naming conflicts, routing table prevails.

### 2.6 Zone Element Declaration

Declares DOM elements owned by Zone (including initially hidden ones).

**Format**:

| Column | Description | Example |
|--------|-------------|---------|
| Selector | DOM selector within Zone | `.btn-run`, `.content`, `textarea` |
| Type | HTML element type or CSS class | `textarea`, `select`, `.btn-primary`, `div` |
| Initial State | State when page loads | `empty`, `hidden`, `value=5`, `enabled, "Run"` |
| Description | Element purpose | `Input: task_description`, `Execute button` |

**Selector Naming Convention**:
- Zone elements use relative selectors: `.btn-run`, `.content`, `textarea`
- In actual generated code, prefix determined by Zone's Tab `tab_id` (e.g. `.solve-input .btn-run`)
- Elements without fixed selectors use parentheses: `(Fill Example)`

**Dynamic Child Elements** (optional): For conditionally rendered child elements within Zone, declare in second table. "Selector" and "Description" columns required, middle column can be customized per Zone semantics (e.g. "Condition", "Role", "Trigger", etc.):

```markdown
Dynamic Child Elements:

| Selector | Condition | Description |
|----------|-----------|-------------|
| .stats-grid (4 cards) | when records exist | batch summary card group |
| .result-card | when credit_score exists | gauge + errors table + Raw JSON |
```

In conversation flow scenarios, middle column can be changed to more semantically appropriate names like "Role":

```markdown
Dynamic Child Elements (message bubbles, appended to .chat-flow):

| Selector | Role | Description |
|----------|------|-------------|
| `.msg.msg-user` | user | user message bubble (right-aligned) |
| `.msg.msg-system` | system | system message bubble (left-aligned) |
```

### 2.7 When to Need Independent Zone

**Need Independent Zone**:
- Area has its own lifecycle (appear/disappear/state switching)
- Area is triggered by multiple other areas
- Area has its own async operations
- Area's interaction logic is complex enough (>5 events)

**Don't Need Independent Zone**:
- Pure display area (no interaction, no state)
- One-time rendered cards (SolutionCard content rendered by ChatFlow, no need for independent Zone)
- Simple sync events, no async operations, only controlled by one Zone (e.g. feedback input bar, as internal element of parent Zone - see §2.8 ResultArea)

**Rule of Thumb**: Only need independent Zone when area has independent async operations or is triggered by multiple Zones. Pure emit thin shell (collect input → emit) usually not worth splitting.

### 2.8 Example: Execute Tab (form mode, 2 Zones)

Directory structure:

```
tabs/audit/
├── _tab.md          # Tab overview + event routing
├── InputForm.md     # Zone: input form
└── ResultArea.md    # Zone: result display + feedback
```

**`_tab.md`**:

```markdown
# audit (Execute)

Layout: form + result

## Zone Topology

```
InputForm ──run_task──► ResultArea
```

## Event Routing

| Source Zone | Event | Target Zone | Target Event |
|-------------|-------|-------------|--------------|
| InputForm | run_task(data) | ResultArea | run_task |

## Zone Files

- [InputForm.md](InputForm.md) -- Input form: fill data, submit triggers execution
- [ResultArea.md](ResultArea.md) -- Result area: display results + feedback interaction
```

**`InputForm.md`**:

```markdown
# Zone: InputForm

> Input form: fill audit data, submit triggers execution

Events: fill_example[sync] | submit[sync]

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `textarea.inp-context` | textarea | empty, rows=6 | | Input: context_input |
| `textarea.inp-model` | textarea | empty, rows=6 | | Input: model_output |
| `.btn-run` | .btn-primary | enabled, "Run Audit" | → submit | Execute button |
| (Fill Example) | .btn-secondary | enabled | → fill_example | Fill example data |

## Event: fill_example  [sync]

> Click (Fill Example)

1. set .inp-context <- example context (see rendering.md example data)
2. set .inp-model <- example model_output

## Event: submit  [sync]

> Click "Run Audit"

1. code validate .inp-context and .inp-model non-empty, else return
2. emit run_task({context_input, model_output})
```

**`ResultArea.md`**:

```markdown
# Zone: ResultArea

> Result area: display execution results, handle status branches, manage feedback interaction

Events: run_task[coroutine] | submit_feedback[coroutine]

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `.content` | div | empty | | Result rendering area |
| `.feedback-area` | div | hidden | | Feedback container |
| `textarea.feedback-input` | textarea | empty | | Feedback text |
| `.btn-submit` | .btn-primary | hidden | → submit_feedback | Submit feedback button |

## State Variables

`_sessionId = null`, `_feedbackRound = 0`, `MAX_FEEDBACK = 3`

## Event: run_task(data)  [coroutine]

> Receives InputForm.submit
> guard: .btn-submit, event:submit_feedback

1. render .content <- spinner
2. set .feedback-area <- hidden
3. call API.runTask(data) -> r
4. set `_sessionId` <- r.session_id
5. render .content <- empty
6. branch r.error -> render .content <- error-card(r.error); return
7. branch r:
   - r contains credit_score -> render .content <- result-card (see rendering.md)
   - r.status === "LACK_OF_INFO":
     1. render .content <- result-card
     2. set .feedback-area <- visible
     3. set .feedback-input placeholder <- "Please supplement information..."
   - r.status === "UNCERTAIN":
     1. render .content <- result-card
     2. set .feedback-area <- visible
     3. set .feedback-input placeholder <- "Enter modification suggestions..."

## Event: submit_feedback  [coroutine]

> Click .btn-submit
> guard: .btn-run, event:run_task

1. code `_feedbackRound++`; branch >= MAX_FEEDBACK -> set .btn-submit disabled; return
2. code read .feedback-input.value -> text; if empty then return
3. set .feedback-input <- empty
4. render .content append spinner
5. call API.submitFeedback({session_id: _sessionId, feedback: text}) -> r
6. render .content <- empty
7. branch r: same as run_task steps 6-7
```

FeedbackArea doesn't need independent Zone - no async operations, only controlled by ResultArea, simple interaction. Feedback bar visibility and submission as ResultArea's internal elements and events.

### 2.9 Example: Batch Tab (Single Zone, Async + Timer)

When Tab interaction is simple (no cross-area communication), Tab directory only has `_tab.md` + one Zone file.

Directory structure:

```
tabs/batch/
├── _tab.md          # Tab overview (no cross-Zone routing)
└── BatchPanel.md    # Zone: only Zone
```

**`_tab.md`**:

```markdown
# batch (Batch)

Layout: form + progress

## Zone Files

- [BatchPanel.md](BatchPanel.md) -- Batch testing: file selection + execution + progress polling
```

**`BatchPanel.md`**:

```markdown
# Zone: BatchPanel

> Batch testing: file selection + execution + progress polling

Events: tab_switch[coroutine] | start_batch[coroutine] | poll_progress[coroutine]

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `select.file` | select | empty | | File selector, item format: `name (N records)` |
| `input.workers` | input[number] | value=5, min=1, max=20 | | Concurrent workers config |
| `.btn-batch` | .btn-primary | enabled, "Start Batch" | → start_batch | Start button |
| (Refresh) | .btn-secondary | enabled | → tab_switch | Refresh file list |
| `.progress` | div | hidden | | Progress area container |
| `.progress-bar` | .progress-bar | width=0% | | Progress bar |
| `.status` | div | empty | | Status text |

## State Variables

`_pollTimer = null`

## Event: tab_switch  [coroutine]

> Auto-triggered when switching to batch Tab

1. call API.listTestFiles() -> files
2. render select.file <- files.map -> `<option>name (N records)</option>`

## Event: start_batch  [coroutine]

> Click "Start Batch"
> guard: .btn-batch, select.file, input.workers

1. code read select.file.value -> file; if empty then return
2. code read input.workers.value -> workers
3. set .progress <- visible
4. call API.startBatch({filename: file, workers}) -> result
5. branch result.error -> render .status <- error; return
6. timer start _pollTimer = setInterval(poll_progress, 1000ms)

## Event: poll_progress  [coroutine]

> Timer triggers every 1000ms

1. call API.getBatchProgress() -> p
2. code pct = p.total ? round(p.completed / p.total * 100) : 0
3. set .progress-bar width <- pct%
4. render .status <- `{completed}/{total} ({pct}%) {errors} errors`
5. branch p.running === false:
   - timer clear _pollTimer
   - set .btn-batch <- enabled
   - render .status append `-- Done: {output_file}`
```

### 2.10 Example: History Tab (Dual Zone, Cross-Zone Communication)

Directory structure:

```
tabs/history/
├── _tab.md          # Tab overview + event routing
├── FileList.md      # Zone: left file list
└── DetailPane.md    # Zone: right detail area
```

**`_tab.md`**:

```markdown
# history (History)

Layout: sidebar(240px) + detail(flex:1), total height calc(100vh - 100px)

## Zone Topology

```
FileList ──file_selected──► DetailPane
```

## Event Routing

| Source Zone | Event | Target Zone | Target Event |
|-------------|-------|-------------|--------------|
| FileList | file_selected(name) | DetailPane | load_file |

## Zone Files

- [FileList.md](FileList.md) -- Left file list, 240px fixed width
- [DetailPane.md](DetailPane.md) -- Right detail area, flex:1
```

**`FileList.md`**:

```markdown
# Zone: FileList

> Left file list, 240px fixed width

Events: tab_switch[coroutine] | click_file[sync]

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `.file-list` | div | empty | | File list container |

Dynamic child elements:

| Selector | Trigger | Description |
|----------|---------|-------------|
| `.file-item` | → click_file | File list item |

## Event: tab_switch  [coroutine]

> Auto-triggered when switching to history Tab

1. call API.listResults() -> files
2. branch files empty -> render .file-list <- empty-state "No results"; return
3. loop file in files -> render .file-list <- .file-item(file.name)

## Event: click_file(name)  [sync]

> Click .file-item

1. set all .file-item remove active; set current item <- .active
2. emit file_selected(name)
```

**`DetailPane.md`**:

```markdown
# Zone: DetailPane

> Right detail area, flex:1

Events: load_file[coroutine]

## Elements

| Selector | Type | Initial State | Trigger | Description |
|----------|------|---------------|---------|-------------|
| `.detail` | div | "Select a result file" | | Detail rendering area |

Dynamic child elements:

| Selector | Condition | Description |
|----------|-----------|-------------|
| .stats-grid (4 cards) | when records exist | batch summary |
| .result-card (meta) | `_type === "meta"` | Profile/LLM info card |
| .result-card (audit) | has credit_score | gauge + errors table + Raw JSON |

## Event: load_file(name)  [coroutine]

> Receives FileList.file_selected

1. render .detail <- spinner
2. call API.loadResult(name) -> records
3. branch records empty -> render .detail <- empty-state "Empty"; return
4. code computeBatchStats(records) -> batchStats
5. render .detail <- renderBatchSummary(batchStats)
6. loop (i, rec) in records:
   - branch rec._type === "meta" -> render meta-card
   - branch rec has credit_score -> render result-card(data, idx, expectedScore)
   - else -> render `<details>Record #{i+1}</details>` + json-block
```

---

## 3. Rendering Mapping (Rendering Layer) — `rendering.md`

Rendering mapping defines correspondence between fields and UI components. Divided into: input fields, output fields, composite rendering components, result normalization, statistical aggregation.

**File Structure**: Top `## Field Mapping Quick Reference` uses concise table listing input/output/stat fields→Widget→rules (human decision points), subsequent complete field attributes section (column width, CSS mapping, subfields, etc.) for AI item-by-item mapping.

### 3.1 Input Field Mapping

Declares form component and attributes for each input contract field.

**Format**:

```markdown
## Input Fields

#### <field_name>
- Type: <data_type>
- Widget: <widget_type>
- <key>: <value>
```

**Widget Types** (input):

| Widget | Applicable Type | Description |
|--------|-----------------|-------------|
| `textarea` | `string` | Multi-line text input (default) |
| `input` | `string` | Single-line text input |
| `number` | `int` / `float` | Numeric input |
| `select` | `enum` | Dropdown selection |
| `checkbox` | `bool` | Checkbox |
| `json-editor` | `object` / `array` | JSON editor |

**Attribute Syntax**:

| Attribute | Applicable Widget | Example |
|-----------|-------------------|---------|
| `rows` | `textarea` | `rows=6` |
| `placeholder` | `textarea`, `input` | `placeholder=Enter context` |
| `min` / `max` | `number` | `min=0, max=100` |
| `options` | `select` | `options=High|Low` |
| `default` | all | `default=5` |

**Example Data** (for "Fill Example" button):

```markdown
## Example Data

```json
{
  "context_input": "According to 2023 financial report...",
  "model_output": "Company A 2023 revenue..."
}
```
```

### 3.2 Output Field Mapping

Declares rendering component and rules for each output contract field.

**Format**:

```markdown
## Output Fields

#### <field_name>
- Type: <data_type>
- Widget: <widget_type>
- Rules: <rendering_rules>
```

**Widget Types** (output):

| Widget | Applicable Type | Rendering Effect |
|--------|-----------------|------------------|
| `gauge-circle` | `int` / `float` | Circular indicator (with color thresholds) |
| `badge` | `bool` / `enum` | Status label (two-color) |
| `text` | `string` | Plain text display |
| `table` | `array[object]` | Table (subfields as column headers) |
| `list` | `array[string]` | Ordered/unordered list |
| `json` | `object` / `any` | Collapsible JSON display |

**Rules Syntax**:

gauge-circle thresholds: `>=70:green, >=40:orange, <40:red`

badge two-value: `true:Detected/red, false:Not Detected/green`

table column declaration: `columns:type,location,evidence,severity[badge]`

**Optional Attributes**:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `Range` | Valid value range for numeric fields | `Range: 0-100` |
| `Description` | Field semantic description | `Description: Confidence score` |
| `Empty Hint` | Alternative text when data empty | `Empty Hint: No errors detected` |
| `CSS Class Mapping` | Value to CSS class mapping | `CSS Class Mapping: .gauge.s5/.s4 -> green` |
| `Size` | Element dimensions | `Size: 48x48px, border 3px` |
| `Column Width` | Table column width allocation | `Column Width: type 30%, explanation auto` |
| `Subfields` | Subfield declaration for array[object] | indented bullet list |

**Example**:

```markdown
#### credit_score
- Type: int
- Widget: gauge-circle
- Rules: >=4:green, >=3:orange, <3:red
- Range: 1-5
- CSS Class Mapping: `.gauge.s5`/`.s4` -> green, `.s3` -> orange, `.s2`/`.s1` -> red
- Size: 48x48px, border 3px, font-size 20px

#### errors
- Type: array[{fact|logic, explanation, severity}]
- Widget: table
- Rules: columns:fact|logic,explanation,severity[badge]
- Empty Hint: No errors detected (green text)
- Column Width: fact|logic 30%, explanation auto, severity 70px
- Subfields:
  - fact|logic: string, text
  - explanation: string, text
  - severity: string, badge -- High:red, Low:orange
```

### 3.3 Composite Rendering Components

When multiple output fields combine into one composite UI component, declare its structure here.

**Format**: Use ASCII tree to describe DOM structure, with text explanation of rendering rules for each part.

**Example**:

```markdown
## Composite Rendering Components

### result-card

.result-card
  .result-header
    .gauge.s{N}          -- credit_score gauge-circle
    [expected comparison]     -- conditional rendering
    credit_score text     -- "Credit Score: N/5"
    errors count          -- "N error(s) found"
  .err-table             -- errors table (or empty hint)
  <details>Raw JSON</details>

### expected comparison (conditional rendering)

When record contains `expected_credit_score` field:
- Semi-transparent small gauge (32x32px, opacity:0.5) shows expected value
- zone match indicator: `=`(green) match / `!=`(red) mismatch

**Zone Mapping Rules**:

| Score | Zone |
|-------|------|
| 1-2   | 0    |
| 3     | 1    |
| 4-5   | 2    |
```

### 3.4 Result Normalization

When frontend needs to handle multiple data formats, declare normalization rules:

```markdown
## Result Normalization

Frontend `normalizeResponse()` uniformly handles multiple data formats:

| Format | Source | Identification | Extraction Logic |
|--------|--------|----------------|------------------|
| Direct dict | API.runTask | `credit_score` at top level | use directly |
| Nested result | batch output | `result` field (JSON string) | `JSON.parse(result)` |
| HOP tuple | `(status, json_str)` | `Array.isArray && length===2` | `JSON.parse(r[1])` |
```

### 3.5 Statistical Aggregation Mapping

Declares aggregation metrics in statistics Tab.

**Format**:

```markdown
## Statistical Aggregation

#### <display_label>
- Source Field: <field_path>
- Aggregation: <agg_type>
- Widget: <widget_type>
- Format: <format_spec>
- Color Rules: <threshold_rules>  (optional)
```

**Aggregation Methods**:

| Aggregation | Applicable Type | Description |
|-------------|-----------------|-------------|
| `count` | all | total records |
| `mean` | `int`/`float` | average |
| `rate(value)` | `bool`/`enum` | specific value rate |
| `distribution(subfield)` | `array[object]` | subfield value distribution |
| `zone_accuracy` | custom | zone match rate |
| `group_by(field)` | grouping | aggregate by field grouping |

**Widget Types** (statistics):

| Widget | Description |
|--------|-------------|
| `stat-card` | numeric card (large text + label) |
| `bar-chart` | horizontal bar chart |
| `table` | comparison table |

Can be divided into **server statistics** (Stats Tab, from `API.getStats`) and **client statistics** (history batch summary, frontend calculated) two subsections.

---

## 4. Layout and Theme (Layout Layer) — `theme.md`

### 4.1 Theme Declaration

```markdown
## Theme

- Style: Tokyo Night / Apple
- Color Mode: auto (prefers-color-scheme)
- Font: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Menlo', monospace
- Font Size-Body: 13px
- Font Size-Label: 11px (uppercase, letter-spacing .5px)
- Font Size-Control: 12px
- Line Height: 1.5
- Border Radius-Card: 8px
- Border Radius-Control: 6px
- Spacing Base: 8px
```

### 4.2 Design Tokens

Divided into Light and Dark groups. If using default Tokyo Night colors, can be abbreviated as `[Default Tokyo Night colors]`.

**Complete Format**:

```markdown
## Design Tokens

### Light

- --bg: #f5f5f7
- --bg-card: #ffffff
- --bg-input: #eeeef0
- --bg-tab: #e8e8ec
- --border: #d1d1d6
- --text: #1d1d1f
- --text-dim: #86868b
- --accent: #0071e3
- --accent-fg: #ffffff
- --green: #34c759
- --red: #ff3b30
- --orange: #ff9500
- --purple: #af52de

### Dark

- --bg: #1a1b26
- --bg-card: #24283b
- --bg-input: #1f2335
- --bg-tab: #16161e
- --border: #3b4261
- --text: #c0caf5
- --text-dim: #565f89
- --accent: #7aa2f7
- --accent-fg: #1a1b26
- --green: #9ece6a
- --red: #f7768e
- --orange: #e0af68
- --purple: #bb9af7
```

**Extended Variables** (task-specific semantic variables, format `--name: <light_value> / <dark_value>`):

```markdown
### Extended

- --badge-high-bg: rgba(255,59,48,.15) / rgba(247,118,142,.15)
- --badge-low-bg: rgba(255,149,0,.15) / rgba(224,175,104,.15)
```

### 4.2 Window

```markdown
## Window

- Title: <AppName>
- Width: 1200
- Height: 820
- Min Width: 900
- Min Height: 600
- macOS traffic lights reserved: 80px
```

### 4.3 Layout Dimensions

Table listing key UI area dimension values:

```markdown
## Layout Dimensions

| Area | Property | Value |
|------|----------|-------|
| Tab bar | button padding | 6px 16px |
| History file list | width | 240px (flex-shrink:0) |
| Stats grid | grid-template-columns | repeat(auto-fill, minmax(180px, 1fr)) |
| Gauge circle | dimensions | 48x48px, border 3px |
| Progress bar | height | 20px |
| JSON block | max-height | 300px (overflow-y:auto) |
```

### 4.4 CSS Class List

Lists all custom CSS classes and their Tab scope:

```markdown
## CSS Class List

| Class | Purpose | Tab |
|-------|---------|-----|
| `.tab-bar` | Tab switch bar | global |
| `.panel` / `.panel.active` | Tab panel visibility | global |
| `.gauge` / `.gauge.s1`-`.s5` | Score circular indicator | audit, history |
| `.badge` / `.badge.high` / `.badge.low` | Severity labels | audit, history |
| `.result-card` | Single result card | audit, history |
| `.stats-grid` | Statistics card grid | stats, perf, history |
| `.stat-card` | Statistics card | stats, perf, history |
| `.err-table` | Data table | audit, history, stats, perf |
| `.spinner` | Loading animation | global |
| `.empty-state` | Empty data hint | global |
```

### 4.5 Animations

```markdown
## Animations

- `.spinner`: `spin .6s linear infinite`
- `.progress-bar`: `transition: width .3s`
- Tab button: `transition: all .15s`
```

---

## ViewSpec to Code Mapping

### Rendering Layer -> Code Mapping

| ViewSpec Declaration | Target File | Generated Content |
|---------------------|-------------|-------------------|
| Input field declaration | `index.html` | form `<textarea>` / `<input>` / `<select>` |
| Input field declaration | `app.py` | `Api.run_task()` parameter list |
| Input field declaration | `web.py` | `RunTaskRequest` Pydantic model fields |
| Output field declaration | `renderer.py` | `render_result_card()` widget rendering |
| Composite component declaration | `renderer.py` + `templates/` | Jinja2 template rendering |
| Result normalization | `renderer.py` | `normalize_response()` function |
| Statistical aggregation declaration | `hop_view.datastore` | `get_stats()` ibis aggregation expressions |

### Interaction Layer -> Code Mapping

| ViewSpec Declaration | Target File | Generated Content |
|---------------------|-------------|-------------------|
| Tab list | `index.html` | Tab bar buttons, Panel containers |
| Zone element table | `index.html` | HTML element declarations (class, initial state), Zone corresponding DOM containers |
| Zone state declaration | `renderer.py` / Jinja2 | Python renderer / Jinja2 template state |
| Event routing table | `index.html` | `emit` mapped to function calls/custom event dispatch |
| Sync event steps | `index.html` | HTMX + ~100 lines JS |
| coroutine event steps | `index.html` + `web.py` | HTMX hx-post/hx-get + server-side rendering |
| guard declaration | `index.html` | coroutine entry disables elements/events + finally restore; cross-Zone propagation derived from routing table |
| API endpoint mapping | `index.html` | HTMX hx-* attributes |
| API endpoint mapping | `web.py` | FastAPI routes (return HTMLResponse) |
| API endpoint mapping | `app.py` | pywebview thin launcher (embedded uvicorn) |

### Theme Layer -> Code Mapping

| ViewSpec Declaration | Target File | Generated Content |
|---------------------|-------------|-------------------|
| Design Tokens | `index.html` | `:root { --bg: ...; }` CSS variables |
| Theme properties | `index.html` | `@media (prefers-color-scheme: dark)` |
| Window properties | `app.py` | `webview.create_window(width=..., height=...)` |
| Layout dimensions | `index.html` | CSS dimension values |
| CSS class list | `index.html` | CSS class definitions |
| Animations | `index.html` | `@keyframes` + `transition` |

---

## Design Decisions and Trade-offs

### Why Choose Zone + Event-Driven Over Global Step List

Old ViewSpec used flat event handling (`on_xxx` step sequence + global state variables), which revealed three problems in practice:

1. **Global State Coupling** - variables like `_sessionId`, `_feedbackRound` scattered across multiple event handlers, any event could read/write any variable, changing one required global impact analysis
2. **Cross-Area Operations Implicit** - one event's steps directly `set #chat-input-bar <- hidden` (belonging to another logical area), dependencies could only be inferred by reading step sequences
3. **Async Paths Implicit** - API calls written in middle of step lists (e.g. "step 6: call API.runTask"), cancel/error paths scattered via `_cancelled` flags

Zone + event-driven solves these three problems:

1. **State Encapsulation** - each Zone owns its state, external cannot directly read/write. Zone A's `_sessionId` won't be accidentally modified by Zone B's events
2. **Explicit Communication** - inter-Zone interaction via `emit` events declared in routing table, topology clear at a glance. Code review only needs routing table to understand Zone dependencies
3. **Async Coroutine Constraints** - single Zone single coroutine, `call` embedded step sequence (consistent with HopSpec), cancel/error handled via sync events and `branch`

### Why Each Zone in Independent File

Zone is ViewSpec's core unit, each Zone file contains: element table (~5-10 lines) + state (~1 line) + events (~5-15 lines each). Total 20-60 lines. Independent file benefits:

1. **Precise Granularity** - modifying ChatInputBar interaction only opens `ChatInputBar.md`, doesn't affect other Zones in same Tab
2. **Accurate Diff** - changes confined to single Zone file, clear at a glance in code review
3. **Reuse Potential** - same Zone definition could be referenced by multiple Tabs in future
4. **Parallel Editing** - different Zone edits don't conflict, even within same Tab

`_tab.md` files only contain layout declaration and event routing table (~15 lines), the "wiring diagram" between Zones, keeping lightweight.

### Why `call` Embedded Step Sequence Over Independent Lifecycle

Considered splitting async events into independent phases (trigger/execute/resolve/cancel/reject), but found in practice:

1. **Inconsistent with HopSpec** - HopSpec's `await session.hop_get()` is just one line in step sequence, preparation before, result handling after. Splitting phases introduces extra structure HopSpec doesn't have
2. **Over-formalization** - most events' "trigger" only has 1-2 lines (set loading), "resolve" is just branch handling results, splitting into sections adds format noise
3. **Cancel is Independent Event** - cancel happens during waiting, essentially another event (user clicks abort button), should be declared as Zone's independent sync event, not crammed into same event's sub-phases

Final choice: `call` embedded in step sequence (consistent with HopSpec), cancel/abort are independent sync events, errors handled via `branch`. Simple rule: **at most one coroutine executes in a Zone at any time**, solving race conditions.

```
## Event: run_task(data)  [coroutine]     ## Event: cancel  [sync]
> guard: event:submit_feedback            > (no guard, sync event)
1. render .content <- spinner             1. code abort current coroutine
2. call API.runTask(data) -> r            2. render remove ThinkingCard
3. render remove spinner                  3. render .content <- "Interrupted"
4. branch r.error -> ...
5. branch r.hop_status -> ...

                                          guard auto-restores:
                                            event:submit_feedback <- enabled
                                            source Zone trigger elements <- enabled (propagation)
```

Left is coroutine event's linear steps (`call` suspends, guard disables on entry, restores on completion), right is cancel event triggered by user during waiting (cancel also triggers guard restore). These are two independent events of Zone, not sub-phases of one event.

### Zone Granularity Trade-offs

**Too Coarse** (one Tab one Zone): degenerates to old global state, loses encapsulation benefits.

**Too Fine** (one button one Zone): emit proliferation, simple interactions need routing declarations, adds specification noise.

**Rule of Thumb**: Zone splitting criteria is **independent async operations** or **triggered by multiple Zones**. Pure sync "collect input → emit" thin shell (e.g. feedback input bar) not worth splitting into independent Zone, as internal element of parent Zone - one less routing, one less file, one less jump.

### Cross-Zone Data Passing

Zones have no shared variables. If Zone B needs data held by Zone A, two approaches:

1. **Pass via Event Parameters** (recommended): Zone A emits event with data as parameters, Zone B receives and caches in its own state via inbound events
2. **Get via API Response**: Zone B calls API, gets needed data from response

**Anti-pattern**: Zone B's event steps directly reference Zone A's state variables (e.g. `_lastTaskDescription`). Violates encapsulation rules, even if implementation-wise Zones are just JS variables in same HTML file, ViewSpec level still prohibits this implicit dependency - makes Zone coupling invisible to routing table.

### chat-flow Layout Mode

`chat-flow` is typical layout for multi-turn conversational interaction (e.g. HOP's SolutionSolver Hoplet), different from form+result one-time submission mode. Characteristics:

- **Append Rendering** - each interaction appends message bubbles, doesn't clear history. Heavy use of `render X <- append Y`
- **Multiple Coroutines Coexist** - task_submit, submit_feedback, retry_task three coroutine events mutually exclusive (guard interlock), but share same message flow container
- **Internal Procedures** - multiple coroutines share handleResponse etc. branch logic, extracted as internal procedures to avoid duplication
- **Server-Authoritative State** - display values (rounds, session_id) from API responses, frontend state only for control flow

This mode's Zone split is typically: InputArea (initial input) + ChatFlow (message flow, owns API calls and state machine) + ChatInputBar (bottom feedback bar, pure emit). ChatFlow is heaviest Zone, carrying core state and all coroutine events.

### Shared Zone vs Generated Zone Choice

Same Tab can mix shared and generated Zones. Typical scenario:

```
SolutionSolver / solve Tab:
  InputArea      [generated]  -- each task's input form different, generated by /code2view
  ChatFlow       [shared]     -- shared library fixed code, parameterized customization
  ChatInputBar   [shared]     -- shared library fixed code, parameterized customization
```

**Decision Criteria**: Are Zone's event step sequences identical across multiple tasks (only parameters differ)?
- **Yes** → suitable for solidifying as shared (code promoted to shared library, ViewSpec splits into interface docs + customization declaration)
- **No** → keep generated (each task has unique event flow)

**Progressive Solidification Path** (Zone level):

```
[generated]  multiple tasks generate similar code separately
      ↓       discover code highly repetitive, only parameters differ
[extract]    code promoted to hop_view shared library, parameterized
      ↓       shared library creates ViewSpec directory recording behavior
[shared]     task-level Zone file shrinks to customization declaration
```

See §2.1 Zone implementation sources, §2.2 shared Zone customization file template.

**Anti-pattern**: shared Zone's task-level file still repeats shared component's protocol (endpoints, state machine, event steps), causing task ViewSpec to become outdated when shared component upgrades, AI generates code inconsistent with runtime based on outdated description.

### What Needs Formalization vs What Doesn't

Following HopSpec's principle - **only formalize what AI easily guesses wrong**:

**Needs Formalization** (structured declaration):
- Zone topology and event routing (AI might directly manipulate state across Zones)
- Coroutine guard guard (AI might miss async period disabled mutual exclusion, or forget cross-Zone propagation)
- Coroutine event `call` steps and error branches (AI might miss error handling or cancel events)
- field→Widget mapping (AI might use wrong component type)
- thresholds and color rules (AI might set arbitrarily)
- statistical aggregation methods (AI might miss or use wrong aggregation functions)
- page elements and initial states (ensure event flow references consistent)
- error boundaries (Zone event exception fallback strategy, AI might miss unhandled exception handling)
- long list performance strategy (AI might not virtual scroll or paginate large data lists)

**Doesn't Need Formalization** (natural language or omitted):
- CSS details (AI derives from Design Tokens)
- HTML tag structure (AI derives from layout mode)
- responsive adaptation (AI derives breakpoints and collapse strategies from layout mode and window dimensions)
- complex Zone state enums and state transition diagrams (AI derives from state variables and events for human review reference)
- loading/error etc. common states (consistent across tasks, written in index.md common behavior)
- Zone internal DOM hierarchy (AI derives from element table)

### Human Decisions vs AI Details File Partitioning

Within each ViewSpec file, human decision content comes first, AI implementation details later. Humans can stop at separator line, AI reads everything.

| File | Human Decisions (Front) | AI Details (Back) |
|------|------------------------|-------------------|
| **_tab.md** | layout, Zone topology, event routing | (none, all decisions) |
| **Zone file** | responsibility description, event summary line, event flow semantics, guard | element table selectors, initial state details |
| **rendering.md** | field mapping quick reference table (field→Widget→rules) | complete attributes (column width, CSS mapping, subfields) |
| **theme.md** | style, window title/dimensions | Design Tokens hex values, layout px, CSS class list |
| **index.md** | Tab list, API endpoint list | pvArgs, dual-mode adaptation, primitive definitions |

**Zone file event summary line**: After Zone file title and responsibility description, immediately follows one-line event summary, letting people see all Zone events and internal procedures at a glance:

```markdown
# Zone: ChatFlow

> Message flow: manage conversation history, execute API calls, branch render by hop_status.

Events: task_submit[coroutine] | submit_feedback[coroutine] | retry_task[coroutine] | cancel[sync]
Internal Procedures: handleResponse(r)
```

**rendering.md field mapping quick reference table**: rendering.md top adds concise mapping quick reference table (input/output/stat small tables), humans see overview from quick reference. Complete field attributes section follows for AI item-by-item mapping.

### Cross-File Trace Anchors (Optional)

When field counts increase or need cross-file renaming, can add 8-byte hex anchors to fields for explicit traceability. Anchors assigned at data contract (source), inherited by ViewSpec and generated code.

**Syntax**: anchor appended to field declaration, format `@<8hex>`.

```
Data Contract                    rendering.md output field        generated code
──────────────────               ──────────────────               ──────────────────
credit_score @a3f7b2c1           #### credit_score @a3f7b2c1      <!-- @a3f3b2c1 -->
                                                                 <div class="gauge">
```

`grep -r a3f7b2c1` locates all occurrences of same field in data contract, ViewSpec, generated code. Field renaming doesn't break chain.

**Applicable Granularity**: field level (input/output contract fields). Zones and events have stable identifiers via `zone_id` / `event_name`, no additional anchors needed.

---

## HOP Toolchain (Hoplet Application Scenario)

ViewSpec describes Hoplet's observation UI in HOP projects. Following commands and reference implementations are HOP-specific.

### Commands

| Command | Purpose | Direction |
|---------|---------|-----------|
| `/code2viewspec <task>` | metainfo + HopSpec → ViewSpec initial generation | contract → spec |
| `/code2view <task>` | ViewSpec + metainfo → View code | spec → code |
| `/view2spec <task>` | View code → ViewSpec reverse sync | code → spec |


```
metainfo.md + HopSpec.md
        |
  /code2viewspec --> ViewSpec/ <-> View/ (files)
  (initial generation)            |           ^
                        |           |
              /code2view --+  +-- /view2spec
              (forward generation) (reverse sync)
```

### Reference Implementation

Complete ViewSpec example can be found in `Tasks/VerifyFast/View/ViewSpec/` directory:
- `index.md` — Overview (Tab list + API adapter + common behavior + primitives + file routing table + file index)
- `rendering.md` — Rendering mapping (2 inputs + 2 outputs + composite components + normalization + 6 statistical metrics)
- `theme.md` — Layout theme (Light/Dark tokens + 23 layout dimensions + 26 CSS classes + 5 animations)
- `tabs/audit/` — Execute Tab (`_tab.md` + 2 Zone files: InputForm + ResultArea)
- `tabs/batch/` — Batch Tab (`_tab.md` + 1 Zone file: BatchPanel)
- `tabs/history/` — History Tab (`_tab.md` + 2 Zone files: FileList + DetailPane)
- `tabs/stats/` — Statistics Tab (`_tab.md` + Zone file)
- `tabs/perf/` — Performance Tab (`_tab.md` + Zone file)

### Related Documentation

- Data contract definition: `Tasks/<TaskName>/Hoplet/metainfo.md`
- Five-layer architecture specification: `Terms/HopletView架构规范_en.md`
- Execution logic specification: `Terms/HopSpec格式规范_en.md`
- `/code2viewspec` command specification: `.claude/commands/code2viewspec.md`
- `/code2view` command specification: `.claude/commands/code2view.md`
- `/view2spec` command specification: `.claude/commands/view2spec.md`

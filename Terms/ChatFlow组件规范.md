# ChatFlow 组件规范

> 交互式 Hoplet 的核心 UI 组件——对话流式多轮求解界面

> **与 ViewSpec 的关系**：本文档描述 ChatFlow 组件的**设计理念、数据流、状态机和实现细节**（Transport 层、Service 层、Frontend 层）。具体的 UI 交互声明（Zone 拆分、元素表、事件步骤序列、事件路由）遵循 `Terms/ViewSpec格式规范.md` 的 Zone-per-file 格式，声明在各任务的 `View/ViewSpec/tabs/<tab_id>/` 目录下。当本文档与 ViewSpec Zone 文件冲突时，以 ViewSpec 为准。

---

## 一、文件路由（关键）

ChatFlow 的代码分散在多个文件中。修改前必须确认改的是正确文件。

| 文件 | 角色 | 何时读取 |
|------|------|---------|
| `hoplogic/hop_view/templates/base.html` | **运行时 HTML + JS**。Jinja2 模板，启动时由 `build_index_html()` 一次性渲染为完整 HTML 页面。所有 JS 交互逻辑在此文件中。 | 每次 app 启动 |
| `hoplogic/hop_view/css_templates/chatflow.css` | **运行时 CSS**。`interactive=True` 时由 `html_builder._read_css()` 注入 `<style>` 标签。 | 每次 app 启动 |
| `hoplogic/hop_view/templates/fragments/run_result.html` | **HTML fragment 模板**。每次 API 调用由 `renderer.render_run_result()` 渲染，通过 SSE 推送到前端。 | 每次 API 请求 |
| `hoplogic/hop_view/html_builder.py` | 组装入口：读 CSS + 渲染 base.html → 完整页面字符串。 | 每次 app 启动 |
| `hoplogic/hop_view/transport.py` | FastAPI 端点定义（含 SSE 端点）。 | 每次 API 请求 |
| `Tasks/*/View/index.html` | `/code2view` 生成的**快照文件**。**不参与运行时**，仅供参考。 | 从不 |

**规则：修 JS → 改 `base.html`；修 CSS → 改 `chatflow.css`；修卡片结构 → 改 `fragments/run_result.html`。绝不改 `Tasks/*/View/index.html` 来修运行时行为。**

---

## 二、定位与概述

ChatFlow 是 HopletView 五层架构中 **Frontend 层的核心交互组件**，专为交互模式（`运行模式: 交互`）的 Hoplet 设计。它将引擎层的 `LACK_OF_INFO → 反馈 → 续解` 闭环映射为用户可见的对话流界面。

### Zone 拆分

| Zone | DOM ID | 职责 |
|------|--------|------|
| InputArea | `#solve-input-area` | 顶部输入表单（从 `config.input_fields` 自动生成），首次提交后收起（`.collapsed`） |
| ChatFlow | `#chat-flow` | 中部消息流：用户气泡、系统气泡（thinking / result cards），初始 `display:none` |
| ChatInputBar | `#chat-input-bar` | 底部反馈栏：反馈输入 + Send + Confirm，通过 `.visible` CSS 类控制显隐 |

### 架构位置

```
┌─────────────────────────────────────────────────────────────┐
│  base.html (Jinja2 渲染，启动时生成)                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Tab Bar: [solve] [batch] [history] [stats] [perf]      ││
│  ├─────────────────────────────────────────────────────────┤│
│  │  #solve-input-area           初始输入表单                ││
│  │  #chat-flow                  消息流                     ││
│  │    .msg.msg-user             用户气泡（右对齐）           ││
│  │    .msg.msg-system           系统气泡（左对齐）           ││
│  │      .thinking               等待中（步骤轮动 + 取消）    ││
│  │      .lack-info-card         信息不足                    ││
│  │      .error-card             错误（含重试）              ││
│  │      .result-card            OK 结果                    ││
│  │      .confirmed-card         用户确认                    ││
│  │      .info-card              系统提示（取消等）           ││
│  │  #chat-input-bar             底部反馈栏                  ││
│  └─────────────────────────────────────────────────────────┘│
│       │                                                      │
│       │  SSE: POST /api/run/init → GET /api/run/stream/{id}  │
│       │  SSE: POST /api/feedback/init → GET /api/feedback/... │
└───────┼──────────────────────────────────────────────────────┘
        │
   transport.py (FastAPI 端点 + SSE 队列)
        │
   BaseService (hop_view.service)     ← session 管理
        │  ._sessions[session_id]
        │  ._session_inputs[session_id]
        │  ._session_iterations[session_id]
        │
   main_hop_func (Hoplet)             ← 业务逻辑
        │
   HopSession.hop_get()               ← 算子调用
        │  返回 (HopStatus, result)
```

### 与批量模式的关系

| 维度 | 交互模式（ChatFlow） | 批量模式（Batch） |
|------|---------------------|------------------|
| 传输 | SSE 两步流（init + stream） | 同步 `POST /api/run` |
| 非 OK 处理 | 显示反馈区，等待用户输入 | 直接记录结果 |
| Session | 跨多轮保活 | 单次执行后释放 |
| 取消支持 | 有（SSE 连接可关闭） | 有（批量可中止） |

---

## 三、传输层：SSE 两步流

### 为什么用 SSE

WKWebView（macOS pywebview 内核）对 HTTP 请求有内置超时。LLM 调用可能耗时数十秒，阻塞式 `fetch` 会被杀死报 "Load failed"。

SSE（Server-Sent Events）解决方案：
1. `POST /api/run/init` 立即返回 `{stream_id}`（毫秒级，不超时）
2. `GET /api/run/stream/{id}` 建立 `EventSource` 长连接
3. 服务端每 5 秒发送 `: ping N\n\n` keep-alive（SSE 注释帧，浏览器忽略但连接保活）
4. LLM 完成后推送 `data: {...}\n\n` 结果事件
5. 前端收到结果后关闭 EventSource

使用原生 `EventSource` API（不是 `fetch + ReadableStream`），因为 WKWebView 对 SSE 连接不施加 HTTP 超时。

### 协议时序

```
Client                                  Server
  │                                       │
  │── POST /api/run/init ────────────────>│ body: {task_description, context}
  │<─ 200 {"stream_id":"uuid"} ──────────│ 立即返回，后台启动 asyncio.Task
  │                                       │
  │── GET /api/run/stream/{id} ─────────>│ EventSource 连接
  │<─ ": ping 1\n\n" ───────────────────│ 5s 无数据
  │<─ ": ping 2\n\n" ───────────────────│ 10s 无数据
  │<─ "data: {json}\n\n" ───────────────│ LLM 完成
  │   EventSource.close()                │ 客户端关闭
  │                                       │ 清理 _pending_streams[id]
```

### SSE 结果消息格式

```json
{
  "type": "result",
  "html": "<div class='lack-info-card' data-hop-status='LACK_OF_INFO' data-session-id='uuid'>...</div>",
  "session_id": "uuid-or-empty",
  "hop_status": "OK|FAIL|LACK_OF_INFO|UNCERTAIN"
}
```

- `html`：Jinja2 渲染的 HTML fragment（`run_result.html`），直接插入 DOM
- `session_id`：Service 层分配的会话 ID，前端据此维护 `_sessionId`
- `hop_status`：用于前端状态分支（显示/隐藏 chat input）

### 服务端实现（transport.py）

```python
_pending_streams: dict[str, asyncio.Queue[str | None]] = {}

@app.post("/api/run/init")
async def init_run_stream(req: RunTaskRequest) -> JSONResponse:
    stream_id = str(uuid4())
    queue = asyncio.Queue()
    _pending_streams[stream_id] = queue
    asyncio.create_task(_run(queue, req))       # 后台执行
    return JSONResponse({"stream_id": stream_id})  # 立即返回

@app.get("/api/run/stream/{stream_id}")
async def stream_run_result(stream_id: str):
    queue = _pending_streams[stream_id]         # 404 if missing
    async def _events():
        while True:
            data = await wait_for(queue.get(), timeout=5.0)
            # TimeoutError → yield ": ping N\n\n"
            # None sentinel → break
            # else → yield f"data: {data}\n\n"
    return StreamingResponse(_events(), media_type="text/event-stream")
```

反馈端点 `/api/feedback/init` + `/api/feedback/stream/{id}` 结构完全相同。

### 向后兼容

旧端点 `POST /api/run` 和 `POST /api/feedback` 仍存在，非交互视图（HTMX 表单模式）继续使用。ChatFlow 专用 SSE 端点。

---

## 四、状态机

### 状态转换图

```
                        ┌──────────┐
                        │ INITIAL  │  InputArea 可见, ChatFlow 隐藏
                        └────┬─────┘
                             │ onSendTask()
                             ▼
                        ┌──────────┐
              ┌────────>│ THINKING │<──────────────────────┐
              │         └────┬─────┘ SSE stream pending    │
              │              │                             │
              │    ┌─────────┼──────────┐                  │
              │    │    hop_status?     │                  │
              │    ▼         ▼          ▼                  │
              │   OK    LACK_OF_INFO  FAIL/error           │
              │   │     UNCERTAIN       │                  │
              │   │         │           │                  │
              │   ▼         ▼           ▼                  │
              │ ┌────┐  ┌──────────┐  ┌───────┐           │
              │ │DONE│  │AWAITING  │  │ ERROR │           │
              │ └────┘  │FEEDBACK  │  └───┬───┘           │
              │ 终态    └────┬─────┘      │ onRetryTask() │
              │              │             └───────────────┘
              │              │ onSubmitFeedback()
              │              │ onConfirm()
              │              └─────────────────────────────┘
              │
              │         ─── onCancelTask() ───
              │         (可在 THINKING 状态触发)
              │              │
              │    ┌─────────┴──────────┐
              │    │ _sessionId set?    │
              │    ▼                    ▼
              │ ┌────────────┐  ┌─────────────────┐
              │ │ CANCELLED  │  │ CANCELLED       │
              │ │ (feedback) │  │ (initial run)   │
              │ │ chat input │  │ retry button    │
              │ │ visible    │  │ chat input      │
              │ └──────┬─────┘  │ hidden          │
              │        │        └────────┬────────┘
              │        │ onSubmitFeedback │ onRetryTask()
              └────────┴─────────────────┘
```

### HopStatus 到 UI 映射

| hop_status | 消息卡片 | chat input | `_sessionId` | 可继续 |
|------------|---------|------------|--------------|--------|
| `OK` | `.result-card` | hidden | 清为 null | 否 |
| `CONFIRMED` | `.confirmed-card` | hidden | 清为 null | 否 |
| `LACK_OF_INFO` | `.lack-info-card` | **visible** | 从 SSE 设置 | 是（feedback） |
| `UNCERTAIN` | `.lack-info-card` | **visible** | 从 SSE 设置 | 是（feedback/confirm） |
| `FAIL` | `.error-card`（含重试） | hidden | **保留** | 是（retry） |
| (传输异常) | 内联 `.error-card`（含重试） | visible | 不变 | 是（retry） |
| `CANCELLED` | `.info-card` | hidden | 清为 null | 否 |

**关键区分**：
- **FAIL vs 传输异常**：FAIL 来自引擎层（核验失败/能力不足），传输异常来自 SSE 连接中断。两者都显示 error card + 重试按钮，但 FAIL 时 `_sessionId` 保留，传输异常时 `_sessionId` 不变。
- **LACK_OF_INFO vs UNCERTAIN**：LACK_OF_INFO 缺少关键信息，UNCERTAIN 方案已生成但不确定。两者都允许 feedback，UNCERTAIN 额外显示 Confirm 按钮。

### 取消的两种场景

这是最易出错的状态转换，必须严格区分：

| 场景 | 条件 | UI 行为 | 用户后续操作 |
|------|------|---------|-------------|
| 取消初始运行 | `_sessionId === null` | info card + "重试" 按钮 | 点击重试 → `onRetryTask()` |
| 取消反馈循环 | `_sessionId !== null` | info card + chat input 可见 | 重新输入 → `onSubmitFeedback()` |

**为什么不同**：初始运行取消时 `_sessionId` 还未设置（UNCERTAIN 结果未到达），`onSubmitFeedback` 有 `if (!text || !_sessionId) return` 守卫，显示 chat input 会导致用户输入后 Send 无响应（silent no-op）。

---

## 五、前端状态变量

```javascript
// ── 会话状态 ──
let _sessionId = null;            // 当前 session ID（来自 SSE result.session_id）
let _feedbackRound = 0;           // 反馈轮次（仅用于 > MAX_FEEDBACK 判断）
let _conversationActive = false;  // 对话是否激活
let _lastResult = null;           // 最近一次结果（用于 confirm）

// ── SSE 流控制 ──
let _cancelled = false;           // 用户是否已取消当前操作
let _currentStream = null;        // 当前 EventSource 实例（取消时关闭）
let _lastAction = null;           // {initUrl, body, summary?} — onRetryTask() 重放用

// ── Thinking 动画 ──
let _thinkingTimer = null;        // setInterval ID（步骤轮动 8s/step）
let _thinkingStep = 0;            // 当前步骤索引

// ── 重试配额 ──
let _retryCount = 0;              // 已重试次数

// ── 常量（Jinja2 注入） ──
const _HOP_THINKING_STEPS = [...];  // 步骤标签列表
const _HOP_RETRY_QUOTA = Infinity;  // 最大重试次数
const MAX_FEEDBACK = 5;              // 最大反馈轮次
```

### `_lastAction` 设计

`_lastAction` 在每次 SSE 调用前设置，记录请求参数：

```javascript
// onSendTask 中：
_lastAction = {initUrl: "/api/run/init", body: {task_description, context}, summary: "..."};

// onSubmitFeedback 中：
_lastAction = {initUrl: "/api/feedback/init", body: {session_id, feedback}};
```

`onRetryTask()` 直接复用 `_lastAction.initUrl` 和 `_lastAction.body` 重走 SSE 流，无需区分是 run 还是 feedback 的重试。

### Server-Authoritative State 规则

- 显示值来自服务端响应，不用前端计数器（`_feedbackRound` 仅控制流）
- `_sessionId` 唯一来源是 SSE `msg.session_id`
- `hop_status` 唯一来源是 SSE `msg.hop_status`

---

## 六、核心事件

### onSendTask()（首次提交）

```
1. 校验: 至少一个 input_field 非空
2. 构建 body: {field_name: value, ...}
3. 收起输入区: #solve-input-area.classList.add("collapsed")
4. 显示消息流: #chat-flow.style.display = "flex"
5. 追加用户气泡: desc[0].slice(0,100) + " | " + desc[1].slice(0,50)
6. 追加 thinking 气泡（含步骤轮动 + 取消按钮）
7. 设置 _lastAction = {initUrl: "/api/run/init", body, summary}
8. SSE Phase 1: POST /api/run/init → {stream_id}
   - 失败: removeThinking → error card（含重试） → showChatInput
9. SSE Phase 2: EventSource("/api/run/stream/" + streamId)
   - onmessage(result): 见「SSE 结果处理」
   - onerror: removeThinking → error card（含重试） → showChatInput
```

### onSubmitFeedback()（反馈提交）

```
1. 守卫: if (!text || !_sessionId) return     ← 关键: _sessionId 必须已设置
2. 清空输入框, _feedbackRound++
3. 追加用户气泡(text)
4. 追加 thinking 气泡
5. 设置 _lastAction = {initUrl: "/api/feedback/init", body: {session_id, feedback}}
6. SSE Phase 1: POST /api/feedback/init → {stream_id}
7. SSE Phase 2: EventSource("/api/feedback/stream/" + streamId)
   - 处理同 onSendTask
```

### onCancelTask()（取消）

```
1. _cancelled = true
2. if (_currentStream) { _currentStream.close(); _currentStream = null; }
3. removeLastThinking()
4. if (_sessionId) {
     // ── 反馈循环取消: session 有效，用户可重新输入 ──
     appendSystemHtml: info-card "Cancelled. You can revise and resubmit."
     showChatInput()
     POST /api/cancel {session_id}   // 通知服务端取消后台 task
     // 保留 _sessionId（session 状态仍有效）
   } else {
     // ── 初始运行取消: session 未建立，只能重试 ──
     appendSystemHtml: info-card "Cancelled." + 重试按钮
     // 不显示 chat input（_sessionId 为 null，onSubmitFeedback 会 silent return）
   }
5. scrollToBottom()
```

### onRetryTask()（重试）

```
1. 守卫: if (!_lastAction) return
2. _cancelled = false
3. 追加 thinking 气泡
4. SSE Phase 1: POST _lastAction.initUrl → {stream_id}
5. SSE Phase 2: EventSource(_lastAction.initUrl.replace("/init", "/stream/") + streamId)
   - 处理同 onSendTask
```

重试不区分是 run 还是 feedback，直接重放 `_lastAction`。

### onConfirm()（确认方案）

```
1. 守卫: if (!_sessionId) return
2. 调用 onSubmitFeedbackWithText("confirm")
   → 等效于用户输入 "confirm" 并 Submit
```

### SSE 结果处理（三个事件共用逻辑）

```javascript
es.onmessage = e => {
  const msg = JSON.parse(e.data);
  if (msg.type === "result") {
    streamDone = true;
    es.close(); _currentStream = null;
    if (_cancelled) return;              // 已取消，丢弃延迟结果
    removeLastThinking();
    if (msg.session_id) _sessionId = msg.session_id;
    appendSystemHtml(msg.html);          // 插入 HTML + 扫描 data-* 属性
    if (hopStatus is UNCERTAIN/LACK_OF_INFO) → showChatInput();
    else → hideChatInput(); if (not FAIL) _sessionId = null;
  }
};
```

### appendSystemHtml() 的 data-attribute 扫描

HTML fragment 由 Jinja2 服务端渲染，通过 `data-*` 属性携带状态信息：

```html
<div class="lack-info-card"
     data-hop-status="LACK_OF_INFO"
     data-session-id="uuid">
  ...
</div>
```

`appendSystemHtml()` 插入 HTML 后扫描 `[data-hop-status]`：
- 提取 `data-session-id` → 设置 `_sessionId`
- `UNCERTAIN | LACK_OF_INFO` → `showChatInput()`
- `OK | CONFIRMED | CANCELLED` → `hideChatInput()` + `_sessionId = null`

**为什么用 data-attribute**：`insertAdjacentHTML` 插入的 `<script>` 标签不会执行（HTML spec）。data-attribute 是唯一可靠的服务端→前端状态通道。

---

## 七、消息卡片渲染

所有卡片由 `fragments/run_result.html` Jinja2 模板服务端渲染，前端通过 `appendSystemHtml()` 插入。

### run_result.html 分支逻辑

```
if error and no hop_status:
  → .error-card + ERROR badge + 重试按钮

elif CANCELLED:
  → .info-card "Task cancelled."

elif LACK_OF_INFO / UNCERTAIN:
  → .lack-info-card + badge + clarification list + summary + chart + Raw JSON

elif FAIL:
  → .error-card + FAIL badge + 重试按钮

else (OK / CONFIRMED):
  → .result-card (.confirmed-card if CONFIRMED) + badge + gauge + summary + errors + chart + Raw JSON
```

### thinking 气泡

```
.thinking-msg
  .system-bubble
    .thinking
      .thinking-summary        ← 任务摘要（可选）
      .thinking-steps          ← 滑动窗口（最多 3 步）
        .thinking-step.completed  ← 前一步: ✓
        .thinking-step.active     ← 当前步: spinner
        .thinking-step.pending    ← 下一步: ○
      button.btn-stop          ← 取消按钮 ■
```

**步骤轮动**：8 秒/步，滑动窗口最多 3 步可见。到达最后一步后停止。`removeLastThinking()` 清除 timer + 移除 DOM。

### CSS 关键约束

- `.msg-bubble` 默认 `white-space: pre-wrap`（用户气泡保留换行）
- `.system-bubble` 覆盖为 `white-space: normal`（避免 Jinja2 模板缩进渲染为可见空白）
- `.chat-input-bar` 默认 `display: none`，`.visible` 类切换为 `display: flex`

---

## 八、Service 层

Session 管理由 `hop_view.service.BaseService` 统一提供。

### 使用方式

```python
service = BaseService(VIEW_CONFIG, HOPLET_DIR, TESTCASES_DIR,
    observer=HopletObserver(OBSERVER_LOG))

result = await service.run_task(input_data)
# → {"session_id": "uuid", "hop_status": "OK|FAIL|LACK_OF_INFO|UNCERTAIN", "iteration": 1, ...}

result = await service.submit_feedback(session_id, feedback)
result = await service.retry_task(session_id)
result = await service.cancel_task(session_id)
```

### Session 生命周期

```
run_task()
  ├── OK         → session.__aexit__() → 完全释放
  ├── FAIL       → session.__aexit__() → 释放 session，保留 input/iterations
  └── LACK_OF_INFO/UNCERTAIN → session 保活
        │
        └── submit_feedback()
              ├── OK/CONFIRMED → session.__aexit__() → 完全释放
              ├── FAIL         → session.__aexit__() → 释放 session，保留 input/iterations
              └── LACK_OF_INFO/UNCERTAIN → 保活，继续循环

retry_task(session_id)
  └── 读取保留的 input_data → 创建新 session → 执行

cancel_task(session_id)
  └── task.cancel() → session.__aexit__() → 释放
```

### FAIL 后 session 保留策略

| 字段 | FAIL 时行为 | 说明 |
|------|------------|------|
| `_sessions` | 清理 | context 已释放 |
| `_session_inputs` | **保留** | 重试时需要 |
| `_session_iterations` | **保留** | 重试时 iteration 继续递增 |
| `_session_errors` | 记录 | 跟踪重试次数 |
| `_running_tasks` | 清理 | task 已完成 |

### Engine 层 API

```python
class HopSession:
    def add_feedback(self, feedback: str) -> None:
        """将 feedback 追加到 run_history 作为 user 消息"""
        self.append_run_message("user", feedback)
```

反馈注入后 LLM 看到: `[user: task, assistant: 前次结果, user: feedback, ...]`。

---

## 九、API 端点

### SSE 端点（ChatFlow 专用）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/run/init` | POST | 启动任务，立即返回 `{stream_id}` |
| `/api/run/stream/{id}` | GET | SSE 流：ping keep-alive + result 事件 |
| `/api/feedback/init` | POST | 启动反馈，立即返回 `{stream_id}` |
| `/api/feedback/stream/{id}` | GET | SSE 流：同上 |

### 同步端点（非交互视图/向后兼容）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/run` | POST | 阻塞执行，返回 HTML fragment |
| `/api/feedback` | POST | 阻塞反馈，返回 HTML fragment |
| `/api/retry` | POST | 重试，返回 HTML fragment |
| `/api/cancel` | POST | 取消，返回 JSON |

---

## 十、设计约束

### 10.1 FAIL vs LACK_OF_INFO 边界

`add_feedback` 只影响 LLM 对话历史，无法修复管线层问题。

| 失败来源 | 正确 status | 可 feedback 续解 |
|----------|-----------|-----------------|
| 前置管线失败（RAG/数据源） | FAIL | 否 |
| 传输失败/核验失败 | FAIL | 否 |
| LLM 报告缺少信息 | LACK_OF_INFO | 是 |
| LLM 报告不确定 | UNCERTAIN | 是 |

**Hop.py 作者规则**：管线失败 → 返回 FAIL（调 `hop_exit`），不要返回 LACK_OF_INFO。

### 10.2 pywebview 环境约束

- **统一 HTTP**：pywebview 通过内嵌 uvicorn 访问同一 FastAPI app
- **文本可选**：全局 `* { user-select: text }`
- **Error Overlay**：`#error-overlay` 捕获 `window.error` + `unhandledrejection`
- **SSE 不超时**：WKWebView 不对 `EventSource` 连接施加 HTTP 超时（解决 "Load failed"）

### 10.3 白空间陷阱

`.msg-bubble` 默认 `white-space: pre-wrap`，用于保留用户输入的换行。但 Jinja2 模板缩进也会被渲染为可见空白行。解决：`.system-bubble { white-space: normal; }` 覆盖。

新增系统气泡样式时注意这一点。

### 10.4 `insertAdjacentHTML` 的 script 限制

HTML spec 规定 `insertAdjacentHTML` 插入的 `<script>` 标签不执行。服务端渲染的 HTML fragment 不能依赖内联 script，必须用 `data-*` 属性传递状态，由 `appendSystemHtml()` 统一扫描处理。

### 10.5 常见陷阱（实战经验）

以下是 ChatFlow 首次集成时遇到的典型问题，列为永久设计约束。

#### 陷阱 1：任务级 ViewSpec 与共享组件 ViewSpec 失步

**症状**：AI 按任务 ViewSpec 生成的代码调用不存在的同步端点（如 `POST /api/run`），运行时 404。
**根因**：共享 ChatFlow ViewSpec（`hoplogic/hop_view/chatflow/ViewSpec/`）已切换到 Two-Phase SSE 协议，但任务级 ViewSpec（`Tasks/*/View/ViewSpec/tabs/solve/`）仍描述旧的同步 HTTP 端点。AI 按任务 ViewSpec 生成代码，与实际运行时不一致。
**规则**：任务级 ViewSpec 的 ChatFlow/ChatInputBar Zone 文件**必须引用共享 ViewSpec**，仅描述定制点（thinking_steps、handleResponse 分支细节、placeholder 映射等），不得重复协议细节。格式：

```markdown
> 共享实现: [`hoplogic/hop_view/chatflow/ViewSpec/zones/ChatFlow.md`](...)
> 本文件仅描述定制点。通用行为见共享 ViewSpec。
```

#### 陷阱 2：模板字段查找链不完备

**症状**：LACK_OF_INFO 卡片的澄清列表为空，尽管 Hop.py 返回了 `clarification_needed` 字段。
**根因**：`run_result.html` 的字段查找链 `clarification_questions || missing_info` 遗漏了 `clarification_needed`。不同 Hoplet 对同一语义使用不同字段名。
**规则**：`run_result.html` 的每个查找链必须覆盖已知的所有字段别名。新增 Hoplet 时，如果输出字段名不在现有查找链中，必须同步更新模板。当前完整查找链：

| 语义 | 查找链 |
|------|--------|
| 澄清列表 | `clarification_questions` → `clarification_needed` → `missing_info` |
| 摘要文本 | `answer` → `summary` → `verification_summary` → `presentation` → `problem_summary` |

#### 陷阱 3：Hop.py 的 HopStatus 分支遗漏

**症状**：`generate_solution` 步骤返回 LACK_OF_INFO 时，UI 显示 `"方案生成失败: {}"`。
**根因**：Hop.py 中只有 `analyze_problem` 步骤有 LACK_OF_INFO 专门处理，`generate_solution` 步骤的 LACK_OF_INFO 落入通用 `status != OK` 分支，被格式化为 error 字符串。
**规则**：交互模式 Hop.py 中，**每个可能返回 LACK_OF_INFO/UNCERTAIN 的算子调用都必须有对应的专门处理分支**，不能依赖通用 error 兜底。checklist：
- [ ] 每个 `hop_get`/`hop_judge` 调用后检查是否有 `if status == HopStatus.LACK_OF_INFO:` 分支
- [ ] LACK_OF_INFO 分支构造的输出 dict 必须包含 `clarification_needed` 列表（非空）
- [ ] UNCERTAIN 分支构造的输出 dict 必须包含 `presentation` 或 `summary`

#### 陷阱 4：改错文件（快照 vs 运行时模板）

**症状**：修改 `Tasks/*/View/index.html` 后 UI 无变化。
**根因**：`index.html` 是 `/code2view` 生成的静态快照，运行时由 `base.html` + `chatflow.css` + `run_result.html` 动态渲染。
**规则**：见 §一 文件路由表。任务 ViewSpec 的 `index.md` 中推荐包含文件路由表（见 `Terms/ViewSpec格式规范.md` §1.7）。

#### 陷阱 5：协程事件缺少 Guard 声明

**症状**：Start 按钮可被连续点击，导致多个 SSE 流并发写入同一个 `#chat-flow` 容器，消息交叉错乱。
**根因**：ViewSpec ChatFlow.md 的 `task_submit` 事件未声明 `guard: _conversationActive, .btn-send`，代码生成/人工实现时遗漏了重入守卫。
**规则**：ViewSpec 中每个 `[coroutine]` 事件**必须显式声明三类守卫**（状态变量守卫、元素守卫、事件互斥守卫），且必须声明恢复函数（如 `_unlockSend()`）。所有终态路径（OK/FAIL/CONFIRMED/error/cancel）必须调用恢复函数。checklist：
- [ ] 每个 `[coroutine]` 事件有 `> guard:` 行
- [ ] guard 包含状态变量（防重入）、触发按钮（UI 反馈）、互斥事件
- [ ] 声明恢复函数名，且所有终态路径都调用
- [ ] `test_html_builder.py` 有对应的约束测试

#### 陷阱 6：Service 层关键词匹配缺少 i18n 覆盖

**症状**：用户输入"确认"后系统将其作为普通 feedback 提交给 LLM，返回不相干的回答（答非所问）。
**根因**：`BaseService._is_confirmation()` 只识别英文 "confirm"/"ok"，遗漏中文 "确认"/"好的"/"可以" 等常用确认词。
**规则**：Service 层任何涉及字符串匹配/关键词识别的逻辑，必须在代码中将关键词声明为显式常量元组（如 `_CONFIRM_PREFIXES`），且必须覆盖中英文。checklist：
- [ ] 关键词声明为模块级或类级常量（非内联字面量）
- [ ] 常量注释中列出所有支持的语言
- [ ] 有参数化测试覆盖所有关键词（`@pytest.mark.parametrize`）
- [ ] 新增语言时只需扩展常量元组 + 添加 parametrize 用例

---

## 十一、测试覆盖

### Transport 测试（test_transport.py）

| 测试 | 覆盖点 |
|------|--------|
| `test_init_run_stream_returns_stream_id` | POST /api/run/init 返回 stream_id |
| `test_stream_delivers_result_event` | GET /api/run/stream/{id} 推送 result |
| `test_stream_unknown_id_returns_404` | 未知 stream_id 返回 404 |
| `test_init_feedback_stream_returns_stream_id` | POST /api/feedback/init |
| `test_feedback_stream_delivers_result` | GET /api/feedback/stream/{id} |

### Frontend 静态检查（test_web.py）

| 测试 | 覆盖点 |
|------|--------|
| `test_global_user_select_text` | `*` 选择器启用文本选中 |
| `test_error_overlay_exists` | error-overlay 元素存在 |

### Service 测试（test_service.py）

| 测试 | 覆盖点 |
|------|--------|
| `test_post_run` | 正常执行 |
| `test_post_feedback` | 反馈提交 |
| `test_feedback_loop` | 多轮 iteration 递增 |

---

## 十二、扩展点

- **LLM Streaming**：在 SSE 结果到达前，流式推送 LLM 生成的文本片段（需要引擎层 callback）
- **Session 超时回收**：长时间未 feedback 的 session 自动释放
- **多任务并发**：左侧会话列表 + 右侧对话流
- **历史回放**：对话消息持久化为 JSONL

---

## 十四、可观测性

### 14.1 Frontend Debug Log

ChatFlow 运行时状态对 Claude Code 默认不可见（JS 内存中的状态变量、UI error overlay 8 秒消失）。Frontend Debug Log 机制解决此问题。

#### 两层设计

| 层 | 触发条件 | 写入文件 | 用途 |
|----|---------|---------|------|
| 错误持久化 | 始终生效 | `TestCases/frontend-debug.jsonl` | 前端错误（JS 异常、网络失败）POST 到后端写 JSONL |
| 状态变更 debug log | `HOP_VIEW_DEBUG=1` 或 `--debug` | `TestCases/frontend-debug.jsonl` | 关键状态变量每次变更记录到 JSONL + UI debug 面板 |

#### 启用方式

```bash
HOP_VIEW_DEBUG=1 uv run view <TaskName>
```

#### 日志格式（JSONL）

```json
{"ts": "2026-01-15T10:30:00.123Z", "level": "state", "message": "_sessionId = 'uuid-xxx' (from SSE)", "context": null}
{"ts": "2026-01-15T10:30:01.456Z", "level": "error", "message": "HTTP 500", "context": null}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts` | string | ISO 8601 时间戳 |
| `level` | string | `"error"` / `"state"` / `"event"` / `"warn"` |
| `message` | string | 人类可读描述 |
| `context` | object \| null | 可选上下文数据 |

#### 状态变量埋点

以下 5 个状态变量的所有变更点均有 `_hopLog("state", ...)` 调用：

- `_sessionId` — 4 处（appendSystemHtml 设置/清空、_handleResult 设置/清空）
- `_conversationActive` — 2 处（onSendTask 设 true、_unlockSend 设 false）
- `_cancelled` — 4 处（onSendTask/onSubmitFeedback/onRetryTask 重置、onCancelTask 设 true）
- `_feedbackRound` — 1 处（onSubmitFeedback 递增）
- `_currentStream` — 4 处（_openStream 设置、_handleResult/handleStreamError/onCancelTask 清空）

#### 规则

新增 coroutine 事件时，**必须同步添加状态变更 `_hopLog` 调用**。checklist：
- [ ] 事件入口有 `_hopLog("event", "event: <name>")` 调用
- [ ] guard 拦截时有 `_hopLog("event", "event: <name> BLOCKED (...)")` 调用
- [ ] 每个状态变量变更处有 `_hopLog("state", "<var> = <value> (<caller>)")` 调用

#### 日志文件生命周期

`frontend-debug.jsonl` 不在 View 重启时自动清空，便于 Claude Code 事后分析。手动清理：
```bash
rm Tasks/<TaskName>/TestCases/frontend-debug.jsonl
```

---

## 十五、与其他规范的关系

| 规范 | 关系 |
|------|------|
| `Terms/HopletView架构规范.md` | ChatFlow 是五层架构中 Frontend 层的交互组件 |
| `Terms/ViewSpec格式规范.md` | ChatFlow 布局类型 `chat-flow` 在 ViewSpec tabs/*.md 中声明 |
| `Terms/HopView共享库规范.md` | BaseService session 管理详细 API |
| `hoplogic/docs/hop_feedback_solving.md` | 引擎层反馈续解机制 |
| `Terms/HOP核心算子.md` | HopStatus 枚举驱动状态转换 |
| `.claude/commands/code2view.md` | `/code2view` 检测运行模式，交互模式生成 ChatFlow |

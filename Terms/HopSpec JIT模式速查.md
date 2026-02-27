# HopSpec JIT模式速查（LLM 生成参考）

> JIT 模式下 `loop` 支持 **for-each**（遍历集合）和 **while**（条件循环，须设置 `max_iterations > 0`，引擎自动注入迭代上限防护）。step_name 可省略。

## 核心规则

- 执行流程是**结构化树**：顺序执行、禁止跳转、嵌套表达
- `loop`/`branch` 完成后自动落到下一个同级步骤，不声明跳转
- 步骤标题：`#### 步骤N: step_name`（step_name 可省略，省略时自动生成），step\_name 为 snake\_case 英文（2-4词），Spec 内唯一

## 6 种原子类型

| 类型       | 含义                        | 节点性质 |
| -------- | ------------------------- | ---- |
| `LLM`    | LLM 执行（带核验）               | 叶子   |
| `call`   | 外部调用（工具/Hoplet/MCP）       | 叶子   |
| `loop`   | 遍历集合（for-each），子步骤缩进内嵌    | 容器   |
| `branch` | 条件分支，子步骤缩进内嵌              | 容器   |
| `code`   | 纯 Python 计算（无 LLM）        | 叶子   |
| `flow`   | 流程控制（exit/continue/break） | 叶子   |

**类型选择**：LLM 任务用 `LLM`，纯计算用 `code`，外部调用用 `call`。`LLM` 内部 get/judge 区分由 AI 从任务描述推断，Spec 层不区分。

## 节点属性速查

### LLM

```markdown
#### 步骤N: step_name
- 类型：LLM
- 任务：<LLM 任务描述>
- 输入：<变量名列表>
- 输出：<变量名>
- 输出格式：<JSON结构>          # 可选
- 核验：逆向/正向交叉/无        # 可选，默认逆向
- 说明：<执行要点>              # 可选
```

### call

```markdown
#### 步骤N: step_name
- 类型：call
- 调用目标：tool/hoplet/mcp    # 必选
- 任务：<调用目标描述>
- 输入：<变量名列表>
- 输出：<变量名>
- 工具域：<域标识>              # tool 时必选
- Hoplet路径：<路径>            # hoplet 时必选
- MCP服务：<服务标识>           # mcp 时必选
```

### loop（仅 for-each）

```markdown
#### 步骤N: step_name（loop）
- 类型：loop
- 遍历集合：<集合变量名>
- 元素变量：<循环变量名>
- 输出：<结果集合变量名>        # 可选

  #### 步骤N.1: child_step
  - 类型：...
```

### branch

```markdown
#### 步骤N: step_name（branch）
- 类型：branch
- 条件：<Python布尔表达式>

  #### 步骤N.1: child_step
  - 类型：...
```

多条件用顺序 branch（if A → if B），不用 else。

### code

```markdown
#### 步骤N: step_name
- 类型：code
- 逻辑：<自然语言计算描述>
- 输入：<变量名列表>
- 输出：<变量名>
```

### flow

```markdown
#### 步骤N: step_name          # exit：终止流程
- 类型：flow
- 动作：exit
- 输出：<返回变量名>
- 退出标识：<EXIT_ID>          # 可选

#### 步骤N: step_name          # continue/break：必须在 loop 内
- 类型：flow
- 动作：continue/break
- 目标循环：<所在 loop 的 step_name>
```

## 书写约定

- 属性名用**中文**，变量名用**英文 snake\_case**
- 输入列表逗号分隔：`输入：context, claim`
- 输出格式用 JSON Schema 风格：`{"claims": List[str]}`
- 条件用 Python 语法：`条件：status == "FAIL"`
- 核验省略时用默认值（LLM 默认逆向），写 `核验：无` 显式跳过
- step_name 可省略（省略时引擎自动生成 `stepN` 形式名称）

## 文档结构

```markdown
## 任务概述
<一句话目标>

## 输入定义
- `var`: 说明

## 硬性约束
- <不可违反的规则>

## 执行流程
#### 步骤1: ...
...
#### 步骤N: output
- 类型：flow
- 动作：exit
- 输出：final_result

## 输出格式
<JSON结构描述>

## 输入日志示例
<示例JSON>
```

## 紧凑示例

```
步骤1: extract_facts        LLM     → atomic_claims
步骤2: check_grounding      loop(atomic_claims → claim)
 └ 步骤2.1: judge_source    LLM     → verdict → grounding_errors
步骤3: check_logic          LLM     → logic_errors
步骤4: check_consistency    LLM     → is_consistent
步骤5: handle_inconsistency branch(is_consistent == False)
 └ 步骤5.1: list_conflicts  LLM     → consistency_errors
步骤6: merge_errors         code    → all_errors
步骤7: score_reliability    LLM     → report
步骤8: assemble_report      code    → final_report
步骤9: output_report        flow:exit → final_report
```

# HopLib 技能库规范

HopLib 是 HOP 项目的跨任务复用技能库。与 Tasks/ 下的 Hoplet 不同，HopLib 条目是经过验证的通用能力单元，可被多个任务通过 `call` 步骤或 `SkillRegistry` API 引用。

> 本文档定义 HopLib 的目录约定、签名约定、质量门槛和引用方式。`SkillRegistry` 和 `HopSkill Protocol` 的 API 细节见 `hoplogic/docs/hop_skill.md`。

## 目录约定

```
HopLib/
  <name>/
    metainfo.md        # 元数据契约（必须）
    Hop.py             # 可执行技能代码（必须）
    SKILL.md           # AgentSkills.io 互操作描述（/spec2code 生成）
    test/              # 单元测试目录（必须）
      __init__.py
      test_<name>.py
    TestCases/         # 批量测试数据（推荐）
      test_cases.jsonl
```

- `<name>` 为技能名称，与 `metainfo.md` 中的 `名称` 字段一致（如 `OCR`、`WebSearch`、`Chart`）。
- `SKILL.md` 由 `generate_skill_md(parse_metainfo(metainfo_path))` 从 `metainfo.md` 生成。

## 与 Task Hoplet 的区别

| 维度 | Task Hoplet (`Tasks/<name>/Hoplet/`) | HopLib (`HopLib/<name>/`) |
|------|---------------------------------------|--------------------------|
| 定位 | 面向特定业务任务 | 跨任务复用的通用能力 |
| 扫描优先级 | 低（SkillRegistry 后扫描） | 高（SkillRegistry 先扫描） |
| 同名冲突 | 被 HopLib 覆盖 | 胜出 |
| hop_engine 依赖 | 通常依赖 | 不依赖（保持独立性） |
| source_type | `"hoplet"` | `"hoplib"` |

`SkillRegistry` 的扫描顺序为 HopLib > Tasks > External，同名条目由先发现者胜出。

## 签名约定

HopLib 技能函数遵循以下签名：

```python
async def hop_<name>(session, input_data: dict) -> tuple[str, dict]:
    """
    Args:
        session: HopSession 实例（可为 None，当技能不需要 LLM 时）
        input_data: 符合 metainfo.md 输入契约的字典

    Returns:
        (status, result) 元组
        - status: "OK" 或 "FAIL" 字符串（使用模块常量 _OK/_FAIL）
        - result: 符合 metainfo.md 输出契约的字典
    """
```

关键约束：
- **不导入 hop_engine**：使用 `_OK = "OK"` / `_FAIL = "FAIL"` 字符串常量代替 `HopStatus` 枚举
- **HopletAdapter 自动转换**：`_normalize_result()` 会将字符串状态强转为 `HopStatus`
- **函数名包含 "hop"**：`_detect_hop_func()` 按名称搜索，函数名中必须包含 "hop"（大小写不敏感）

## 依赖隔离

HopLib 条目的依赖必须局限于自身，不扩展到 hoplogic：

- 不导入 `hop_engine`、`hop_mcp`、`hop_rag` 等 hoplogic 子包
- 需要 LLM 能力时通过 `session` 参数间接使用（由调用方注入）
- 第三方依赖在 `metainfo.md` 的 `依赖` 部分声明
- 纯计算型技能（如 Chart）的 `session` 参数可为 `None`

## 版本管理

HopLib 条目使用 [SemVer](https://semver.org/) 版本号，记录在 `metainfo.md` 的 `版本` 字段中。

递增规则：

| 变更类型 | 递增 |
|----------|------|
| `input_contract` / `output_contract` 破坏性变更（删除字段、修改类型） | MAJOR |
| 新增可选输入字段、新增输出字段 | MINOR |
| Bug 修复、性能优化、内部重构 | PATCH |

## 质量门槛

| 指标 | 要求 |
|------|------|
| 单测覆盖率 | >= 99%（含 branch） |
| `test/` 目录 | 必须存在 |
| `TestCases/` 目录 | 推荐（含 `test_cases.jsonl`） |
| metainfo.md | 必须完整填写所有 section |
| SKILL.md | 必须存在（`generate_skill_md` 生成） |

## 引用方式

### HopSpec `call` 步骤引用

在 HopSpec.md 中，`call` 步骤的 `skill` 字段填写 HopLib 条目名称：

```yaml
- step_name: extract_text
  type: call
  skill: OCR
  input_map: {image: "{image_url}"}
  output: ocr_result
```

JIT 引擎的 `_exec_call` 通过 `session._skill_registry.get(name)` 解析技能实例并调用 `invoke()`。

### Python API 引用

```python
from hop_skill import SkillRegistry

reg = SkillRegistry(hoplib_root="HopLib", tasks_root="Tasks")
reg.scan()

skill = reg.get("Chart")
status, result = await skill.invoke(session, {
    "data": [{"x": "A", "y": 1}],
    "chart_type": "bar",
    "x_field": "x",
    "y_field": "y",
})
```

### CLI 引用

```bash
cd hoplogic && uv run python -m hop_skill run Chart '{"data": [{"x":"A","y":1}], "chart_type":"bar", "x_field":"x", "y_field":"y"}'
```

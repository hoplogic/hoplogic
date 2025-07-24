# HOP执行算子梳理
  - hop_get (高阶知识抽取)
  - hop_judge (高阶知识判断)
  - hop_tool_use (工具调用)
    * HOP 显式控制工具调用：仅允许场景相关工具，减少误用； 
    * 自动校验参数/返回格式与类型，异常兜底，保障协同可靠。

# HOP核验算子梳理
  - reverse_verify (逆向核验)
  - forward_cross_verify (正向交叉核验)
  - tool_use_verifier (工具调用核验)

# 如何使用算子，以hop_get为例：
## HOP_GET
#### 功能描述
hop_get 是用于执行信息获取型任务的核心方法，通过结构化输出机制和验证器确保返回数据的准确性。支持自定义返回格式、结果验证和重试机制。
#### 使用示例
##### 示例1：基础调用
```python
agent = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)
status, result = agent.hop_get(
    task="解析用户邮箱",
    context="用户资料：John Doe, contact: john@example.com"
)
print(status)  # 输出: HopStatus.SUCCESS
print(result)  # 输出: "john@example.com"
```

##### 示例2：结构化输出
```python

agent = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)

schema = {
    "city": (str, ...), 
    "temperature": (float, ...),  
    "is_rainy": (bool, ...),  
}

status, data = agent.hop_get(
    task="从文本提取天气信息",
    context="北京今天气温25.6℃，晴天",
    return_format=schema,
    explanation_description="温度单位是摄氏度"
)

# 成功返回示例
print(data)  # 输出: {"explanation":"从文本中提取了北京的天气信息，温度单位为摄氏度。","final_answer":{"city":"北京","temperature":25.6,"is_rainy":false}}
```
##### 示例3：如何接入通用核验
```python

agent = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)
status, result = agent.hop_get(
    task="解析用户邮箱",
    context="用户资料：John Doe, contact: john@example.com",
    verifier=reverse_verify
)
print(status)  # 输出: HopStatus.SUCCESS
print(result)  # 输出: "john@example.com"
```
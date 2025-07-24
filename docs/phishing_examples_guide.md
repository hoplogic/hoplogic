## 🎣 钓鱼邮件场景
钓鱼邮件是指攻击者伪装成可信联系人，通过邮件诱导用户：
- 回复敏感信息  
- 点击恶意链接  
- 打开带毒附件  
从而窃取数据或植入木马，实施进一步攻击。
## 🔍 SOP（人工判断）
判断逻辑：
- 第一步：根据邮件域名判断是否是钓鱼恶意域名，如果是恶意钓鱼域名则判为钓鱼邮件。
- 第二步：判断邮件主题是否与“账号、薪资、个税”等诱导性主题相关，如果不是则判为非钓鱼邮件。
- 第三步：判断邮件主题是否与工作岗位相关，如果相关则判为非钓鱼邮件，否则判为钓鱼邮件。
## 🤖 HOP步骤（系统自动化）
hop步骤： 
- TASK1：hop.tool_use("判断邮件域名是否为钓鱼恶意域名")
- TASK2：hop.judge("判断邮件主题是否与“账号、薪资、个税”等诱导性主题相关")
- TASK3：hop.judge("判断邮件主题是否与工作岗位相关")

## ⚙️ HOP代码（编排）
1. 涉及hop.tool_use算子进行工具调用的，如有自定义工具，请在/hop_engine/sec_tools.py中定义工具函数。例如：
```python
@register_tool("get_mail_doamin_cti")
class DomainCTISearch(BaseTool):
    description = "判断邮件域名是否属于钓鱼邮件恶意域名，输入参数对应为domain字段"
    parameters = [
        {
            "name": "domain",
            "type": "string",
            "description": "查询的邮件域名字段",
            "required": True,
        }
    ]

    def call(self, par: str) -> str:
        domain = json.loads(par).get("domain")
        white_list = ["domino.com", "repldomain.com", "sample-company.com", "awuye.com"]
        black_list = ["testdomain.org", "xyz-tech.org", "randomsite.net"]
        if domain in black_list:
            return "True"
        elif domain in white_list:
            return "False"
        else:
            return "uncertain"
```
2. 填写examples下对应的settings.yaml配置文件
```yaml
system_model_config:
  inference_engine: "your_inference_engine"
  openai:
    api_key: "your_api_key_path"  
    base_url: "base_url"
  model: "qwen3_32b"
  max_tokens: 4000  # 需要调大时修改此处
```
3. 编写对应的HOP代码
##### 读取settings.yaml配置文件，创建处理器实例
```python
from hop_engine.processors.hop_processor import HopProc
from hop_engine.config.model_config import ModelConfig

run_config = ModelConfig.from_yaml(
    "system", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)
verify_config = ModelConfig.from_yaml(
    "verify", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)

hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)
```
##### 自定义核验函数
```python
class VerifyContext:
    think: str  # 思考过程，可以为空
    messages: List[dict]  # prompt的messages
    tool_domain: str  # 工具域 用于工具核验
    response_format: Optional[Type[BaseModel]]
    verify_llm: LLM  # 验证用LLM实例

# 可以根据对应的VerifyContext的内容进行核验，例如：
def temperature_range_verifier(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    """自定义温度范围验证器（示例）"""
    # 从模型结果中提取温度值
    if model_result is None:
        return HopVerifyResult(HopStatus.FAIL, "结果中缺少温度字段")
    if not isinstance(model_result, dict):
        return HopVerifyResult(HopStatus.FAIL, "结果不是字典类型")
    temperature = model_result.get("temperature", 0)

    # 验证范围
    if 0 <= float(temperature) <= 100:
        return HopVerifyResult(HopStatus.OK, f"温度值 {temperature} 在有效范围内")
    return HopVerifyResult(HopStatus.FAIL, f"温度值 不在{temperature} 在有效范围内")
```
##### 编写对应的HOP算子
- TASK1：hop.tool_use("判断邮件域名是否为钓鱼恶意域名")
```python
task = "判断邮件域名是否为钓鱼恶意域名,返回bool类型"
context = "域名：" + str(from_domain) + "邮件主题：" + str(subject)
status, domain_condition = hop_proc.hop_tool_use(
    task=task, context=context, verifier=tool_use_verifier
)
logger.info("Status: %s, Result: %s", status, domain_condition)
if status == HopStatus.OK:
    if str(domain_condition) == "True":
        return "钓鱼邮件"
    elif str(domain_condition) == "False":
        return "非钓鱼邮件"
else:
    return "工具调用失败"
```
- TASK2：hop.judge("判断邮件主题是否与“账号、薪资、个税”等诱导性主题相关")
```python
subject_judge_condition = "根据上下文语境判断邮件主题是否与概念“账号、薪资、个税”匹配，如果匹配则返回True，不匹配返回False，无法确定返回Uncertain。"
explanation_description = "对于结果输出的解释，在最后列出用于判断的关键词，要求关键词必须出自【上下文】部分，以'关键词有**'开头，用'**'结尾，如果有多个关键词用','分割。输出格式为'explanation。关键词有**keyword_1,keyword_2**'"
context = "邮件主题：" + str(subject)
status, subject_condition = hop_proc.hop_judge(
    task=subject_judge_condition,
    context=context,
    verifier=phishing_judge_verifier,
    explanation_description=explanation_description,
)
logger.info("Status: %s, Result: %s", status, subject_condition)
if status == HopStatus.OK:
    if subject_condition.lower() == "false":
        return "非钓鱼邮件"
else:
    return "judge失败"
```
- TASK3：hop.judge("判断邮件主题是否与工作岗位相关")
```python
job_judge_condition = "根据语境判断收到的邮件主题内容与收件人岗位职责是否严格相关，相关则返回True，不相关则返回False，无法确定则返回Uncertain。"
context = "邮件主题：" + str(subject) + "\n收件人岗位：" + str(to_job)
status, job_condition = hop_proc.hop_judge(
    task=job_judge_condition,
    context=context,
    verifier=phishing_judge_verifier,
    explanation_description=explanation_description,
)
logger.info("Status: %s, Result: %s", status, job_condition)
if status == HopStatus.OK:
    if job_condition.lower() == "true":
        return "非钓鱼邮件"
else:
    return "judge失败"
```

4. 组合成对应的HOP函数代码，详见/examples/phishing/phishing.py
5. 执行案例

```bash
sudo python -m examples.phishing.phishing
```
6. 执行案例结果
```python
hop_shared_logger - INFO - =========处理第1个样本:===========
hop_shared_logger - INFO - 您的个税申报被退回，请查看原因并重新提交

Thought: 需要判断邮件域名是否为钓鱼恶意域名，应使用get_mail_doamin_cti工具，输入参数为domain字段。
Action: get_mail_doamin_cti
Action Input: {"domain": "example.com"}
hop_shared_logger - INFO - ========HOP核验结果========
hop_shared_logger - INFO - Attempt 1/3 OK
hop_shared_logger - INFO - Status: HopStatus.OK, Result: uncertain

hop_shared_logger - INFO - ========llm返回答案========
hop_shared_logger - INFO - {"explanation":"邮件主题提到'个税申报被退回'，这直接涉及'个税'这一概念。同时，个税通常与薪资和账号相关联，因为个税的计算和申报需要基于个人的薪资信息，并通过特定的账号进行操作。关键词有**个税,薪资,账号**","final_answer":"True"}
hop_shared_logger - INFO - ======输出的核验response======
hop_shared_logger - INFO - {"explanation":"邮件主题明确提到了'个税申报被退回'，这直接关联到概念中的'个税'部分。因此，可以判断该邮件主题与给定的概念相匹配。关键词有**个税**","final_answer":"Passed"}
hop_shared_logger - INFO - ========HOP核验结果========
hop_shared_logger - INFO - Attempt 1/3 OK
hop_shared_logger - INFO - Status: HopStatus.OK, Result: True


hop_shared_logger - INFO - ========llm返回答案========
hop_shared_logger - INFO - {"explanation":"邮件主题提到个税申报被退回，需要查看原因并重新提交。收件人的岗位是运营，通常与税务处理无直接关联。因此，该邮件内容与收件人岗位职责不严格相关。关键词有**个税申报,运营**","final_answer":"False"}
hop_shared_logger - INFO - ======输出的核验response======
hop_shared_logger - INFO - {"explanation":"邮件主题涉及个税申报问题，这通常与财务或人力资源部门相关，而非运营岗位的职责。因此，该邮件内容与收件人的岗位职责不严格相关。关键词有**个税申报,运营**","final_answer":"Passed"}
hop_shared_logger - INFO - ========HOP核验结果========
hop_shared_logger - INFO - Attempt 1/3 OK
hop_shared_logger - INFO - Status: HopStatus.OK, Result: False

hop_shared_logger - INFO - 最终研判: 钓鱼邮件
hop_shared_logger - INFO - label: 钓鱼邮件
```
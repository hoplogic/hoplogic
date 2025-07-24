from hop_engine.config.constants import TOOL_DOMAINS
from hop_engine.config.constants import JsonValue, HopStatus
from hop_engine.prompts.prompt_strategies import (
    HopReverseVerifyStrategy,
    HopReverseProcessVerifyStrategy,
    HopReverseNoProcessVerifyStrategy,
    MulVeriPromptStrategy,
    PlusVeriPromptStrategy,
)
from hop_engine.callers.llm import LLM
from hop_engine.utils.utils import (
    create_response_format_model,
    safe_json_parse,
    LoggerUtils,
)
from typing import List, Optional, Literal, Type
from qwen_agent.tools.base import BaseTool, register_tool, TOOL_REGISTRY

from pydantic import BaseModel
from dataclasses import dataclass
import json

logger = LoggerUtils.get_logger()


@dataclass
class HopVerifyResult:
    status: HopStatus
    reason: str


@dataclass
class VerifyContext:
    think: str  # 思考过程，可以为空
    messages: List[dict]  # prompt的messages
    tool_domain: str  # 工具域 用于工具核验
    response_format: Optional[Type[BaseModel]]
    verify_llm: LLM  # 验证用LLM实例


def reverse_verify(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:

    hop_status_dict = {status.name: status for status in HopStatus}
    hop_status_desc_dict = {status.name: status.description for status in HopStatus}

    strategy = (
        HopReverseProcessVerifyStrategy()
        if ctx.think
        else HopReverseNoProcessVerifyStrategy()
    )

    full_context = f"{context}\n{hop_status_desc_dict}\nTask: {task}"

    response_format = create_response_format_model(
        "HOPVerifyReasoning", return_format=Literal[tuple(hop_status_dict.keys())]
    )

    verify_prompt = strategy.create_prompt(
        context=full_context,
        think=ctx.think or "",
        conclusion=model_result,
        return_format=str(response_format.model_json_schema()),
    )

    success, raw_response = ctx.verify_llm.query_llm(
        verify_prompt, response_format=response_format, temperature=0.1, max_tokens=2000
    )
    if not success:
        return HopVerifyResult(HopStatus.FAIL, f"LLM调用失败: {raw_response}")
    try:
        parsed_response = safe_json_parse(str(raw_response), response_format)
        # 检查属性是否存在并获取值
        if not hasattr(parsed_response, "final_answer"):
            raise ValueError("parsed_response 对象中缺少 'final_answer' 属性")
        final_answer = parsed_response.final_answer
        if not hasattr(parsed_response, "explanation"):
            raise ValueError("parsed_response 对象中缺少 'explanation' 属性")
        explanation = parsed_response.explanation
    except ValueError as e:
        return HopVerifyResult(HopStatus.FAIL, str(e))

    return HopVerifyResult(
        status=hop_status_dict.get(final_answer, HopStatus.FAIL), reason=explanation
    )


def forward_cross_verify(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    params = {
        "messages": ctx.messages,
        "temperature": 0.3,
        "response_format": ctx.response_format,
        "max_tokens": 2000,
    }
    reference_results = []
    for attempt in range(3):
        success, raw_response = ctx.verify_llm.query_llm(**params)

        if not success:
            logger.error(f"第 {attempt+1} 次验证调用失败: {raw_response}")
            continue
        try:
            if ctx.response_format:
                parsed = safe_json_parse(str(raw_response), ctx.response_format)
                result = parsed.final_answer
            else:
                result = raw_response
            reference_results.append(
                result.json() if isinstance(result, BaseModel) else result
            )
        except ValueError as e:
            logger.error(f"结果解析失败: {str(e)}")

    match_count = reference_results.count(model_result)
    total = len(reference_results)

    status_mapping = [
        (0.7, HopStatus.OK),  # ≥70%匹配
        (0.4, HopStatus.UNCERTAIN),  # ≥40%匹配
        (0, HopStatus.FAIL),  # <40%
    ]

    for threshold, status in status_mapping:
        if (match_count / total if total > 0 else 0) >= threshold:
            return HopVerifyResult(
                status=status, reason=f"一致性验证 ({match_count}/{total})"
            )

    return HopVerifyResult(HopStatus.FAIL, "无法确定验证状态")


def tool_use_verifier(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    tool_list = TOOL_DOMAINS[ctx.tool_domain]
    tool_use_dict = json.loads(str(model_result))
    action, action_input = tool_use_dict.get("action"), tool_use_dict.get(
        "action_input"
    )
    # action 存在校验
    if action not in tool_list:
        return HopVerifyResult(HopStatus.FAIL, f"工具 {action} 不在可用范围内")
    # action_input 参数检验
    tool_params = TOOL_REGISTRY[action].parameters
    for param in tool_params:
        if param["name"] not in action_input:
            return HopVerifyResult(
                HopStatus.FAIL, "action_input参数不合法，缺少参数{}".format(param["name"])
            )
    # 正向交叉核验工具action选取
    params = {
        "messages": ctx.messages,
        "temperature": 0.3,
        "max_tokens": 5000,
    }
    reference_results = []
    for attempt in range(3):
        success, raw_response = ctx.verify_llm.query_llm(**params)

        if not success:
            logger.error(f"第 {attempt+1} 次验证调用失败: {raw_response}")
            continue

        result = raw_response
        reference_results.append(
            result.json() if isinstance(result, BaseModel) else result
        )

    match_cases = [result for result in reference_results if action in result]
    match_count = len(match_cases)
    total = len(reference_results)

    status_mapping = [
        (0.7, HopStatus.OK),  # ≥70%匹配
        (0.4, HopStatus.UNCERTAIN),  # ≥40%匹配
        (0, HopStatus.FAIL),  # <40%
    ]

    for threshold, status in status_mapping:
        if (match_count / total if total > 0 else 0) >= threshold:
            return HopVerifyResult(
                status=status, reason=f"工具action核验成功 ({match_count}/{total})"
            )

    return HopVerifyResult(HopStatus.FAIL, "无法确定验证状态")


#### 场景自定义核验 ######


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


def plus_verifier(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    hop_status_dict = {status.name: status for status in HopStatus}
    context = context
    model_result = (model_result,)  # 使用处理后的答案
    response_format = ctx.response_format
    # 构建核验prompt
    context = json.loads(context)
    num1 = context.get("number1", "")
    num2 = context.get("number2", "")
    model_result = json.loads(model_result[0])
    mul_result = model_result.get("result")
    strategy = PlusVeriPromptStrategy()
    full_context = """
数字1：{num1}
数字2：{num2}
""".format(
        num1=num1, num2=num2
    )

    response_format = create_response_format_model(
        "HOPVerifyReasoning", return_format=Literal[tuple(hop_status_dict.keys())]
    )
    verify_prompt = strategy.create_prompt(
        context=full_context,
        model_result=mul_result,
        return_format=str(response_format.model_json_schema()),
    )

    success, raw_response = ctx.verify_llm.query_llm(
        verify_prompt, response_format=response_format, temperature=0.1, max_tokens=2000
    )
    if not success:
        return HopVerifyResult(HopStatus.FAIL, f"LLM调用失败: {raw_response}")
    try:
        parsed_response = safe_json_parse(str(raw_response), response_format)
        # 检查属性是否存在并获取值
        if not hasattr(parsed_response, "final_answer"):
            raise ValueError("parsed_response 对象中缺少 'final_answer' 属性")
        final_answer = parsed_response.final_answer
        if not hasattr(parsed_response, "explanation"):
            raise ValueError("parsed_response 对象中缺少 'explanation' 属性")
        explanation = parsed_response.explanation
    except ValueError as e:
        return HopVerifyResult(HopStatus.FAIL, str(e))

    return HopVerifyResult(
        status=hop_status_dict.get(final_answer, HopStatus.FAIL), reason=explanation
    )


def multation_verifier(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    hop_status_dict = {status.name: status for status in HopStatus}
    context = context
    model_result = (model_result,)  # 使用处理后的答案
    response_format = ctx.response_format
    # 构建核验prompt
    context = json.loads(context)
    num1 = context.get("number1", "")
    num2 = context.get("number2", "")
    model_result = json.loads(model_result[0])
    mul_result = model_result.get("result")
    strategy = MulVeriPromptStrategy()
    full_context = """
数字1：{num1}
数字2：{num2}
""".format(
        num1=num1, num2=num2
    )

    response_format = create_response_format_model(
        "HOPVerifyReasoning", return_format=Literal[tuple(hop_status_dict.keys())]
    )
    verify_prompt = strategy.create_prompt(
        context=full_context,
        model_result=mul_result,
        return_format=str(response_format.model_json_schema()),
    )

    success, raw_response = ctx.verify_llm.query_llm(
        verify_prompt, response_format=response_format, temperature=0.1, max_tokens=2000
    )
    if not success:
        return HopVerifyResult(HopStatus.FAIL, f"LLM调用失败: {raw_response}")
    try:
        parsed_response = safe_json_parse(str(raw_response), response_format)
        # 检查属性是否存在并获取值
        if not hasattr(parsed_response, "final_answer"):
            raise ValueError("parsed_response 对象中缺少 'final_answer' 属性")
        final_answer = parsed_response.final_answer
        if not hasattr(parsed_response, "explanation"):
            raise ValueError("parsed_response 对象中缺少 'explanation' 属性")
        explanation = parsed_response.explanation
    except ValueError as e:
        return HopVerifyResult(HopStatus.FAIL, str(e))

    return HopVerifyResult(
        status=hop_status_dict.get(final_answer, HopStatus.FAIL), reason=explanation
    )


# 钓鱼场景核验
def phishing_judge_verifier(
    task: str, context: str, model_result: JsonValue, ctx: VerifyContext
) -> HopVerifyResult:
    def overlap_ratio(keywords_1, keywords_2, ratio_t):
        import difflib

        matched = set()

        for k1 in keywords_1:
            for k2 in keywords_2:
                if (
                    k1 == k2
                    or k1 in k2
                    or k2 in k1
                    or difflib.SequenceMatcher(None, k1, k2).ratio() > 0.7
                ):
                    matched.add((k1, k2))
                    break

        total_elements = len(set(keywords_1 + keywords_2))
        overlap_count = len(matched)
        radio = overlap_count / total_elements if total_elements > 0 else 0
        return radio > ratio_t or overlap_count >= 2

    hop_status_dict = {"Passed": HopStatus.OK, "Not Passed": HopStatus.FAIL}

    strategy = HopReverseVerifyStrategy()

    full_context = f"{context}\n"

    response_format = create_response_format_model(
        "HOPVerifyReasoning",
        return_format=Literal[tuple(hop_status_dict.keys())],
        explanation_description="对于final_answer的解释，在最后列出用于判断的关键词，要求关键词必须出自【上下文】部分，以'关键词有**'开头，用'**'结尾，如果有多个关键词用','分割。输出格式为'explanation。关键词有**keyword_1,keyword_2**'",
    )

    verify_prompt = strategy.create_prompt(
        task=str(task),
        context=full_context,
        conclusion=str(model_result),
        return_format=str(response_format.model_json_schema()),
    )

    success, raw_response = ctx.verify_llm.query_llm(
        verify_prompt, response_format=response_format, temperature=0.1, max_tokens=2000
    )
    logger.info("======输入的核验prompt======")
    logger.info(verify_prompt)
    logger.info("======输出的核验response======")
    logger.info(raw_response)
    if not success:
        return HopVerifyResult(HopStatus.FAIL, f"LLM调用失败: {raw_response}")
    try:
        parsed_response = safe_json_parse(str(raw_response), response_format)
        # 检查属性是否存在并获取值
        if not hasattr(parsed_response, "final_answer"):
            raise ValueError("parsed_response 对象中缺少 'final_answer' 属性")
        final_answer = parsed_response.final_answer
        if not hasattr(parsed_response, "explanation"):
            raise ValueError("parsed_response 对象中缺少 'explanation' 属性")
        explanation = parsed_response.explanation
    except ValueError as e:
        return HopVerifyResult(HopStatus.FAIL, str(e))
    if (
        hop_status_dict.get(final_answer) == HopStatus.FAIL
        or model_result.lower() != "true"
    ):
        return HopVerifyResult(
            status=hop_status_dict.get(final_answer, HopStatus.FAIL),
            reason=explanation.split("关键词有**", 1)[0],
        )

    if "关键词有**" not in ctx.think or "关键词有**" not in explanation:
        return HopVerifyResult(
            status=HopStatus.FAIL,
            reason="think或explanation字段中缺乏关键词",
        )

    keywords_1 = (
        ctx.think.replace("，", ",").split("关键词有**", 1)[1].split("**", 1)[0].split(",")
    )
    keywords_2 = (
        explanation.replace("，", ",").split("关键词有**", 1)[1].split("**", 1)[0].split(",")
    )

    if keywords_1 == keywords_2:
        return HopVerifyResult(
            status=hop_status_dict.get(final_answer, HopStatus.FAIL), reason=explanation
        )
    keywords_1 = [
        keyword.strip() for keyword in keywords_1 if keyword.strip() in context
    ]
    keywords_2 = [
        keyword.strip() for keyword in keywords_2 if keyword.strip() in context
    ]

    if len(keywords_1) == 0 or len(keywords_2) == 0:
        return HopVerifyResult(
            status=HopStatus.FAIL,
            reason="explanation字段中缺乏关键词，或者关键词提取格式不符合",
        )
    if overlap_ratio(keywords_1, keywords_2, 0.25):
        return HopVerifyResult(
            status=hop_status_dict.get(final_answer, HopStatus.FAIL), reason=explanation
        )
    else:
        return HopVerifyResult(status=HopStatus.FAIL, reason="关键词比对不通过")

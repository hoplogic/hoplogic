from qwen_agent.tools.base import BaseTool, register_tool, TOOL_REGISTRY
from hop_engine.config.constants import TOOL_DOMAINS
from hop_engine.prompts.hop import (
    HOP_GET_PROMPT,
    HOP_JUDGE_PROMPT,
    HOP_TOOL_USE_PROMPT,
    HOP_REVERSE_VERIFIER_PROMPT,
    HOP_REVERSE_VERIFIER_PROMPT_PROCESS,
    HOP_REVERSE_VERIFIER_PROMPT_NO_PROCESS,
    HOP_TOOL_USE_VERIFIER_PROMPT,
)
from hop_engine.prompts.verifier import (
    MUL_VERIFIER_PROMPT,
    PLUS_VERIFIER_PROMPT,
)
from hop_engine.sec_tools import *

# 定义 Prompt 策略基类
class PromptStrategy:
    def create_prompt(self, *args, **kwargs):
        raise NotImplementedError("子类必须实现 create_prompt 方法")


# 辅助函数，用于生成用户角色的提示列表
def generate_user_prompt(prompt_content):
    return [{"role": "user", "content": prompt_content}]


# 定义 hop_get 的 Prompt 策略类
class HopGetPromptStrategy(PromptStrategy):
    def create_prompt(self, task, context, return_format=""):
        prompt = HOP_GET_PROMPT.format(
            task=task, return_format=return_format, context=context
        )
        return generate_user_prompt(prompt)


# 定义 hop_judge 的 Prompt 策略类
class HopJudgePromptStrategy(PromptStrategy):
    def create_prompt(self, task, context, return_format=""):
        prompt = HOP_JUDGE_PROMPT.format(
            task=task, return_format=return_format, context=context
        )
        return generate_user_prompt(prompt)


# 定义 tool_use 的 Prompt 策略类
class ToolUsePromptStrategy(PromptStrategy):
    def create_prompt(self, task, context, tool_domain):
        tool_names = []
        tool_descs = []
        if tool_domain in TOOL_DOMAINS:
            add_tools = TOOL_DOMAINS[tool_domain]
        else:
            add_tools = []

        for tool in [tool for tool in TOOL_REGISTRY if tool in add_tools]:
            tool_names.append(tool)
            tool_descs.append(
                tool
                + ":"
                + TOOL_REGISTRY[tool].description
                + "parameters:"
                + str(TOOL_REGISTRY[tool].parameters)
            )

        query = "根据我的工具要求:{}，日志:{},帮我选取下工具".format(task, str(context))
        prompt = HOP_TOOL_USE_PROMPT.format(
            tool_descs=tool_descs, tool_names=tool_names, task=query
        )
        return generate_user_prompt(prompt)


# 定义 verify 的 Prompt 策略类


class HopReverseVerifyStrategy(PromptStrategy):
    def create_prompt(self, task, context, conclusion, return_format=""):
        prompt = HOP_REVERSE_VERIFIER_PROMPT.format(
            task=task,
            context=context,
            conclusion=conclusion,
            return_format=str(return_format),
        )
        return generate_user_prompt(prompt)



class HopReverseProcessVerifyStrategy(PromptStrategy):
    def create_prompt(self, context, think, conclusion, return_format=""):
        prompt = HOP_REVERSE_VERIFIER_PROMPT_PROCESS.format(
            context=context,
            think=think,
            conclusion=conclusion,
            return_format=str(return_format),
        )
        return generate_user_prompt(prompt)


class HopReverseNoProcessVerifyStrategy(PromptStrategy):
    def create_prompt(self, context, think, conclusion, return_format=""):
        prompt = HOP_REVERSE_VERIFIER_PROMPT_NO_PROCESS.format(
            context=context, conclusion=conclusion, return_format=str(return_format)
        )
        return generate_user_prompt(prompt)


class HopForwardCrossVerifyStrategy(PromptStrategy):
    def create_prompt(self, prompt, return_format=""):
        return generate_user_prompt(prompt)


class ToolUseVerifyPromptStrategy(PromptStrategy):
    def create_prompt(self, task, context, tool_domain):
        tool_names = []
        tool_descs = []
        if tool_domain in TOOL_DOMAINS:
            add_tools = TOOL_DOMAINS[tool_domain]
        else:
            add_tools = []

        for tool in [tool for tool in TOOL_REGISTRY if tool in add_tools]:
            tool_names.append(tool)
            tool_descs.append(
                tool
                + ":"
                + TOOL_REGISTRY[tool].description
                + "parameters:"
                + str(TOOL_REGISTRY[tool].parameters)
            )

        query = "根据我的工具要求:{}，日志:{},帮我选取下工具".format(task, str(context))
        prompt = HOP_TOOL_USE_VERIFIER_PROMPT.format(
            tool_descs=tool_descs, tool_names=tool_names, task=query
        )
        return generate_user_prompt(prompt)


# 定义 加法核验 的 Prompt 策略类
class PlusVeriPromptStrategy(PromptStrategy):
    def create_prompt(self, context, model_result, return_format=""):
        prompt = PLUS_VERIFIER_PROMPT.format(
            return_format=return_format, context=context, llm_result=model_result
        )
        return generate_user_prompt(prompt)


# 定义 乘法核验 的 Prompt 策略类
class MulVeriPromptStrategy(PromptStrategy):
    def create_prompt(self, context, model_result, return_format=""):
        prompt = MUL_VERIFIER_PROMPT.format(
            return_format=return_format, context=context, llm_result=model_result
        )
        return generate_user_prompt(prompt)

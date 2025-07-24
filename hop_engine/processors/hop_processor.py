from inspect import signature
import json
from typing import Any, Callable, Literal, Optional, Tuple, Type

from hop_engine.callers.llm import LLM
from hop_engine.config.constants import TOOL_DOMAINS
from hop_engine.config.constants import HopStatus, JsonValue
from hop_engine.config.model_config import ModelConfig
from hop_engine.prompts.prompt_strategies import (
    HopGetPromptStrategy,
    HopJudgePromptStrategy,
    PromptStrategy,
    ToolUsePromptStrategy,
)
from pydantic import BaseModel
from qwen_agent.tools.base import TOOL_REGISTRY
from hop_engine.utils.status_recorder import RetryContext, auto_record_status
from hop_engine.utils.utils import (
    LoggerUtils,
    create_response_format_model,
    safe_json_parse,
)
from hop_engine.validators.result_validators import (
    VerifyContext,
    forward_cross_verify,
    reverse_verify,
    tool_use_verifier,
)

logger = LoggerUtils.get_logger()


class HopProc:
    def __init__(
        self,
        run_model_config: Optional[ModelConfig] = None,
        verify_model_config: Optional[ModelConfig] = None,
        hop_retry: int = 3,
        system_prompt: str = "",
        debug: bool = False,
    ):
        if run_model_config is None:
            raise ValueError("run_model_config 不能为 None，请通过配置文件显式传递参数")
        if verify_model_config is None:
            raise ValueError("verify_model_config 不能为 None，请通过配置文件显式传递参数")
        self.run_model_config = run_model_config
        self.verify_model_config = verify_model_config
        self.system_prompt = system_prompt
        self.hop_retry = hop_retry
        self.debug = debug
        self._init_models(run_model_config, verify_model_config)
        self.validators = {"reverse": reverse_verify, "cross": forward_cross_verify}

    def _init_models(self, run_cfg: ModelConfig, verify_cfg: ModelConfig):
        self.run_cfg = run_cfg
        self.verify_cfg = verify_cfg

        self.run_llm = self._create_llm(self.run_cfg)
        self.verify_llm = self._create_llm(self.verify_cfg)

    def _create_llm(self, config: ModelConfig) -> LLM:
        return LLM(
            model=config.model,
            system_prompt=self.system_prompt,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            inference_engine=config.inference_engine,
            timeout=config.timeout,
            max_retry_count=config.max_retry_count,
        )

    def _create_response_model(
        self,
        task_type: str,
        return_format: JsonValue,
        explanation_description: str = "对于输出结果的解释",
    ) -> Type[BaseModel]:
        model_name = f"HOP{task_type}Reasoning"
        if explanation_description:
            return create_response_format_model(
                model_name, return_format, explanation_description
            )
        else:
            return create_response_format_model(model_name, return_format)

    def _get_verifier_params(self, verifier: Callable, ctx: VerifyContext) -> dict:
        sig = signature(verifier)
        params = sig.parameters.keys()
        return {k: getattr(ctx, k) for k in params if hasattr(ctx, k)}

    def _detect_tool(self, text):
        special_func_token = "Action:"
        special_args_token = "\nAction Input:"

        func_name, func_args = None, None
        i = text.rfind(special_func_token)
        j = text.rfind(special_args_token)

        if 0 <= i < j:
            # Extract function name and arguments
            func_name = text[i + len(special_func_token) : j].strip()
            func_args = text[j + len(special_args_token) :].strip()

            return True, func_name, func_args
        return False, None, None

    def _prepare_task(
        self,
        task: str,
        context: str,
        tool_domain: str = "",
        strategy_class: Type[PromptStrategy] = PromptStrategy,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> list:
        """任务准备阶段：生成prompt messages"""
        from hop_engine.config.constants import SAFETY_TOKENS

        # 过滤越狱TOKEN
        def sanitize_text(text: str) -> str:
            for token in SAFETY_TOKENS:
                text = text.replace(token, "")
            return text

        task = sanitize_text(task)
        context = sanitize_text(context)
        strategy = strategy_class()
        if strategy_class == ToolUsePromptStrategy:
            return strategy.create_prompt(
                task=task,
                context=context,
                tool_domain=tool_domain,
            )
        else:
            if response_model:
                return strategy.create_prompt(
                    task=task,
                    context=context,
                    return_format=response_model.model_json_schema(),
                )
            return strategy.create_prompt(task=task, context=context)

    def _execute_core(
        self, messages: list, response_model: Optional[Type[BaseModel]] = None
    ) -> str:
        """核心执行阶段：LLM交互"""
        try:
            success, response = self.run_llm.query_llm(
                messages,
                response_format=response_model,
                temperature=self.run_cfg.temperature,
                max_tokens=self.run_cfg.max_tokens,
            )
            if not success:
                raise ValueError(f"LLM API Error: {response}")
            return str(response)

        except Exception as e:
            raise RuntimeError(f"Execution Failed: {str(e)}")

    def _verify_result(
        self,
        verifier: Optional[Callable],
        task: str,
        context: str,
        messages: list,
        answer: str,
        tool_domain: str,
        response_model: Optional[Type[BaseModel]] = None,
    ) -> Tuple[HopStatus, str, str]:
        """HOP验证阶段"""

        # 工具类解析
        if tool_domain:
            has_action, func_name, func_args = self._detect_tool(answer)
            if not has_action:
                return HopStatus.FAIL, f"解析失败: 未找到Action和Action Input", answer
            if not func_name or not func_args:
                return HopStatus.FAIL, f"解析失败: Action和Action Input为空", answer
            processed_answer = {"action": func_name, "action_input": func_args}
            processed_answer = json.dumps(processed_answer)
            process = ""
        # 非工具场景解析
        else:
            # 格式核验
            try:
                if response_model:
                    parsed_result = safe_json_parse(answer, response_model)
                    processed_answer = (
                        parsed_result.final_answer.json()
                        if isinstance(parsed_result.final_answer, BaseModel)
                        else parsed_result.final_answer
                    )
                    process = parsed_result.explanation
                else:
                    processed_answer = answer
                    process = ""
            except Exception as e:
                return HopStatus.FAIL, f"解析失败: {str(e)}", ""

        if verifier == None:
            return HopStatus.OK, "", processed_answer

        verify_ctx = VerifyContext(
            think=process,
            messages=messages,
            tool_domain=tool_domain,
            response_format=response_model,
            verify_llm=self.verify_llm,
        )

        verification_result = verifier(
            task=task, context=context, model_result=processed_answer, ctx=verify_ctx
        )
        return verification_result.status, verification_result.reason, processed_answer

    def _execute_task(
        self,
        task: str,
        context: str,
        strategy_class: Type[PromptStrategy],
        response_model: Optional[Type[BaseModel]] = None,
        tool_domain: str = "",
        verifier: Optional[Callable] = None,
    ) -> Tuple[HopStatus, Optional[Any], int]:  # 返回元组增加重试次数
        """整合执行流程，返回重试次数"""

        if strategy_class == ToolUsePromptStrategy:
            if tool_domain not in TOOL_DOMAINS:
                return HopStatus.FAIL, f"工具域{tool_domain}不存在", 0
            if verifier and verifier != tool_use_verifier:
                return HopStatus.FAIL, f"工具验证器{verifier}必须是tool_use_verifier", 0

        original_context = context  # 保存原始上下文避免污染
        error_info = ""
        attempts = 0

        for attempt in range(1, self.hop_retry + 1):
            attempts = attempt  # 记录当前尝试次数
            is_last_attempt = attempt == self.hop_retry
            current_context = original_context

            if error_info:
                current_context += f"\n核验反馈信息：{error_info} 请重新再执行一下哈\n"

            # 动态生成任务messages
            messages = self._prepare_task(
                task, current_context, tool_domain, strategy_class, response_model
            )
            if self.debug:
                logger.info("========prompt========")
                logger.info(messages)
            # 执行核心流程
            answer = self._execute_core(messages, response_model)
            if self.debug:
                logger.info("========llm返回答案========")
                logger.info(answer)
            # HOP验证结果
            status, reason, processed_answer = self._verify_result(
                verifier=verifier,
                task=task,
                context=context,
                messages=messages,
                answer=answer,
                tool_domain=tool_domain,
                response_model=response_model,
            )
            if self.debug:
                logger.info("========HOP核验结果========")
            # 记录重试每次日志
            if status == HopStatus.OK:
                RetryContext.log_retry_attempt(status, processed_answer)
                logger.info(f"Attempt {attempt}/{self.hop_retry} OK")
                return status, processed_answer, attempts - 1

            elif is_last_attempt:
                if status in (HopStatus.LACK_OF_INFO, HopStatus.UNCERTAIN):
                    RetryContext.log_retry_attempt(status, processed_answer)
                    logger.info(
                        f"Attempt {attempt}/{self.hop_retry} not OK, retrying... Status:{status},Reason:{processed_answer}"
                    )
                    return status, processed_answer, attempts - 1
                else:
                    RetryContext.log_retry_attempt(HopStatus.FAIL, reason)
                    logger.info(
                        f"Attempt {attempt}/{self.hop_retry} failed, retrying... Status:{status},Reason:{error_info}"
                    )
                    return HopStatus.FAIL, reason, attempts - 1
            else:
                error_info = reason
                logger.info(
                    f"Attempt {attempt}/{self.hop_retry} failed, retrying... Status:{status},Reason:{error_info}"
                )
                RetryContext.log_retry_attempt(status, reason)
        return HopStatus.FAIL, None, attempts - 1

    @auto_record_status
    def hop_get(
        self,
        task: str,
        context: str = "",
        return_format: JsonValue = None,
        verifier: Optional[Callable] = reverse_verify,
        explanation_description: str = "",
    ) -> Tuple[HopStatus, JsonValue]:
        """信息获取型任务"""
        if return_format:
            # 构建 Structured Outputs pydantic类
            if explanation_description:
                response_model = self._create_response_model(
                    "Get", return_format, explanation_description
                )
            else:
                response_model = self._create_response_model("Get", return_format)
        else:
            response_model = None

        status, result, attempts = self._execute_task(
            task=task,
            context=context,
            strategy_class=HopGetPromptStrategy,
            response_model=response_model,
            verifier=verifier,
        )

        # 将重试次数存储在上下文
        RetryContext.set_retry_count(attempts)
        return status, result

    @auto_record_status
    def hop_judge(
        self,
        task: str,
        context: str = "",
        return_format: JsonValue = None,
        verifier: Optional[Callable] = reverse_verify,
        explanation_description: str = "",
    ) -> Tuple[HopStatus, JsonValue]:
        """研判型任务"""
        if return_format is None:
            return_format = Literal[tuple(["True", "False", "Uncertain"])]
        # 构建 Structured Outputs pydantic类
        if explanation_description:
            response_model = self._create_response_model(
                "Judge", return_format, explanation_description
            )
        else:
            response_model = self._create_response_model("Judge", return_format)
        status, result, attempts = self._execute_task(
            task=task,
            context=context,
            strategy_class=HopJudgePromptStrategy,
            response_model=response_model,
            verifier=verifier,
        )

        # 将重试次数存储在上下文
        RetryContext.set_retry_count(attempts)
        return status, result

    @auto_record_status
    def hop_tool_use(
        self,
        task: str,
        context: str = "",
        tool_domain: str = "all",
        verifier: Optional[Callable] = tool_use_verifier,
    ) -> Tuple[HopStatus, JsonValue]:
        """工具调用任务"""
        if not tool_domain:
            tool_domain = "all"

        status, processed_answer, attempts = self._execute_task(
            task=task,
            context=context,
            strategy_class=ToolUsePromptStrategy,
            response_model=None,
            tool_domain=tool_domain,
            verifier=verifier,
        )
        RetryContext.set_retry_count(attempts)
        if status == HopStatus.OK:
            processed_answer = json.loads(str(processed_answer))
            action, action_input = (
                processed_answer["action"],
                processed_answer["action_input"],
            )
            tool = TOOL_REGISTRY[action]()
            tool_result = tool.call(action_input)
            return status, tool_result
        else:
            return status, processed_answer

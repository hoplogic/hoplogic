from typing import Any, Dict, List
from hop_engine.utils.utils import LoggerUtils
import openai

logger = LoggerUtils.get_logger()


class LLM:
    def __init__(
        self,
        model: str,
        system_prompt: str = "",
        api_key: str = "",
        base_url: str = "",
        timeout: int = 120,
        inference_engine: str = "vllm",
        max_retry_count: int = 1,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retry_count = max_retry_count
        self.inference_engine = inference_engine
        self.system_prompt = system_prompt

    def _create_client(self):
        return openai.Client(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def _handle_error(self, e: Exception, attempt: int) -> str:
        error_message = f"Attempt {attempt + 1}/{self.max_retry_count} failed: {str(e)}"
        logger.error(error_message)
        if attempt < self.max_retry_count - 1:
            logger.info(f"Retrying... Attempt {attempt + 2}/{self.max_retry_count}")
        return error_message

    def query_llm(
        self,
        messages: List[Dict[str, str]],
        response_format: Any = None,
        temperature: float = 0,
        max_tokens: int = 1000,
    ):
        client = self._create_client()
        params = {
            "model": self.model,
            "messages": messages,
            "timeout": self.timeout,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": {"split_reasoning_content": True, "separate_reasoning": True},
        }
        error_details = []
        for attempt in range(self.max_retry_count):
            try:
                if response_format:
                    json_schema = response_format.model_json_schema()
                    params["extra_body"]["guided_json"] = json_schema
                    if self.inference_engine == "aistudio-vllm":
                        response = client.chat.completions.create(
                            **params,
                            response_format={
                                "type": "json_schema",
                                "json_schema": {"schema": json_schema},
                            },
                        )
                    elif self.inference_engine in ["siliconflow"]:
                        response = client.chat.completions.create(
                            **params,
                            response_format={"type": "json_object"},
                        )
                    # bailian 不使用 json_object
                    elif self.inference_engine in ["bailian"]:
                        params["extra_body"]["enable_thinking"] = False
                        response = client.chat.completions.create(
                            **params,
                        )
                    else:
                        response = client.beta.chat.completions.parse(
                            **params, response_format=response_format
                        )
                        return True, response.choices[0].message.parsed.json()
                else:
                    response = client.chat.completions.create(**params)

                # 深度推理模型 think
                # if hasattr(response.choices[0].message, "reasoning_content"):
                return True, response.choices[0].message.content
            except Exception as e:
                error_message = self._handle_error(e, attempt)
                if error_message:
                    error_details.append(error_message)
        return False, error_details

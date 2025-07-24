from pydantic import BaseModel
import yaml
from pathlib import Path


class ModelConfig(BaseModel):
    model: str
    inference_engine: str = "vllm"
    openai_api_key: str
    openai_base_url: str
    frequency_penalty: float = 0.0
    max_completion_tokens: int = 1000
    max_tokens: int = 5000
    n: int = 1
    stream: bool = False
    temperature: float = 0.1
    top_p: float = 1.0
    timeout: int = 120
    max_retry_count: int = 3

    @classmethod
    def from_yaml(cls, config_type: str, file_path: str = None):
        config_path = Path(__file__).parent / (file_path or "settings.yaml")
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            data = data[f"{config_type}_model_config"]

            # 从配置中获取密钥文件路径
            api_key_path = Path(data["openai"]["api_key"])

            # 验证路径并读取密钥
            if not api_key_path.exists():
                raise FileNotFoundError(f"API key file not found at {api_key_path}")
            if not api_key_path.is_file():
                raise IsADirectoryError(
                    f"API key path is a directory, not a file: {api_key_path}"
                )

            with open(api_key_path, "r") as key_file:
                openai_api_key = key_file.read().strip()

            return cls(
                openai_api_key=openai_api_key,
                openai_base_url=data["openai"]["base_url"],
                **data,
            )

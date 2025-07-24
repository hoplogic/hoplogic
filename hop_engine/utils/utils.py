from pydantic import BaseModel, create_model, ValidationError, Field
from typing import List, Any, Type
import re
import logging
import json
import ast
import inspect


class LoggerUtils:
    _logger = None

    @classmethod
    def get_logger(cls, name="hop_shared_logger", log_file="hop_log.log"):
        if cls._logger is None:
            cls._logger = logging.getLogger(name)
            cls._logger.setLevel(logging.DEBUG)

            if not cls._logger.handlers:
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )

                # 添加控制台处理器
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                cls._logger.addHandler(console_handler)

                # 如果指定了日志文件路径，则添加文件处理器
                if log_file:
                    file_handler = logging.FileHandler(log_file)
                    file_handler.setFormatter(formatter)
                    cls._logger.addHandler(file_handler)

        return cls._logger


def safe_json_parse(s: str, model: Type[BaseModel]) -> BaseModel:
    """
    安全解析并验证JSON字符串到指定Pydantic模型
    """
    try:
        cleaned_json = extract_json_from_string(s)
        return model.model_validate_json(cleaned_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON format{}".format(e)) from e
    except ValidationError as e:
        raise ValueError("Validation failed {}".format(e)) from e


def extract_json_from_string(s: str) -> str:
    """
    从混合内容中分离思考过程和JSON数据（返回元组：思考内容, 清理后的JSON）

    改进点：
    1. 严格分割 </think> 标签
    2. 智能处理多种JSON格式（含容错机制）
    3. 支持Python风格布尔值的转换
    """
    # 分离思考内容 和 JSON数据
    think_tag = "</think>"
    json_tag = "```json"

    if think_tag in s:
        s = s.split(think_tag, 1)[0]
    if json_tag in s:
        json_str = s.split(json_tag, 1)[1].strip()
    else:
        json_str = s.strip()

    # 清理Markdown代码块
    json_str = re.sub(
        r"^\s*```json|```\s*$", "", json_str, flags=re.IGNORECASE | re.MULTILINE
    )

    # 容错处理流程
    for _ in range(2):  # 最多尝试两次解析
        try:
            # 尝试直接解析JSON
            parsed = json.loads(json_str)
            if "properties" in parsed:
                parsed = parsed["properties"]
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            # 尝试修复Python风格的字典
            try:
                parsed = ast.literal_eval(json_str)
                if isinstance(parsed, dict):
                    # 转换Python布尔值到JSON兼容格式
                    converted = {
                        k: str(v).lower() if isinstance(v, bool) else v
                        for k, v in parsed.items()
                    }
                    if "properties" in converted:
                        converted = converted["properties"]
                    return json.dumps(converted, ensure_ascii=False)
            except (SyntaxError, ValueError):
                # 修复常见JSON错误
                json_str = json_str.replace("'", '"')
                json_str = re.sub(r"(?<!\\)\"", '"', json_str)  # 处理转义引号
                json_str = re.sub(r",\s*(?=[}\]])", "", json_str)  # 移除尾部逗号

    # 最终验证
    try:
        parsed = json.loads(json_str)
        if "properties" in parsed:
            parsed = parsed["properties"]
        return json.dumps(parsed, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"无法解析JSON内容: {str(e)}")


def create_response_format_model(
    model_name: str,
    return_format: Any = None,
    explanation_description: str = "对于输出结果的解释"
) -> Type[BaseModel]:

    explanation_field = (str, Field(..., description=explanation_description))

    def process_value(value: Any) -> tuple:
        """统一处理字段定义中的 ... 和 Field"""
        if isinstance(value, tuple):
            # 处理 (type, ...) 语法糖
            if len(value) == 2 and value[1] is ...:
                return (value[0], Field(...))
            # 处理 Field 实例或已定义的规则
            elif len(value) >= 2 and (
                isinstance(value[1], (type(Field(...)), type(...)))
            ):
                field_type = value[0]
                field_args = (
                    value[1] if not isinstance(value[1], type(...)) else Field(...)
                )
                return (field_type, field_args)
            else:
                raise ValueError(f"Invalid tuple format: {value}")
        else:
            # 递归处理嵌套结构
            sub_model = create_response_format_model(f"{model_name}_Nested", value)
            return (sub_model, Field(...))

    if return_format is None:
        final_answer_type = (str, Field(...))
    elif inspect.isclass(return_format) and issubclass(return_format, (BaseModel,)):
        final_answer_type = (return_format, Field(...))
    elif isinstance(return_format, tuple):
        final_answer_type = process_value(return_format)
    elif isinstance(return_format, dict):
        nested_fields = {}
        for key, value in return_format.items():
            nested_fields[key] = process_value(value)
        nested_model = create_model(f"{model_name}_Nested", **nested_fields)
        final_answer_type = (nested_model, Field(...))
    elif isinstance(return_format, list):
        item_type = return_format[0] if return_format else str
        list_model = create_response_format_model(f"{model_name}_Item", item_type)
        final_answer_type = (List[list_model], Field(...))
    else:
        final_answer_type = (return_format, Field(...))

    return create_model(
        model_name, explanation=explanation_field, final_answer=final_answer_type
    )

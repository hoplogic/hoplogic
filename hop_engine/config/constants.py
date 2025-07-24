from enum import Enum, auto
from typing import Union, Dict, List, Any, Literal

JsonValue = Union[
    None,
    bool,
    int,
    float,
    str,
    List[Any],
    Dict[str, Any],
    Literal["True", "False", "Uncertain"],
]


class HopStatus(Enum):
    OK = auto()
    LACK_OF_INFO = auto()
    UNCERTAIN = auto()
    FAIL = auto()

    def __init__(self, value):
        self._value_ = value

    @property
    def description(self):
        """
        返回状态的详细描述。
        """
        descriptions = {
            HopStatus.OK: "核验成功，即给定的结论正确",
            HopStatus.LACK_OF_INFO: "核验缺乏信息，因为缺乏关键信息所以无法得出核验明确结果",
            HopStatus.UNCERTAIN: "核验不确定，无法得出核验结果，非缺乏信息导致",
            HopStatus.FAIL: "核验失败，即结论错误或者格式错误",
        }
        return descriptions.get(self, "未知状态")


# 越狱防护相关特殊标记
SAFETY_TOKENS = [
    "<|im_start|>",
    "<|im_end|>",
    "<|im_sep|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<<SYS>>",
    "[/INST]",
]

# 工具域定义 TODO: 先固定使用，后续可以根据用户配置来实现
TOOL_DOMAINS = {
    "all": [
        "cmd_par_tool",
        "install_pack_tool",
        "chmod_baseline_tool",
        "get_mail_doamin_cti",
    ],
    "security": [
        "cmd_par_tool",
        "install_pack_tool",
        "chmod_baseline_tool",
        "get_mail_doamin_cti",
    ],
}

from hop_engine.config.model_config import ModelConfig
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.status_recorder import GLOBAL_STATS, function_monitor
from hop_engine.utils.utils import LoggerUtils
import os
import json
import ast

run_config = ModelConfig.from_yaml(
    "system", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)
verify_config = ModelConfig.from_yaml(
    "verify", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)

# 创建处理器实例
hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)
logger = LoggerUtils.get_logger()

FIND_FACT_PROMPT = """找出以下内容中涉及到的所有事实性声明，并整理其表述后给出。

* 给出的每条表述必须 **仅包含一个知识点**，包含多个知识点的声明应当分开给出。
* 给出的每条表述都必须是完整且独立的，即对于任一条给出的表述，都必须能直接通过网络搜索对其内容的真实性进行核验。
* 给出的表述中不应该出现代词，如果有代词应当从内容中找到相应内容替换之。
* 必须保持原语种。
* 将结果整理成一个python list给出。

**内容：**
%s

**给出的表述：**

"""

VERIFY_FACT_PROMPT = """判断给定描述是否包含非事实性陈述。 

**非事实性陈述**包含以下类型的陈述：
* 无法通过信息搜索核验其真实性的陈述
* 补充说明性的文本
* 涉及未来的推测性陈述

输出要求：如果包含非事实性陈述则回答'无效陈述'；否则回答'有效陈述'。

**描述：**
%s

**判断：**

"""

REMOVE_REPEAT_PROMPT = """以下list中包含了若干条陈述，其中可能有一些陈述是重复的，如果有则去掉重复的陈述；如果没有则直接返回原始list。
必须保持原语种。将结果整理成一个python list给出。
**直接给出list结果。**

**list：**
%s

**去重结果：**

"""

@function_monitor
def fact_extraction(input_text):
    """
    事实提取函数：从给定文本中提取所有事实性声明
    
    Args:
        input_text: 需要提取事实的文本内容
        
    Returns:
        list: 提取出的事实性声明列表
    """
    try:
        # 步骤1：文本分割
        text_list = input_text.split('\n\n') if '\n\n' in input_text else [input_text]
        
        # 步骤2：提取事实
        extracted_facts = []
        for para in text_list:
            if para.strip():  # 跳过空段落
                fact_res = hop_proc.hop_get(
                    task=FIND_FACT_PROMPT % para,
                    context="",
                    verifier=None
                )
                extracted_facts.append(fact_res)
        
        # 步骤3：解析提取结果
        list_of_facts = []
        for fs in extracted_facts:
            try:
                # 清理和解析LLM返回的结果
                content = str(fs).strip('`').replace('python', '', 1).strip()
                facts = ast.literal_eval(content)
                if isinstance(facts, list):
                    list_of_facts.extend(facts)
            except (ValueError, SyntaxError) as e:
                logger.warning(f"解析事实列表失败: {e}")
                continue
        
        # 步骤4：过滤无效陈述
        valid_facts = []
        for fact in list_of_facts:
            if fact.strip():  # 跳过空字符串
                verify_res = hop_proc.hop_get(
                    task=VERIFY_FACT_PROMPT % fact,
                    context="",
                    verifier=None
                )
                if '有效陈述' in str(verify_res):
                    valid_facts.append(fact)
        
        # 步骤5：去重
        if valid_facts:
            no_repeat_facts = hop_proc.hop_get(
                task=REMOVE_REPEAT_PROMPT % str(valid_facts),
                context="",
                verifier=None
            )
            try:
                content = str(no_repeat_facts).strip('`').replace('python', '', 1).strip()
                final_facts = ast.literal_eval(content)
                if isinstance(final_facts, list):
                    return final_facts
            except (ValueError, SyntaxError) as e:
                logger.warning(f"解析去重结果失败: {e}")
                return valid_facts
        
        return valid_facts
        
    except Exception as e:
        logger.error(f"事实提取过程中发生错误: {e}")
        return []

# 使用示例
def print_hop_metrics(stats, func_name, is_global=False):
    """打印HOP指标统计"""
    # 获取算子级统计
    operator_stats = stats.get_operator_stats()
    logger.info("\nHOP算子执行统计:")
    for op_name, data in operator_stats.items():
        logger.info(f"「{op_name}」调用成功率: {data['success_rate']*100:.1f}%")
        logger.info(f"平均耗时: {data['avg_time']:.3f}s | 最大耗时: {data['max_time']:.3f}s")
        logger.info(f"累计重试次数: {data['total_retries']}次")

    # 获取函数级统计
    if is_global:
        func_stats = stats.get_function_stats(func_name)
        logger.info("\n处置函数统计:")
        logger.info(f"总处置次数: {func_stats.get('calls', 0)}")
        logger.info(f"HOP函数完成率: {func_stats.get('success_rate', 0.0) * 100:.1f}%")
        logger.info(f"平均处置耗时: {func_stats.get('avg_time',0):.3f}s")

if __name__ == "__main__":
    # 指标清空，开始统计
    GLOBAL_STATS.reset()
    
    # 测试数据
    test_cases = [
        {
            "text": "北京是中国的首都，上海是中国最大的城市，广州位于广东省。2025年中国的GDP增长率预计为5%左右。",
            "expected_facts": [
                "北京是中国的首都",
                "上海是中国最大的城市", 
                "广州位于广东省"
            ]
        },
        {
            "text": "苹果公司成立于1976年，总部位于美国加利福尼亚州库比蒂诺。iPhone 15系列于2023年9月发布，起售价为799美元。未来苹果手机的价格可能会上涨。",
            "expected_facts": [
                "苹果公司成立于1976年",
                "苹果公司总部位于美国加利福尼亚州库比蒂诺",
                "iPhone 15系列于2023年9月发布",
                "iPhone 15系列起售价为799美元"
            ]
        },
        {
            "text": "清华大学创建于1911年，位于中国北京市海淀区。北京大学成立于1898年，是中国最早的国立综合性大学。有些人认为清华大学比北京大学更有名，但是还有一些人更向往北京大学。",
            "expected_facts": [
                "清华大学创建于1911年",
                "清华大学位于中国北京市海淀区",
                "北京大学成立于1898年",
                "北京大学是中国最早的国立综合性大学"
            ]
        }
    ]
    
    total_samples = 0
    for case in test_cases:
        total_samples += 1
        text = case["text"]
        logger.info(f"=========处理第{total_samples}个样本:===========")
        logger.info(f"原文本: {text}")
        
        # 执行事实提取
        result, current_stats = fact_extraction(text)
        
        logger.info(f"提取到的事实:")
        for i, fact in enumerate(result, 1):
            logger.info(f"{i}. {fact}")
        
        # 会话级指标
        print_hop_metrics(current_stats, "fact_extraction")
    
    # 全局指标
    logger.info(f"=========全局结果统计:===========")
    print_hop_metrics(GLOBAL_STATS, "fact_extraction", True)

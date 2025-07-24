from hop_engine.config.constants import HopStatus
from hop_engine.config.model_config import ModelConfig
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.status_recorder import GLOBAL_STATS, function_monitor
from hop_engine.validators.result_validators import multation_verifier, plus_verifier
from hop_engine.utils.utils import LoggerUtils
import os
import json

run_config = ModelConfig.from_yaml(
    "system", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)
verify_config = ModelConfig.from_yaml(
    "verify", file_path=os.path.join(os.path.dirname(__file__), "settings.yaml")
)

logger = LoggerUtils.get_logger()

# 创建处理器实例
hop_proc = HopProc(
    run_model_config=run_config,
    verify_model_config=verify_config,
    hop_retry=3,
    debug=True,
)

# 保留原始日志处理函数
@function_monitor
def big_number_mult(input_data):
    try:
        subject_structure = {
            "result": (str, ...),  # key1 是字符串类型
        }
        num1 = input_data.get("number1")
        num2 = input_data.get("number2")
        num2_str = str(num2)
        finally_result = 0
        for i in range(len(num2_str)):
            curr_mult_input_data = {"number1": num1, "number2": int(num2_str[::-1][i])}
            mul_task = """您是一个专业的数学计算器，请计算number1与number2的乘法结果，结果以JSON格式返回,输出格式：\n{{"result": str(number1 * number2 的乘法结果)}}"""
            mul_status, mul_model_result = hop_proc.hop_get(
                task=mul_task,
                context=json.dumps(curr_mult_input_data),
                return_format=subject_structure,
                verifier=multation_verifier,
            )

            if mul_status == HopStatus.FAIL:
                return mul_model_result
            else:
                # 计算加法
                curr_mul_result = json.loads(str(mul_model_result))["result"] + "0" * i
                curr_plus_input_data = {
                    "number1": finally_result,
                    "number2": int(curr_mul_result),
                }
                plus_task = """您是一个专业的数学计算器，请计算number1与number2的加法结果，结果以JSON格式返回,输出格式：\n{{"result": str(number1+number2 的加法结果)}}"""
                plus_status, plus_model_result = hop_proc.hop_get(
                    task=plus_task,
                    context=json.dumps(curr_plus_input_data),
                    return_format=subject_structure,
                    verifier=plus_verifier,
                )
                if plus_status == HopStatus.FAIL:
                    return plus_verifier
                else:
                    finally_result = int(json.loads(str(plus_model_result))["result"])
        return finally_result
    except Exception as e:
        return "执行中断，存在失败算子"


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
    total_samples = 0
    correct_predictions = 0
    data = [{"input": {"number1": 110, "number2": 220}, "label": 24200}]
    for item in data:
        total_samples = total_samples + 1
        input_data = item["input"]
        label = item["label"]
        logger.info(f"=========处理第{total_samples}个样本:===========")
        result, current_stats = big_number_mult(input_data)
        print_hop_metrics(current_stats, "big_number_mult")  # 新增统计输出
        logger.info(f"最终乘法结果: {result}")
        if result == label:
            correct_predictions = correct_predictions + 1

    func_stats = GLOBAL_STATS.get_function_stats("big_number_mult")
    completion_rate = 1 - (float(func_stats["error_rate"]) if func_stats else 0)
    accuracy = (
        correct_predictions / (total_samples * completion_rate)
        if completion_rate > 0
        else 0
    )

    logger.info(f"=========全局结果统计:===========")
    logger.info(f"完成率: {completion_rate:.2%}")
    logger.info(f"准确率: {accuracy:.2%}")
    print_hop_metrics(GLOBAL_STATS, "big_number_mult", True)  # 新增统计输出

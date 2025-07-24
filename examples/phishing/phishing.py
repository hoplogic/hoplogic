from hop_engine.config.model_config import ModelConfig
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.status_recorder import GLOBAL_STATS, function_monitor
from hop_engine.validators.result_validators import (
    phishing_judge_verifier,
    tool_use_verifier,
)
from hop_engine.config.constants import HopStatus
from hop_engine.utils.utils import LoggerUtils
import os
import json

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

# 保留原始日志处理函数
@function_monitor
def hop_phishing(input_log):
    try:
        explanation_description = "对于结果输出的解释，在最后列出用于判断的关键词，要求关键词必须出自【上下文】部分，以'关键词有**'开头，用'**'结尾，如果有多个关键词用','分割。输出格式为'explanation。关键词有**keyword_1,keyword_2**'"
        if "subject" not in input_log:
            return "无法定性:subject缺失"

        subject = input_log.get("subject")
        from_domain = input_log.get("from_domain")
        to_job = input_log.get("job")
        logger.info(subject)

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

        subject_judge_condition = (
            "根据上下文语境判断邮件主题是否与概念“账号、薪资、个税”匹配，如果匹配则返回True，不匹配返回False，无法确定返回Uncertain。"
        )
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

        job_judge_condition = (
            "根据语境判断收到的邮件主题内容与收件人岗位职责是否严格相关，相关则返回True，不相关则返回False，无法确定则返回Uncertain。"
        )
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

        if subject_condition.lower() == "true":
            return "钓鱼邮件"
        if subject_condition.lower() == "uncertain":
            return "判断无法确定（uncertain）"
        return "钓鱼邮件"

    except Exception as e:
        return f"执行中断，存在失败算子：{str(e)}"


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
        print(func_stats)
        logger.info("\n处置函数统计:")
        logger.info(f"总处置次数: {func_stats.get('calls', 0)}")
        logger.info(f"HOP函数完成率: {func_stats.get('success_rate', 0.0) * 100:.1f}%")
        logger.info(f"HOP函数不确定占比: {func_stats.get('uncertain_rate', 0.0) * 100:.1f}%")
        logger.info(f"平均处置耗时: {func_stats.get('avg_time',0):.3f}s")


if __name__ == "__main__":
    # 指标清空，开始统计
    GLOBAL_STATS.reset()

    phishing_json_list = [
        {
            "subject": "您的个税申报被退回，请查看原因并重新提交",
            "from_domain": "example.com",
            "job": "运营",
            "label": "钓鱼邮件",
        }
    ]

    total_samples = 0
    for input_data in phishing_json_list:
        total_samples = total_samples + 1
        label = input_data["label"]
        logger.info(f"=========处理第{total_samples}个样本:===========")
        result, current_stats = hop_phishing(input_data)
        logger.info(f"最终研判: {result}")
        logger.info(f"label: {label}")
        # 会话级指标
        print_hop_metrics(current_stats, "hop_phishing")
    # 全局指标
    logger.info(f"=========全局结果统计:===========")
    print_hop_metrics(GLOBAL_STATS, "hop_phishing", True)
    logger.info(f"=========业务指标结果统计:===========")

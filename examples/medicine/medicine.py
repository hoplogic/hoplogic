from hop_engine.config.model_config import ModelConfig
from hop_engine.processors.hop_processor import HopProc
from hop_engine.utils.status_recorder import GLOBAL_STATS, function_monitor
from hop_engine.validators.result_validators import (
    reverse_verify,
)
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


def hop_get(sub_fee_item, item_inf):
    if item_inf:
        llm_create_item = """
你是一个医疗专家，【{fee_item}】是一个收费项目。请输出【{fee_item}】的详细信息。详细内容需要包含以下三个方面：
适用范围：说明该收费项目的适用范围，包括适用的患者群体、适用的医疗场景或治疗类型。
标准操作：描述该收费项目的标准操作步骤和实施方式。如果项目包含样本采集在提取标准操作时不考虑通用的样本采集类的相关的操作，比如样本采集，质控，人工或仪器测定，审核结果，录入实验室信息系统或人工登记，发送报告；按规定处理废弃物；接受临床相关咨询等
除外内容：明确哪些项目或服务不能与该项目同时收费，以避免重复收费或费用叠加。

该项目详情参考项目内涵描述：
{item_inf}
针对适用范围与标准操作给出详细的描述通过1，2，3...列出相关详细信息。最终输出的格式是字符串string。
请确保信息准确、全面，并参考相关法规或行业规范进行说明。
    """.format(
            fee_item=sub_fee_item, item_inf=item_inf
        )
    else:
        llm_create_item = """
你是一个医疗专家，【{fee_item}】是一个收费项目。请输出【{fee_item}】的详细信息。详细内容需要包含以下三个方面：
适用范围：说明该收费项目的适用范围，包括适用的患者群体、适用的医疗场景或治疗类型。
标准操作：描述该收费项目的标准操作流程和实施方式，包括实施条件、操作步骤以及技术要求。如果项目包含样本采集在提取标准操作时不考虑通用的样本采集类的相关的操作，比如样本采集，质控，人工或仪器测定，审核结果，录入实验室信息系统或人工登记，发送报告；按规定处理废弃物；接受临床相关咨询等
除外内容：明确哪些项目或服务不能与该项目同时收费，以避免重复收费或费用叠加。

针对适用范围与标准操作给出详细的描述通过1，2，3...列出相关详细信息。最终输出的格式是字符串string。
请确保信息准确、全面，并参考相关法规或行业规范进行说明。""".format(
            fee_item=sub_fee_item
        )

    get_task = llm_create_item
    status, result = hop_proc.hop_get(
        task=get_task,
        context="",
        verifier=reverse_verify,
    )
    return result


def hop_judge(first, second, tem):
    error_count = 0
    llm_create_item = """
你是一个医疗专家，以下是一个病人在治疗期间的两个收费项目关于【{tem}】的详情：
1 {first},
2 {second}。
判断这两个收费项在【{tem}】是否有重复的情况。返回True表示有重叠，返回False表示没有重叠。reason表示判断原因，不超过50个字。
""".format(
        first=first, second=second, tem=tem
    )
    verify_flag = False
    while not verify_flag and error_count < 3:
        subject_structure = {
            "result": (bool, ...),
            "reason": (str, ...),
        }
        status, result = hop_proc.hop_get(
            task=llm_create_item,
            context="",
            return_format=subject_structure,
            verifier=None,
        )
        logger.info("msg:======hop_judge原始结果====")
        logger.info(result)
        hop_judge_verification_result = hop_judge_verification(
            first, second, tem, result
        )
        logger.info("msg:======hop_judge_verification====")
        logger.info(hop_judge_verification_result)
        # 如核验不通过
        if "核验通过" in hop_judge_verification_result:
            verify_flag = True
        else:
            error_count += 1
            logger.info("msg:======核验不通过重新判断====")
    return result


def hop_judge(first, second, tem):
    error_count = 0
    llm_create_item = """
你是一个医疗专家，以下是一个病人在治疗期间的两个收费项目关于【{tem}】的详情：
1 {first},
2 {second}。
判断这两个收费项在【{tem}】是否有重复的情况。返回True表示有重叠，返回False表示没有重叠。reason表示判断原因，不超过50个字。
""".format(
        first=first, second=second, tem=tem
    )
    verify_flag = False
    while not verify_flag and error_count < 3:
        subject_structure = {
            "result": (bool, ...),
            "reason": (str, ...),
        }
        status, result = hop_proc.hop_get(
            task=llm_create_item,
            context="",
            return_format=subject_structure,
            verifier=None,
        )
        logger.info("msg:======hop_judge原始结果====")
        logger.info(result)
        hop_judge_verification_result = hop_judge_verification(
            first, second, tem, result
        )
        logger.info("msg:======hop_judge_verification====")
        logger.info(hop_judge_verification_result)
        # 如核验不通过
        if "核验通过" in hop_judge_verification_result:
            verify_flag = True
        else:
            error_count += 1
            logger.info("msg:======核验不通过重新判断====")
    return result


def hop_judge_verification(first, second, tem, hop_juge_result):
    llm_create_item = """
# 要求：
作为验证专家，需要核验结果是否正确。验证步骤：
1 确定结论表示的意义
2 根据结论的原因分析其是否符合逻辑或是符合事实。
强调：只需要输出结果，不需要进行解释
# 示范例子1：
【核验内容】
{{'cmd': '/usr/libexec/path_helper -s','cmd_condition':False}} 
【输入】
'cmd' '/usr/libexec/path_helper -s'，核验的任务是判断cmd是否赋予文件可执行权限
【结果】：
{{"result":"核验通过","reason":"cmd命令行为'/usr/libexec/path_helper -s',执行代码后的变量cmd_condition为False表示cmd命令行并没有赋予文件可执行权限,而真实的cmd命令行'/usr/libexec/path_helper -s'确实没有赋予文件可执行权限"}}

# 示范例子2：
【核验内容】
{{'cmd': '/usr/libexec/path_helper -s','cmd_condition':True}}
【输入】
'cmd' '/usr/libexec/path_helper -s'，核验的任务是判断cmd是否赋予文件可执行权限
【结果】：
{{"result":"核验不通过","reason":"执行代码后的变量cmd_condition为True表示cmd命令行赋予文件可执行权限,而真实的cmd命令行'/usr/libexec/path_helper -s'没有赋予文件可执行权限,执行代码行的结果与真实情况相矛盾。"}}
# 推理
【核验内容】
{hop_juge_result}
【输入】
1 {first},
2 {second}。
核验任务是判断核验内容是否正确。
【结果】
""".format(
        first=first, second=second, tem=tem, hop_juge_result=hop_juge_result
    )
    status, result = hop_proc.hop_get(
        task=llm_create_item,
        context="",
        verifier=None,
    )
    return result


def NLP_core_veri(curr_entity, fee_item, sub_item_info):
    # 核验是
    curr_prompt = """
    您是一个医疗专家，请核验一下{curr_entity}是否是收费项目的{fee_item}的{sub_item_info},最终只需要给True or False.
    """.format(
        curr_entity=curr_entity, fee_item=fee_item, sub_item_info=sub_item_info
    )
    status, veri_result = hop_proc.hop_judge(
        task=curr_prompt,
        context="",
        verifier=None,
    )

    return veri_result


def hop_entity_extract(fee_item, item_info):
    logger.info("MSG:=====hop实体提取====")
    task = """
     ## 角色设置
    
    你是一个医疗专家，同时也是一个实体提取专家。
    
    ## 要求：
    根据收费项目的详情提取相应的具体信息,返回list形式的结果，列表一定不能为空。如果提取 标准操作 的实体不需要提取类似核对患者信息、处理废弃物等通用的标准操作步骤。
    """
    llm_operator = """    
    下面有一个示例可以参考：
    【收费项目详情】
    ### 特级护理详细信息
    
    #### 1. 适用范围
    - **重症患者**：包括但不限于重症监护室（ICU）内的患者、术后恢复期患者、严重创伤或烧伤患者、多器官功能衰竭患者等。
    - **特殊需求患者**：需要持续监测生命体征、特殊治疗和护理的患者，如使用呼吸机、心电监护、血液透析等设备的患者。
    
    
    #### 2. 标准操作
    - **24小时专人护理**：由具有丰富经验的护士提供24小时不间断的护理服务。
    - **生命体征监测**：持续监测患者的血压、心率、呼吸、血氧饱和度等生命体征。
    - **药物管理**：按时按量给药，确保药物治疗的准确性和安全性。
    - **病情记录**：详细记录患者的病情变化、治疗措施及效果，及时与医生沟通。
    - **生活护理**：协助患者进行基本的生活护理，如翻身、擦浴、喂食等。
    - **心理支持**：提供必要的心理支持和安慰，帮助患者保持积极的心态。
    
    #### 3. 除外内容
    - **非医疗费用**：如个人物品损坏赔偿、私人护理用品等。
    - **非必要检查费用**：未经医生批准的额外检查费用。
    - **非必要治疗费用**：未经医生批准的额外治疗费用。
    - **非住院期间费用**：患者出院后的康复费用、随访费用等。
    
    【需要提取的实体信息】
    适用范围
    【结果】
    ["重症监护室（ICU）内的患者","术后恢复期患者","严重创伤或烧伤患者","多器官功能衰竭患者","需要持续监测生命体征的患者","需要特殊治疗和护理的患者","使用呼吸机、心电监护、血液透析等设备的患者 ]
    
    ## 推理
    【收费项目详情】
    {fee_item_info}
    【需要提取的实体信息】
    {sub_item_info}
    【结果】
    """.format(
        fee_item_info=fee_item, sub_item_info=item_info
    )

    subject_structure = {
        "result": (list, ...),  # 表示结果是一个列表，不能为空
    }

    status, llm_operator_result = hop_proc.hop_get(
        task=task,
        context=llm_operator,
        return_format=subject_structure,
        verifier=None,
    )
    llm_operator_result = json.loads(llm_operator_result)
    llm_result_list = llm_operator_result.get("result")

    # for curr_entity in llm_result_list:
    #     logger.info("MSG:===当前抽取实体核验结果===")
    #     curr_veri_result = NLP_core_veri(curr_entity, fee_item, item_info)
    return llm_result_list


@function_monitor
def double_charge(input_log):
    try:
        tem_info = ["适用范围", "标准操作"]
        log_info = ""
        fee_item = list(input_log.keys())
        fee_item = fee_item[:3]
        fee_info_knowledge = {}
        for first_num in range(len(fee_item) - 1):
            for second_num in range(first_num + 1, len(fee_item)):
                curr_item_pair_result = {}
                logger.info(
                    "MSG:====针对项目【{}】与收费项目【{}】开始重复计费判断===".format(
                        fee_item[first_num], fee_item[second_num]
                    )
                )
                log_info += (
                    "MSG:====针对项目【{}】与收费项目【{}】开始重复计费判断===".format(
                        fee_item[first_num], fee_item[second_num]
                    )
                    + "\n"
                )
                first_item_inf = input_log.get(fee_item[first_num])
                print("MSG:======first_item_inf===")
                print(first_item_inf)
                second_item_inf = input_log.get(fee_item[second_num])
                print("MSG:======second_item_inf===")
                print(second_item_inf)
                # 获取项目详情
                # hop_get获取第一个收费项目详情
                if fee_item[first_num] in fee_info_knowledge:
                    first_info = fee_info_knowledge.get(fee_item[first_num])

                else:
                    first_info = hop_get(fee_item[first_num], first_item_inf)
                    print("MSG:====first_info===")
                    print(first_info)
                    fee_info_knowledge[fee_item[first_num]] = first_info
                print("MSG:=====各收费项目项目内涵=====")
                logger.info("MSG:=====各收费项目项目内涵=====")
                logger.info("msg:===first_info====")
                logger.info(first_info)
                log_info += "msg:===first_info====" + "\n"
                log_info += str(first_info) + "\n"
                # 第二个收费项目详情
                if fee_item[second_num] in fee_info_knowledge:
                    second_info = fee_info_knowledge.get(fee_item[second_num])
                else:
                    second_info = hop_get(fee_item[second_num], second_item_inf)
                    fee_info_knowledge[fee_item[second_num]] = second_info
                logger.info("msg:===second_info====")
                logger.info(second_info)
                log_info += "msg:===second_info====" + "\n"
                log_info += str(second_info) + "\n"
                # 判断除外项
                # 判断两个收费项目除外内容判断
                logger.info("MSG:=====各收费项目除外内容分析=====")
                log_info += "MSG:=====各收费项目除外内容分析=====" + "\n"
                first_curr_chuwai = first_info.split("除外内容")[-1]
                second_curr_chuwai = second_info.split("除外内容")[-1]
                chuwai_prompt = """
                你是一个医疗专家。收费项目的除外内容表示不能与该收费项目一起收费的项目。你需要判断一个收费项目是否属于别外一个收费项目的除外内外。
                第一个收费项目【{first_fee_item}】的除外内容为：
                {first_curr_chuwai}
                第二个收费项目【{second_fee_item}】的除外内容为：
                {second_curr_chuwai}
                判断第一个收费项目【{first_fee_item}】是否属于第二个收费项目【{second_fee_item}】的除外内容或第二个收费项目【{second_fee_item}】是否属于第一个收费项目【{first_fee_item}】的除外内容。如果是返回True,如果否返回False,reason表示判断原因，不超过50个字。
                """.format(
                    first_fee_item=fee_item[first_num],
                    second_fee_item=fee_item[second_num],
                    first_curr_chuwai=first_curr_chuwai,
                    second_curr_chuwai=second_curr_chuwai,
                )

                subject_structure = {
                    "result": (bool, ...),
                    "reason": (str, ...),
                }
                chuwai_status, chuwai_result = hop_proc.hop_get(
                    task=chuwai_prompt,
                    context="",
                    return_format=subject_structure,
                    verifier=reverse_verify,
                )
                logger.info("msg:===除外内容信息LLM判断结果====")
                logger.info(
                    "收费项目【{first_fee}】与收费项目【{second_fee}】除外内容判断结果:".format(
                        first_fee=fee_item[first_num],
                        second_fee=fee_item[second_num],
                    )
                )
                logger.info(chuwai_result)
                log_info += "msg:===除外内容信息LLM判断结果====" + "\n"
                log_info += (
                    "收费项目【{first_fee}】与收费项目【{second_fee}】除外内容判断结果:".format(
                        first_fee=fee_item[first_num],
                        second_fee=fee_item[second_num],
                    )
                    + "\n"
                )
                log_info += chuwai_result + "\n"

                if not chuwai_status:
                    logger.info("msg:===除外内容信息====")
                    logger.info(
                        "收费项目【{first_fee}】与收费项目【{second_fee}】除外内容判断没通过核验。".format(
                            first_fee=fee_item[first_num],
                            second_fee=fee_item[second_num],
                        )
                    )
                    log_info += "msg:===除外内容信息====" + "\n"
                    log_info += (
                        "收费项目【{first_fee}】与收费项目【{second_fee}】除外内容判断没通过核验。".format(
                            first_fee=fee_item[first_num],
                            second_fee=fee_item[second_num],
                        )
                        + "\n"
                    )
                    curr_item_pair_result = {
                        "result": "Uncertain",
                        "reason": "收费项目【{first_fee}】与收费项目【{second_fee}】缺少明确的项目内涵".format(
                            first_fee=fee_item[first_num],
                            second_fee=fee_item[second_num],
                        ),
                    }
                else:
                    if "true" in chuwai_result.lower():

                        logger.info("msg:===除外内容信息====")
                        logger.info(
                            "收费项目【{first_fee}】与收费项目【{second_fee}】之间除外项表示这两项目收费不能重复收费".format(
                                first_fee=fee_item[first_num],
                                second_fee=fee_item[second_num],
                            )
                        )
                        log_info += "msg:===除外内容信息====" + "\n"
                        log_info += (
                            "收费项目【{first_fee}】与收费项目【{second_fee}】之间除外项表示这两项目收费不能重复收费".format(
                                first_fee=fee_item[first_num],
                                second_fee=fee_item[second_num],
                            )
                            + "\n"
                        )
                        curr_item_pair_result = {
                            "result": "True",
                            "reason": "收费项目【{first_fee}】与收费项目【{second_fee}】之间除外项表示这两项目收费不能重复收费".format(
                                first_fee=fee_item[first_num],
                                second_fee=fee_item[second_num],
                            ),
                        }
                        return {
                            "result": "True",
                            "log_info": log_info,
                            "fee_info_knowledge": fee_info_knowledge,
                        }
                        # continue
                    else:
                        # 如果两个收费项目均是测定项目且不同则直接判定不是重复收费
                        if (
                            "样本" in first_item_inf
                            and "样本" in second_item_inf
                            and fee_item[first_num] != fee_item[second_num]
                        ):
                            curr_item_pair_result = {
                                "result": "False",
                                "reason": "收费项目【{first_fee}】与收费项目【{second_fee}】在均属于样本检查类项目不属于重复收费。".format(
                                    first_fee=fee_item[first_num],
                                    second_fee=fee_item[second_num],
                                ),
                            }
                            logger.info(curr_item_pair_result)
                            log_info += str(curr_item_pair_result) + "\n"
                        else:
                            first_dic = {}
                            logger.info("msg:===除外内容无重叠====")
                            log_info += (
                                "收费项目【{first_fee}】与收费项目【{second_fee}】的除外内容表示两个项目无重复".format(
                                    first_fee=fee_item[first_num],
                                    second_fee=fee_item[second_num],
                                )
                                + "\n"
                            )
                            # 判断两个收费项目的类型是否是样本采集

                            # 如果适用范围不重叠
                            for tem in tem_info:
                                logger.info("MSG:=====当前处理阶段：{}====".format(tem))
                                first_curr_tem = hop_entity_extract(first_info, tem)
                                logger.info(
                                    "msg:====第一个收费项目提取的{tem}相应实体===".format(tem=tem)
                                )
                                logger.info(first_curr_tem)
                                log_info += (
                                    "msg:====第一个收费项目提取的{tem}相应实体===".format(tem=tem)
                                    + "\n"
                                )
                                log_info += str(first_curr_tem) + "\n"
                                first_dic[tem] = first_curr_tem
                                second_curr_tem = hop_entity_extract(second_info, tem)
                                logger.info(
                                    "msg:====第二个收费项目提取的{tem}===".format(tem=tem)
                                )
                                logger.info(second_curr_tem)
                                log_info += (
                                    "msg:====第二个收费项目提取的{tem}===".format(tem=tem) + "\n"
                                )
                                log_info += str(second_curr_tem) + "\n"
                                # 判断first与second的是否有重合
                                if first_curr_tem and second_curr_tem:
                                    curr_judge_result = hop_judge(
                                        first_curr_tem, second_curr_tem, tem
                                    )
                                else:
                                    return {
                                        "result": "uncertain",
                                        "log_info": log_info,
                                        "fee_info_knowledge": fee_info_knowledge,
                                    }
                                logger.info("msg:====hop_judge====")
                                logger.info(curr_judge_result)
                                log_info += "msg:====hop_judge====" + "\n"
                                log_info += str(curr_judge_result) + "\n"
                                # 如果是适用范围的话
                                if (
                                    tem == "适用范围"
                                    and "true" in curr_judge_result.lower()
                                ):
                                    continue
                                elif tem == "适用范围":
                                    curr_item_pair_result = {
                                        "result": "False",
                                        "reason": "收费项目【{first_fee}】与收费项目【{second_fee}】在适用范围没有重叠。".format(
                                            first_fee=fee_item[first_num],
                                            second_fee=fee_item[second_num],
                                        ),
                                    }
                                    logger.info(curr_item_pair_result)
                                    log_info += str(curr_item_pair_result) + "\n"

                                else:
                                    if "true" in curr_judge_result.lower():
                                        return {
                                            "result": "True",
                                            "log_info": log_info,
                                            "fee_info_knowledge": fee_info_knowledge,
                                        }

                logger.info(
                    "MSG:====针对项目【{}】与收费项目【{}】的结果===".format(
                        fee_item[first_num], fee_item[second_num]
                    )
                )
                logger.info(curr_item_pair_result)
                log_info += (
                    "MSG:====针对项目【{}】与收费项目【{}】的结果===".format(
                        fee_item[first_num], fee_item[second_num]
                    )
                    + "\n"
                )
                log_info += str(curr_item_pair_result) + "\n"
            if not fee_info_knowledge:
                fee_info_knowledge = input_log

            return {
                "result": "False",
                "log_info": log_info,
                "fee_info_knowledge": fee_info_knowledge,
            }
    except Exception as e:
        return {"result": str(e), "log_info": "执行中断，存在失败算子"}


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
    raw_data = [
        {
            "input_log": {
                "显微镜下断指再植术": "\n\n显微镜下断指再植术详细信息如下：  \n**适用范围**：  \n1. 适用于因外伤导致完全或不完全断指（包括手指完全离断或部分离断伴血管神经损伤）的患者。  \n2. 适用于断指再植手术中需显微镜下吻合血管、神经的复杂病例，如血管口径细小（直径＜3mm）、神经损伤需精准缝合的情况。  \n3. 适用于急诊或限期手术场景，需在断指后6-8小时内实施再植手术以提高存活率。  \n\n**标准操作**：  \n1. **术前准备**：消毒铺巾，安置气囊止血带控制术区出血。  \n2. **清创探查**：彻底清创创面，探查断指残端血管、神经、肌腱及骨关节损伤范围。  \n3. **骨与关节复位固定**：复位骨折端并采用克氏针、微型钢板或髓内钉固定，恢复骨骼连续性。  \n4. **肌腱神经缝合**：显微镜下精准缝合屈伸肌腱及受损神经束膜。  \n5. **血管吻合**：显微镜下吻合指动脉及伴行静脉，确保血流通畅，必要时采用血管移植桥接缺损。  \n6. **术后处理**：松止血带观察血供，关闭创口并加压包扎，术后监测再植指体血运。  \n\n**除外内容**：  \n1. 组织移植术（如皮瓣移植、骨移植等）不可与本项目同时收费。  \n2. 同一手术部位的其他显微外科操作（如单纯肌腱修复术、血管结扎术）不得叠加收费。  \n3. 术后护理（如抗凝治疗、高压氧治疗）、影像学检查（如血管超声、X线）及康复治疗需单独计费。  \n\n依据《医疗服务项目规范》及显微外科手术指南，本项目以显微操作为核心，强调血管神经的精准修复，需严格区分附加操作以避免重复收费。",
                "小动脉吻合术": "1. 适用范围：  \n1.1 外伤性指、趾动脉断裂或缺损患者，需进行血管重建以恢复肢体血供的情况。  \n1.2 缺血性疾病（如血栓闭塞性脉管炎、动脉硬化闭塞症）导致的小动脉缺损修复，需行血管旁路手术的患者。  \n1.3 肿瘤切除术后或先天性血管畸形矫正所需的指、趾动脉重建场景。  \n\n2. 标准操作：  \n2.1 术前消毒铺巾后，于目标动脉部位作局部切口，分离皮下组织暴露小动脉。  \n2.2 游离待吻合段小动脉，使用静脉肝素溶液局部抗凝处理，防止术中血栓形成。  \n2.3 阻断血管近远端血流，采用显微外科技术对血管断端进行端端或端侧吻合，缝合采用7-0至9-0无损伤缝线。  \n2.4 术毕彻底止血并用生理盐水冲洗创腔，放置引流条后逐层关闭切口，加压包扎。  \n\n3. 除外内容：  \n3.1 不得与同部位大动脉吻合术（如桡动脉、足背动脉）或血管移植术同时收费。  \n3.2 若包含在复合性手外伤修复术（如肌腱、神经同步修复）中，则不可单独计费。  \n3.3 术中使用的血管内超声或荧光造影等实时影像评估项目需另行编码收费。  \n\n（注：内容依据《医疗服务项目内涵与医保支付标准》及相关显微外科操作规范整理，确保临床操作合规性与收费合理性。）",
            },
            "result": "True",
        }
    ]

    for item in raw_data:
        input_data = item["input_log"]
        label = item["result"]
        result, current_stats = double_charge(input_data)
        logger.info(f"事实label: {label}")
        logger.info(f"最终研判: {result}")
        # 会话级指标
        print_hop_metrics(current_stats, "double_charge")
    # 全局指标
    logger.info(f"=========全局结果统计:===========")
    print_hop_metrics(GLOBAL_STATS, "double_charge", True)

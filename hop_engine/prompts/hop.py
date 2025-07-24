HOP_GET_PROMPT = """
## 要求
你是一个知识抽取的agent，请根据要求帮我从上下文中抽取知识。并返回结果。如果有返回格式要求，请严格遵循。请一步一步思考。

## 返回格式schema,请注意输出结果符合json格式要求
{return_format}

## 相关信息
【上下文】：{context}
【任务要求】：{task}

## 研判
【结果】：
"""

HOP_JUDGE_PROMPT = """
## 要求
你是一个研判知识的agent，请帮我研判一下下面的知识。如果有返回格式要求，请严格遵循。请一步一步思考。

## 返回格式schema,请注意输出结果符合json格式要求
{return_format}

最终结果必须是以下三种情况之一：
   - 如果条件判断为真，请返回'True'；
   - 如果条件判断为假，请返回'False'；
   - 如果无法确定，请返回'Uncertain'。

## 相关信息
【上下文】：{context}
【判断条件】：{task}
## 研判
【结果】：
"""


HOP_TOOL_USE_PROMPT = """Answer the following questions as best you can. You have access to the following tools:

{tool_descs}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action. The variable names and values in the input need to be returned in json format, e.g. {{"location":"beijing"}}. You are not required to mock data, it must come from the query.

You must Thought first, then choose the Action，and Action Input。
if Action Input is not in Question,you must return {{"key":""}}
Begin!

Question: {task}
Thought: """

HOP_REVERSE_VERIFIER_PROMPT_NO_PROCESS = """
# 要求：
作为知识验证专家,我会给你【上下文】、【结论】,请根据【结论】进行逆向核验。如果有返回格式要求，请严格遵循。请一步步分析。

## 验证步骤：
1. 逆向核验的步骤主要有以下三个点你需要判断：
    b. 判断【结论】是否和【上下文】是否符合逻辑

最终结果必须是以下三种情况之一：
    如果上述每个验证步骤都符合逻辑，最终结果返回True；
    如果有不符合逻辑的话，最终结果返回False；
    如果不确定，最终结果请返回Uncertain。

## 返回格式schema,请注意输出结果符合json格式要求
{return_format}

## 相关信息
【上下文】：{context}
【结论】：{conclusion}
## 研判
【结果】：
"""


HOP_REVERSE_VERIFIER_PROMPT_PROCESS = """
# 要求：
作为知识验证专家,我会给你三个信息【上下文】、【过程】、【结论】,需要你通过给出的【结论】进行逆向核验。如果有返回格式要求，请严格遵循。请一步步分析。

## 验证步骤：
1. 逆向核验的步骤主要有以下三个点你需要判断：
    a. 判断【结论】是否和【过程】是否符合逻辑
    b. 判断【结论】是否和【上下文】是否符合逻辑
    c. 判断 【结论】->【过程】->【上下文】这条链路是否符合逻辑

最终结果必须是以下三种情况之一：
    如果上述每个验证步骤都符合逻辑，最终结果返回True；
    如果有不符合逻辑的话，最终结果返回False；
    如果不确定，最终结果请返回Uncertain。

## 返回格式schema,请注意输出结果符合json格式要求
{return_format}

## 相关信息
【上下文】：{context}
【过程】：{think}
【结论】：{conclusion}
## 研判
【结果】：
"""


HOP_TOOL_USE_VERIFIER_PROMPT = """

You have access to the following tools:
        
{tool_descs}

Use the following format:
tool_specifications: tool_specifications
Thought: you should always think about what to do
Ranking: Give each tool a similarity score for tools_descs and tool_specifications on a scale of 0-10
Action: The tool_name you selected,should be one of [{tool_names}]

Begin!
tool_specifications:{task}
Thought: """


HOP_REVERSE_VERIFIER_PROMPT = """
# 要求：
请核验【结论】对应于【判断条件】和【上下文】是否正确，若【结论】符合【判断条件】和【上下文】则【核验结果】为Passed，否则【核验结果】为Not Passed。如有返回格式要求，请遵循。
注意：【核验结果】与【结论】的概念不同，【核验结果】是判断【结论】是否正确。

## 返回格式schema,请注意输出结果符合json格式要求
{return_format}

## 研判
【判断条件】：{task}
【上下文】：{context}
【结论】：{conclusion}
【核验结果】：
"""

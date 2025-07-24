import json
import os
import re
import hashlib
import requests

from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool


# Add a custom tool named my_image_gen：
@register_tool("cmd_par_tool")
class CmdParTool(BaseTool):
    description = "判断cmd字段是否赋予文件可执行权限。"
    parameters = [
        {"name": "cmd", "type": "string", "description": "cmd字段", "required": True}
    ]

    def call(self, par: str, **kwargs) -> str:
        cmd_input = json.loads(par).get("cmd")
        if type(cmd_input) == str:
            cmd_list = [cmd_input]
        else:
            cmd_list = eval(cmd_input)

        for cmd_input in cmd_list:
            # 生成规范化的chmod命令
            cmd = "chmod " + cmd_input.split("chmod")[-1]
            # 使用正则表达式来解析符号形式的权限设置
            chmod = " ".join([subitem.strip() for subitem in cmd.split("-R")])
            symbolic_match = re.match(
                r"chmod\s+([ugoa]*[+-=]?[rwxXst]*)(?:,[ugoa]*[+-=]?[rwxXst]*)*\s+(\S+)",
                chmod,
            )

            # 使用正则表达式来解析八进制形式的权限设置
            octal_match = re.match(r"chmod\s+([0-7]{3,4})\s+(\S+)", chmod)
            if octal_match:
                # 八进制形式的权限设置
                octal_permissions, file_path = octal_match.groups()
                # print(octal_permissions)
                # 检查八进制权限的最右边3位数字中是否包含1（执行权限）
                wants_executable_permission = any(
                    char in "157" for char in octal_permissions[-3:]
                )
            elif symbolic_match:
                # 符号形式的权限设置

                permissions_part, file_path = symbolic_match.groups()
                wants_executable_permission = (
                    "a+x" in chmod
                    or "u+x" in chmod
                    or "g+x" in chmod
                    or "o+x" in chmod
                    or "+x" in chmod
                )
            else:
                result = False
            # 输出判断
            if wants_executable_permission:
                return True
            else:
                result = False
        return result


@register_tool("install_pack_tool")
class InstallPackTool(BaseTool):
    description = "检查安装包是否是常用软件的安装包。"
    parameters = [
        {
            "name": "install_package",
            "type": "string",
            "description": "install_package字段",
            "required": True,
        }
    ]

    def call(self, par: str, **kwargs) -> str:
        install_package = json.loads(par).get("install_package")
        """
        功能：安装包并判断是否常见安装包
        """
        normal_install_pack = [
            "com.mysql.mysql",
        ]
        if install_package in normal_install_pack:
            return True
        else:
            return False


@register_tool("get_mail_doamin_cti")
class DomainCTISearch(BaseTool):
    description = "判断邮件域名是否属于钓鱼邮件恶意域名，输入参数对应为domain字段"
    parameters = [
        {
            "name": "domain",
            "type": "string",
            "description": "查询的邮件域名字段",
            "required": True,
        }
    ]

    def call(self, par: str) -> str:
        domain = json.loads(par).get("domain")
        white_list = ["domino.com", "repldomain.com", "sample-company.com", "awuye.com"]
        black_list = ["testdomain.org", "xyz-tech.org", "randomsite.net"]
        if domain in black_list:
            return "True"
        elif domain in white_list:
            return "False"
        else:
            return "uncertain"

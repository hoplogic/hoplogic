# 1. 环境准备
* 操作系统：支持 macOS、Linux、Windows
* 安装 Python：建议选择 3.9、3.10 版本。

# 2. 构建环境和安装依赖
- 创建独立环境
```bash
conda create -n myenv python=3.10 
```
- 激活环境
```bash
conda activate myenv
```
- 安装依赖
```bash
pip install -r requirements.txt
```
- 退出环境

```bash
conda deactivate
```

# 3. 修改examples下的配置

```shell
cp examples/phishing/settings.yaml
```
inference_engine: 目前支持推理引擎

云端推理引擎
| 支持推理引擎 | 备注 | 是否支持 |
|-------|-------|-------|
| aistudio-vllm | 蚂蚁内部引擎 | ✅|
| siliconflow | 硅基流动引擎 | ✅ |
| bailian | 阿里云百炼 | ✅ |

本地推理引擎
| 支持推理引擎 | 备注 | 是否支持 |
|-------|-------|-------|
| ollama | ollama本地引擎 | ✅ |
| vllm | vllm开源引擎 | ✅ |
| sglang | sglang开源引擎 | ✅ |

然后修改 settings.yaml 的配置内容等等
- inference_engine: 推理引擎
- api_key: 存放推理引擎的 api key的路径
- model: 模型名称

# 4. 创建文件并写入key
```bash
sudo sh -c 'echo "your api key" > /etc/openai-key'
sudo chmod 600 /etc/openai-key             
sudo chown root:root /etc/openai-key        
sudo cat /etc/openai-key
```
填写/etc/openai-key到api_key参数中

# 5. 执行案例

```bash
sudo python -m examples.phishing.phishing
```
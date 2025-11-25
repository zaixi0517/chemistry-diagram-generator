import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import re  # 引入正则表达式库用于清洗 Gemini 输出

# 确保在初始化客户端之前加载环境变量
load_dotenv() 

try:
    from google import genai
    from google.genai.errors import APIError
except ImportError:
    # 理论上不会发生，因为我们在 venv 中安装了
    print("错误：缺少 google-genai SDK。")
    exit()

app = Flask(__name__)
# 生产环境中，最好将 origins 限制为您的实际域名
# 但为了本地测试和初次部署的简单性，暂时允许所有来源
CORS(app) 

# 从环境变量中获取 API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # 生产部署时，API Key 会由平台注入，而不是来自 .env 文件
    print("警告：GEMINI_API_KEY 未找到。请确保在部署时设置了环境变量。")
    # 如果本地测试，可以暂时退出
    # raise ValueError("未找到 GEMINI_API_KEY。")

# 初始化 Gemini 客户端 (只有当 Key 存在时才初始化)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# -----------------------------------------------------------
# 后端代理 API 接口
# -----------------------------------------------------------
@app.route('/generate_diagram', methods=['POST'])
def generate_diagram():
    """接收前端概念，调用 Gemini 生成动态 HTML 代码，并返回。"""
    
    if not client:
        return jsonify({"error": "Gemini 客户端未初始化，请检查 API Key。"}), 500

    # 1. 解析请求数据
    try:
        data = request.get_json()
        concept = data.get('concept')
        if not concept:
            return jsonify({"error": "请求体中缺少 'concept' 参数。"}), 400
    except Exception:
        return jsonify({"error": "请求数据格式错误，应为 JSON。"}), 400

    # 2. 构建给 Gemini 的指令 Prompt
    prompt = f"""
    你是一个专业的化学可视化生成器。
    请根据用户提供的概念，生成一段**仅包含**HTML元素、CSS样式和JavaScript脚本的代码块。
    此代码块必须能够被**直接注入**到前端页面的一个DIV容器中，且**不包含**<html>、<head>、<body>或完整的文档结构标签。
    要求：使用纯 CSS 动画或 SVG/JavaScript 实现动态或交互效果。请确保代码的简洁和可读性。

    概念：【{concept}】
    """

    print(f"-> 接收到请求概念: {concept}")

    # 3. 调用 Gemini API
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        # 4. 关键优化：提取纯净的 HTML 代码
        raw_text = response.text.strip()
        
        # 使用正则表达式移除常见的 Markdown 代码块界定符
        # 匹配开头如 ```html, ```javascript, ```，以及结尾的 ```
        match = re.search(r'```(?:html|javascript|js)?\s*([\s\S]*?)\s*```', raw_text)
        
        if match:
            html_content = match.group(1).strip()
        else:
            # 如果没有匹配到 Markdown 块，则直接使用原始文本
            html_content = raw_text

        # 5. 返回处理后的 HTML 内容
        return html_content, 200, {'Content-Type': 'text/plain'}

    except APIError as e:
        error_msg = f"Gemini API 调用失败 (APIError): {e}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_msg = f"服务器内部错误 (Exception): {e}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

# -----------------------------------------------------------
# 新增：用于提供 index.html 文件的路由 (方便部署在同一服务器)
# -----------------------------------------------------------
from flask import send_from_directory

@app.route('/')
def serve_index():
    # 生产环境中，我们会将 index.html 放在一个名为 'static' 的文件夹中
    # 为了简化，我们假设它和 app.py 在同一目录
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    print("--- 启动化学示意图生成后端代理 ---")
    print("API 接口: POST http://127.0.0.1:5000/generate_diagram")
    # ⚠️ 部署时，此行代码会被 Gunicorn 替换，但本地测试需要它
    app.run(debug=True, port=5000)
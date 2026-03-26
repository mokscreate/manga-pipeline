"""
server.py — 飞书 webhook 接收服务
飞书多维表格「记录创建时」触发 → 自动跑 pipeline

启动方式：
    DEEPSEEK_API_KEY=sk-xxx python server.py

然后在飞书自动化里把 webhook 地址填：
    http://localhost:5000/webhook
"""

import os
import threading
import subprocess
import sys
from flask import Flask, request, jsonify

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


app = Flask(__name__)


def reset_input_status():
    """收到 webhook 后，把「输入」表所有记录状态清空，等待新内容注入。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from feishu import get_token, list_tables, FEISHU_APP_TOKEN
        import requests as _requests
        token = get_token()
        tables = list_tables(token)
        table_id = tables.get("输入")
        if not table_id:
            return
        resp = _requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 100},
            timeout=10,
        )
        items = resp.json().get("data", {}).get("items", [])
        for item in items:
            _requests.put(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/{item['record_id']}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"fields": {
                    "状态": "待处理",
                    "剧本状态": "",
                    "人物场景状态": "",
                    "分镜状态": "",
                }},
                timeout=10,
            )
        print(f"  ✓ 已重置 {len(items)} 条记录状态")
    except Exception as e:
        print(f"  ⚠ 重置状态失败：{e}")


def run_pipeline():
    """在后台线程里跑 pipeline --feishu"""
    print("\n🚀 检测到新剧本，开始运行 pipeline...\n")
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "pipeline.py", "--feishu"],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode == 0:
        print("\n✅ Pipeline 运行完成\n")
    else:
        print("\n❌ Pipeline 运行失败\n")


@app.route("/webhook", methods=["POST"])
def webhook():
    print(f"📩 收到飞书 webhook：{request.json}")
    reset_input_status()
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return jsonify({"code": 0, "msg": "ok"})


@app.route("/", methods=["GET"])
def index():
    return "漫剧 pipeline 服务运行中 ✅"


if __name__ == "__main__":
    print("🌐 服务启动，监听 http://localhost:5000/webhook")
    print("📋 请在飞书自动化里填写 webhook 地址：http://localhost:5000/webhook")
    print("   （如需外网访问，请用 ngrok 暴露端口）\n")
    app.run(host="0.0.0.0", port=5000, debug=False)

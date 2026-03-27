"""
server.py — 漫剧 pipeline Web 服务

启动：
    python server.py

然后打开浏览器访问 http://localhost:5000
粘贴剧本，点「开始生成」即可。

（飞书 webhook 保留在 /webhook，可选用）
"""

import os
import threading
import sys
from flask import Flask, request, jsonify, send_file, Response

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# ── 全局任务状态 ───────────────────────────────────────────────
_job = {
    "running": False,
    "status": "idle",
    "excel_path": None,
    "error": None,
}
_job_lock = threading.Lock()


def _run_web_pipeline(novel_text: str):
    global _job
    try:
        from pipeline import run_pipeline

        def on_status(msg):
            with _job_lock:
                _job["status"] = msg

        excel_path = run_pipeline(novel_text, status_callback=on_status)
        with _job_lock:
            _job["excel_path"] = excel_path
            _job["running"] = False
    except Exception as e:
        with _job_lock:
            _job["error"] = str(e)
            _job["status"] = f"❌ 出错：{e}"
            _job["running"] = False


# ── Web UI ────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>漫剧 AI 工作流</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f5; color: #222; padding: 24px; }
  h1 { font-size: 1.4rem; margin-bottom: 6px; }
  p.sub { color: #666; font-size: 0.9rem; margin-bottom: 20px; }
  textarea { width: 100%; height: 280px; padding: 12px; border: 1px solid #ccc;
             border-radius: 8px; font-size: 0.95rem; resize: vertical;
             font-family: inherit; line-height: 1.6; }
  .row { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
  button { padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;
           font-size: 1rem; font-weight: 600; transition: opacity .15s; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  #btnRun  { background: #1a73e8; color: #fff; }
  #btnDL   { background: #34a853; color: #fff; display: none; }
  #status  { margin-top: 16px; padding: 12px 16px; border-radius: 8px;
             background: #fff; border: 1px solid #e0e0e0; font-size: 0.95rem;
             min-height: 48px; white-space: pre-wrap; }
  #steps   { margin-top: 10px; padding: 10px 16px; border-radius: 8px;
             background: #fafafa; border: 1px solid #eee;
             font-size: 0.85rem; color: #555; display: none; }
  .step    { padding: 3px 0; }
  .done    { color: #2e7d32; } .cur { color: #1a73e8; font-weight:600; } .wait { color: #aaa; }
</style>
</head>
<body>
<h1>漫剧 AI 工作流</h1>
<p class="sub">粘贴剧本 → 点「开始生成」→ 等待完成 → 下载 Excel</p>

<textarea id="script" placeholder="在这里粘贴剧本内容（支持完整剧本或构思草稿）…"></textarea>

<div class="row">
  <button id="btnRun" onclick="startRun()">开始生成</button>
  <button id="btnDL"  onclick="download()">下载 Excel</button>
  <span id="spinner" style="display:none;color:#888">运行中…</span>
</div>

<div id="status">准备就绪，请粘贴剧本后点「开始生成」。</div>
<div id="steps">
  <div class="step" id="s1">Step 1：改写推文文案</div>
  <div class="step" id="s2">Step 2：提取角色设定</div>
  <div class="step" id="s3">Step 3：提取场景设定</div>
  <div class="step" id="s4">Step 4：生成分镜脚本</div>
</div>

<script>
let polling = null;

function startRun() {
  const text = document.getElementById('script').value.trim();
  if (!text) { alert('请先粘贴剧本内容'); return; }
  document.getElementById('btnRun').disabled = true;
  document.getElementById('btnDL').style.display = 'none';
  document.getElementById('spinner').style.display = '';
  document.getElementById('steps').style.display = '';
  setStep(0);
  document.getElementById('status').textContent = '⏳ 正在启动...';

  fetch('/api/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({script: text})
  }).then(r => r.json()).then(d => {
    if (d.error) { showError(d.error); return; }
    polling = setInterval(pollStatus, 1500);
  }).catch(e => showError(e));
}

function pollStatus() {
  fetch('/api/status').then(r => r.json()).then(d => {
    document.getElementById('status').textContent = d.status;
    updateSteps(d.status);
    if (!d.running) {
      clearInterval(polling);
      document.getElementById('spinner').style.display = 'none';
      document.getElementById('btnRun').disabled = false;
      if (d.excel_path) {
        document.getElementById('btnDL').style.display = '';
        setStep(5);
      }
      if (d.error) showError(d.error);
    }
  });
}

function updateSteps(status) {
  if (status.includes('Step1')) setStep(1);
  else if (status.includes('Step2') || status.includes('角色')) setStep(2);
  else if (status.includes('Step3') || status.includes('场景')) setStep(3);
  else if (status.includes('Step4') || status.includes('分镜')) setStep(4);
  else if (status.includes('全部完成')) setStep(5);
}

function setStep(n) {
  ['s1','s2','s3','s4'].forEach((id, i) => {
    const el = document.getElementById(id);
    el.className = 'step ' + (i+1 < n ? 'done' : i+1 === n ? 'cur' : 'wait');
  });
}

function download() {
  window.location.href = '/api/download';
}

function showError(msg) {
  document.getElementById('status').textContent = '❌ ' + msg;
  document.getElementById('spinner').style.display = 'none';
  document.getElementById('btnRun').disabled = false;
  clearInterval(polling);
}
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/api/run", methods=["POST"])
def api_run():
    global _job
    if _job["running"]:
        return jsonify({"error": "当前有任务正在运行，请等待完成后再提交"})
    novel_text = (request.json or {}).get("script", "").strip()
    if not novel_text:
        return jsonify({"error": "剧本内容不能为空"})
    with _job_lock:
        _job = {"running": True, "status": "⏳ 启动中...", "excel_path": None, "error": None}
    thread = threading.Thread(target=_run_web_pipeline, args=(novel_text,), daemon=True)
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def api_status():
    with _job_lock:
        return jsonify({
            "running": _job["running"],
            "status": _job["status"],
            "excel_path": _job["excel_path"],
            "error": _job["error"],
        })


@app.route("/api/download", methods=["GET"])
def api_download():
    with _job_lock:
        path = _job["excel_path"]
    if not path or not os.path.exists(path):
        return jsonify({"error": "没有可下载的文件"}), 404
    return send_file(os.path.abspath(path), as_attachment=True)


# ── 飞书 webhook（保留，可选） ─────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    print(f"📩 收到飞书 webhook：{request.json}")

    def _feishu_pipeline():
        import subprocess
        result = subprocess.run(
            [sys.executable, "pipeline.py", "--feishu"],
            env=os.environ.copy(),
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        print("\n✅ Pipeline 完成\n" if result.returncode == 0 else "\n❌ Pipeline 失败\n")

    threading.Thread(target=_feishu_pipeline, daemon=True).start()
    return jsonify({"code": 0, "msg": "ok"})


if __name__ == "__main__":
    print("\n🌐 服务启动：http://localhost:5000")
    print("   打开浏览器访问上面的地址，粘贴剧本即可使用\n")
    print("   （飞书 webhook 地址保留在 /webhook，可选用）\n")
    app.run(host="0.0.0.0", port=5000, debug=False)

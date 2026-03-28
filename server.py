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
import json
from pathlib import Path
from datetime import datetime
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
    "results": {},
}
_job_lock = threading.Lock()


def _run_web_pipeline(novel_text: str):
    global _job
    try:
        from pipeline import run_pipeline_with_results

        def on_status(msg):
            with _job_lock:
                _job["status"] = msg

        def on_result(step_name, content):
            with _job_lock:
                _job["results"][step_name] = content

        excel_path = run_pipeline_with_results(novel_text, on_status, on_result)

        # 保存历史记录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        history_file = f"output/history_{timestamp}.json"
        Path("output").mkdir(exist_ok=True)
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "excel_path": excel_path,
                "results": _job["results"],
                "input_length": len(novel_text)
            }, f, ensure_ascii=False, indent=2)

        with _job_lock:
            _job["excel_path"] = excel_path
            _job["running"] = False
    except Exception as e:
        with _job_lock:
            _job["error"] = str(e)
            _job["status"] = f"出错：{e}"
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
         background: #f5f5f5; color: #222; padding: 24px; max-width: 1400px; margin: 0 auto; }
  h1 { font-size: 1.4rem; margin-bottom: 6px; }
  h2 { font-size: 1.1rem; margin: 24px 0 12px; color: #333; }
  p.sub { color: #666; font-size: 0.9rem; margin-bottom: 20px; }
  textarea { width: 100%; height: 280px; padding: 12px; border: 1px solid #ccc;
             border-radius: 8px; font-size: 0.95rem; resize: vertical;
             font-family: inherit; line-height: 1.6; }
  .row { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
  button { padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;
           font-size: 1rem; font-weight: 600; transition: opacity .15s; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  #btnRun  { background: #1a73e8; color: #fff; }
  #btnReset { background: #666; color: #fff; display: none; }
  #btnDL   { background: #34a853; color: #fff; display: none; }
  #status  { margin-top: 16px; padding: 12px 16px; border-radius: 8px;
             background: #fff; border: 1px solid #e0e0e0; font-size: 0.95rem;
             min-height: 48px; white-space: pre-wrap; }
  #steps   { margin-top: 10px; padding: 10px 16px; border-radius: 8px;
             background: #fafafa; border: 1px solid #eee;
             font-size: 0.85rem; color: #555; display: none; }
  .step    { padding: 3px 0; }
  .done    { color: #2e7d32; } .cur { color: #1a73e8; font-weight:600; } .wait { color: #aaa; }

  .result-section { display: none; margin-top: 24px; padding: 16px; background: #fff;
                    border-radius: 8px; border: 1px solid #ddd; }
  .result-section h2 { margin-top: 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.85rem; }
  th, td { padding: 8px 12px; text-align: left; border: 1px solid #ddd; }
  th { background: #f5f5f5; font-weight: 600; }
  tr:hover { background: #fafafa; }
  .script-list { list-style: decimal; padding-left: 24px; line-height: 1.8; }
  .script-list li { margin: 8px 0; }

  #historyPanel { margin-top: 24px; padding: 16px; background: #fff; border-radius: 8px; border: 1px solid #ddd; }
  #historyPanel h2 { margin-top: 0; }
  .history-item { padding: 12px; margin: 8px 0; background: #fafafa; border-radius: 6px; cursor: pointer;
                  border: 1px solid #e0e0e0; transition: all .2s; }
  .history-item:hover { background: #f0f0f0; border-color: #1a73e8; }
  .history-time { font-size: 0.9rem; color: #666; }
  .history-info { font-size: 0.85rem; color: #999; margin-top: 4px; }
</style>
</head>
<body>
<h1>漫剧 AI 工作流</h1>
<p class="sub">粘贴剧本 → 点「开始生成」→ 实时查看结果 → 下载 Excel</p>

<textarea id="script" placeholder="在这里粘贴剧本内容（支持完整剧本或构思草稿）…"></textarea>

<div class="row">
  <button id="btnRun" onclick="startRun()">开始生成</button>
  <button id="btnReset" onclick="resetTask()">重新开始</button>
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

<div id="result1" class="result-section">
  <h2>Step 1：推文文案</h2>
  <ol id="scriptList" class="script-list"></ol>
</div>

<div id="result2" class="result-section">
  <h2>Step 2：角色设定</h2>
  <div id="charactersTable"></div>
</div>

<div id="result3" class="result-section">
  <h2>Step 3：场景设定</h2>
  <div id="scenesTable"></div>
</div>

<div id="result4" class="result-section">
  <h2>Step 4：分镜脚本</h2>
  <div id="storyboardTable"></div>
</div>

<div id="historyPanel">
  <h2>历史记录</h2>
  <div id="historyList">加载中...</div>
</div>

<script>
let polling = null;
let lastResults = {};

// 页面加载时获取历史记录
window.onload = function() {
  loadHistory();
};

function startRun() {
  const text = document.getElementById('script').value.trim();
  if (!text) { alert('请先粘贴剧本内容'); return; }

  // 重置界面
  document.getElementById('btnRun').disabled = true;
  document.getElementById('btnReset').style.display = 'none';
  document.getElementById('btnDL').style.display = 'none';
  document.getElementById('spinner').style.display = '';
  document.getElementById('steps').style.display = '';
  ['result1','result2','result3','result4'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
  lastResults = {};
  setStep(0);
  document.getElementById('status').textContent = '正在启动...';

  fetch('/api/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({script: text})
  }).then(r => r.json()).then(d => {
    if (d.error) { showError(d.error); return; }
    polling = setInterval(pollStatus, 1500);
  }).catch(e => showError(e));
}

function resetTask() {
  // 清空界面，重新开始
  document.getElementById('btnRun').disabled = false;
  document.getElementById('btnReset').style.display = 'none';
  document.getElementById('btnDL').style.display = 'none';
  document.getElementById('spinner').style.display = 'none';
  document.getElementById('steps').style.display = 'none';
  ['result1','result2','result3','result4'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
  document.getElementById('status').textContent = '准备就绪，请粘贴剧本后点「开始生成」。';
  setStep(0);
  lastResults = {};
  if (polling) clearInterval(polling);
}

function pollStatus() {
  fetch('/api/status').then(r => r.json()).then(d => {
    document.getElementById('status').textContent = d.status;
    updateSteps(d.status);

    // 渲染新的结果
    if (d.results) {
      if (d.results.script && !lastResults.script) {
        renderScript(d.results.script);
        lastResults.script = true;
      }
      if (d.results.characters && !lastResults.characters) {
        renderTable('charactersTable', d.results.characters, 'result2');
        lastResults.characters = true;
      }
      if (d.results.scenes && !lastResults.scenes) {
        renderTable('scenesTable', d.results.scenes, 'result3');
        lastResults.scenes = true;
      }
      if (d.results.storyboard && !lastResults.storyboard) {
        renderTable('storyboardTable', d.results.storyboard, 'result4');
        lastResults.storyboard = true;
      }
    }

    if (!d.running) {
      clearInterval(polling);
      document.getElementById('spinner').style.display = 'none';
      document.getElementById('btnRun').disabled = false;
      document.getElementById('btnReset').style.display = '';
      if (d.excel_path) {
        document.getElementById('btnDL').style.display = '';
        setStep(5);
        loadHistory(); // 刷新历史记录
      }
      if (d.error) showError(d.error);
    }
  });
}

function renderScript(text) {
  const lines = text.split('\\n').filter(l => l.trim());
  const html = lines.map(l => `<li>${escapeHtml(l)}</li>`).join('');
  document.getElementById('scriptList').innerHTML = html;
  document.getElementById('result1').style.display = 'block';
}

function renderTable(containerId, text, sectionId) {
  const lines = text.split('\\n').filter(l => l.includes('|||'));
  if (lines.length === 0) return;

  const headers = lines[0].split('|||').map(h => h.trim());
  const rows = lines.slice(1).map(line => line.split('|||').map(c => c.trim()));

  let html = '<table><thead><tr>';
  headers.forEach(h => { html += `<th>${escapeHtml(h)}</th>`; });
  html += '</tr></thead><tbody>';
  rows.forEach(row => {
    html += '<tr>';
    row.forEach(cell => { html += `<td>${escapeHtml(cell)}</td>`; });
    html += '</tr>';
  });
  html += '</tbody></table>';

  document.getElementById(containerId).innerHTML = html;
  document.getElementById(sectionId).style.display = 'block';
}

function loadHistory() {
  fetch('/api/history').then(r => r.json()).then(list => {
    if (list.length === 0) {
      document.getElementById('historyList').innerHTML = '<p style="color:#999">暂无历史记录</p>';
      return;
    }
    let html = '';
    list.forEach(item => {
      const time = item.timestamp.replace(/_/g, ' ').replace(/^(\\d{4})(\\d{2})(\\d{2}) (\\d{2})(\\d{2})(\\d{2})$/, '$1-$2-$3 $4:$5:$6');
      html += `<div class="history-item" onclick="loadHistoryDetail('${item.id}')">
        <div class="history-time">${time}</div>
        <div class="history-info">输入长度：${item.input_length} 字符</div>
      </div>`;
    });
    document.getElementById('historyList').innerHTML = html;
  });
}

function loadHistoryDetail(id) {
  fetch(`/api/history/${id}`).then(r => r.json()).then(data => {
    // 显示历史结果
    if (data.results.script) renderScript(data.results.script);
    if (data.results.characters) renderTable('charactersTable', data.results.characters, 'result2');
    if (data.results.scenes) renderTable('scenesTable', data.results.scenes, 'result3');
    if (data.results.storyboard) renderTable('storyboardTable', data.results.storyboard, 'result4');

    document.getElementById('btnDL').style.display = '';
    document.getElementById('btnReset').style.display = '';
    document.getElementById('status').textContent = '已加载历史记录';
    setStep(5);

    // 设置下载链接为历史记录的 Excel
    window.currentExcelPath = data.excel_path;
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
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
  if (window.currentExcelPath) {
    window.location.href = `/api/download?path=${encodeURIComponent(window.currentExcelPath)}`;
  } else {
    window.location.href = '/api/download';
  }
}

function showError(msg) {
  document.getElementById('status').textContent = '出错：' + msg;
  document.getElementById('spinner').style.display = 'none';
  document.getElementById('btnRun').disabled = false;
  document.getElementById('btnReset').style.display = '';
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
        _job = {"running": True, "status": "启动中...", "excel_path": None, "error": None, "results": {}}
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
            "results": _job["results"],
        })


@app.route("/api/download", methods=["GET"])
def api_download():
    # 支持下载历史记录的 Excel
    path = request.args.get("path")
    if not path:
        with _job_lock:
            path = _job["excel_path"]
    if not path or not os.path.exists(path):
        return jsonify({"error": "没有可下载的文件"}), 404
    return send_file(os.path.abspath(path), as_attachment=True)


@app.route("/api/history", methods=["GET"])
def api_history():
    """返回历史记录列表"""
    output_dir = Path("output")
    if not output_dir.exists():
        return jsonify([])

    history_files = sorted(output_dir.glob("history_*.json"), reverse=True)
    history_list = []
    for f in history_files[:20]:  # 最多返回最近20条
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                history_list.append({
                    "id": f.stem.replace("history_", ""),
                    "timestamp": data.get("timestamp"),
                    "input_length": data.get("input_length", 0),
                })
        except:
            pass
    return jsonify(history_list)


@app.route("/api/history/<history_id>", methods=["GET"])
def api_history_detail(history_id):
    """返回某条历史记录的详细内容"""
    history_file = Path(f"output/history_{history_id}.json")
    if not history_file.exists():
        return jsonify({"error": "历史记录不存在"}), 404

    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)


# ── 飞书 webhook（保留，可选） ─────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    print(f"收到飞书 webhook：{request.json}")

    def _feishu_pipeline():
        import subprocess
        result = subprocess.run(
            [sys.executable, "pipeline.py", "--feishu"],
            env=os.environ.copy(),
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        print("\nPipeline 完成\n" if result.returncode == 0 else "\nPipeline 失败\n")

    threading.Thread(target=_feishu_pipeline, daemon=True).start()
    return jsonify({"code": 0, "msg": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n服务启动：http://localhost:{port}")
    print("   打开浏览器访问上面的地址，粘贴剧本即可使用\n")
    print("   （飞书 webhook 地址保留在 /webhook，可选用）\n")
    app.run(host="0.0.0.0", port=port, debug=False)

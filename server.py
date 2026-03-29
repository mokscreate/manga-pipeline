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
    "current_step": 0,  # 0=未开始, 1=文案完成, 2=角色场景完成, 3=分镜完成
    "input_text": "",   # 保存原始输入
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
  textarea { width: 100%; padding: 12px; border: 1px solid #ccc;
             border-radius: 8px; font-size: 0.95rem; resize: vertical;
             font-family: inherit; line-height: 1.6; }
  #script { height: 280px; }
  .edit-area { height: 200px; font-family: monospace; }
  .row { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
  button { padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;
           font-size: 1rem; font-weight: 600; transition: opacity .15s; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  #btnRun  { background: #1a73e8; color: #fff; }
  #btnReset { background: #666; color: #fff; display: none; }
  #btnEdit { background: #ea4335; color: #fff; display: none; }
  #btnGenerateImages { background: #9c27b0; color: #fff; display: none; }
  #btnExport { background: #f57c00; color: #fff; display: none; }
  #btnSave { background: #34a853; color: #fff; display: none; }
  #btnCancel { background: #999; color: #fff; display: none; }
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

  #editPanel { display: none; margin-top: 24px; padding: 16px; background: #fff;
               border-radius: 8px; border: 1px solid #ddd; }
  #editPanel h2 { margin-top: 0; }
  .edit-section { margin: 16px 0; }
  .edit-section label { display: block; font-weight: 600; margin-bottom: 8px; color: #333; }

  #historyPanel { margin-top: 24px; padding: 16px; background: #fff; border-radius: 8px; border: 1px solid #ddd; }
  #historyPanel h2 { margin-top: 0; }
  .history-item { padding: 12px; margin: 8px 0; background: #fafafa; border-radius: 6px; cursor: pointer;
                  border: 1px solid #e0e0e0; transition: all .2s; }
  .history-item:hover { background: #f0f0f0; border-color: #1a73e8; }
  .history-time { font-size: 0.9rem; color: #666; }
  .history-info { font-size: 0.85rem; color: #999; margin-top: 4px; }

  .section { padding: 16px; background: #fff; border-radius: 8px; border: 1px solid #ddd; }

  .image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-top: 16px; }
  .image-item { border: 1px solid #ddd; border-radius: 8px; padding: 12px; background: #fff; }
  .image-item h3 { margin: 0 0 8px 0; font-size: 0.95rem; color: #333; }
  .image-item img { width: 100%; border-radius: 4px; }
</style>
</head>
<body>
<h1>漫剧 AI 工作流</h1>
<p class="sub">粘贴剧本 → 生成文案并修改 → 生成角色场景并修改 → 生成分镜 → 下载 Excel</p>

<div class="section" style="margin-bottom: 20px;">
  <h2 style="font-size: 1rem; margin-bottom: 12px;">API 配置</h2>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
    <div>
      <label style="display: block; font-size: 0.85rem; color: #666; margin-bottom: 4px;">DeepSeek API Key</label>
      <input type="password" id="deepseekKey" placeholder="sk-..." style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem;">
    </div>
    <div>
      <label style="display: block; font-size: 0.85rem; color: #666; margin-bottom: 4px;">NanoBanana API Key</label>
      <input type="password" id="nanobananaKey" placeholder="sk-..." style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem;">
    </div>
  </div>
  <p style="font-size: 0.8rem; color: #999; margin-top: 8px;">API Key 仅保存在浏览器本地，不会上传到服务器</p>
</div>

<textarea id="script" placeholder="在这里粘贴剧本内容（支持完整剧本或构思草稿）…"></textarea>

<div class="row">
  <button id="btnRun" onclick="startRun()">开始生成</button>
  <button id="btnReset" onclick="resetTask()">重新开始</button>
  <button id="btnEdit" onclick="enterEditMode()">下一步，人工修改</button>
  <button id="btnGenerateImages" onclick="goToImagePage()">生成角色场景图</button>
  <button id="btnExport" onclick="exportExcel()">导出 Excel</button>
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

<div id="editPanel">
  <h2>人工修改内容</h2>
  <p style="color:#666;margin-bottom:16px" id="editHint">直接在下方文本框中修改内容，修改完成后点击「保存并进入下一步」</p>

  <div class="edit-section">
    <label>推文文案（每行一段）</label>
    <textarea id="editScript" class="edit-area"></textarea>
  </div>

  <div class="edit-section">
    <label>角色设定（表格格式，用 ||| 分隔字段）</label>
    <textarea id="editCharacters" class="edit-area"></textarea>
  </div>

  <div class="edit-section">
    <label>场景设定（表格格式，用 ||| 分隔字段）</label>
    <textarea id="editScenes" class="edit-area"></textarea>
  </div>

  <div class="edit-section">
    <label>分镜脚本（表格格式，用 ||| 分隔字段）</label>
    <textarea id="editStoryboard" class="edit-area"></textarea>
  </div>

  <div class="row">
    <button id="btnSave" onclick="saveEdits()">保存并进入下一步</button>
    <button id="btnCancel" onclick="cancelEdit()">取消</button>
  </div>
</div>

<div id="historyPanel">
  <h2>历史记录</h2>
  <div id="historyList">加载中...</div>
</div>

<script>
let polling = null;
let lastResults = {};
let currentResults = {};
let currentStep = 0;  // 0=未开始, 1=文案完成, 2=角色场景完成, 3=分镜完成

window.onload = function() {
  loadHistory();
  loadApiKeys();
};

function loadApiKeys() {
  const deepseekKey = localStorage.getItem('deepseek_api_key') || '';
  const nanobananaKey = localStorage.getItem('nanobanana_api_key') || '';
  document.getElementById('deepseekKey').value = deepseekKey;
  document.getElementById('nanobananaKey').value = nanobananaKey;
}

function saveApiKeys() {
  const deepseekKey = document.getElementById('deepseekKey').value.trim();
  const nanobananaKey = document.getElementById('nanobananaKey').value.trim();
  if (deepseekKey) localStorage.setItem('deepseek_api_key', deepseekKey);
  if (nanobananaKey) localStorage.setItem('nanobanana_api_key', nanobananaKey);
}

function startRun() {
  const text = document.getElementById('script').value.trim();
  if (!text) { alert('请先粘贴剧本内容'); return; }

  const deepseekKey = document.getElementById('deepseekKey').value.trim();
  if (!deepseekKey) { alert('请先填写 DeepSeek API Key'); return; }

  saveApiKeys();

  document.getElementById('btnRun').disabled = true;
  document.getElementById('btnReset').style.display = 'none';
  document.getElementById('btnEdit').style.display = 'none';
  document.getElementById('btnDL').style.display = 'none';
  document.getElementById('spinner').style.display = '';
  document.getElementById('steps').style.display = '';
  document.getElementById('editPanel').style.display = 'none';
  ['result1','result2','result3','result4'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
  lastResults = {};
  currentResults = {};
  currentStep = 0;
  setStep(0);
  document.getElementById('status').textContent = '正在生成推文文案...';

  fetch('/api/step1', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      script: text,
      deepseek_api_key: deepseekKey
    })
  }).then(r => r.json()).then(d => {
    if (d.error) { showError(d.error); return; }
    polling = setInterval(pollStatus, 1500);
  }).catch(e => showError(e));
}

function nextStep() {
  if (currentStep === 1) {
    // 从编辑框获取修改后的文案，进入 Step2
    const script = document.getElementById('editScript').value;
    currentResults.script = script;

    const deepseekKey = localStorage.getItem('deepseek_api_key') || '';

    document.getElementById('editPanel').style.display = 'none';
    document.getElementById('btnEdit').style.display = 'none';
    document.getElementById('spinner').style.display = '';
    document.getElementById('status').textContent = '正在生成角色和场景...';

    fetch('/api/step2', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        script: script,
        deepseek_api_key: deepseekKey
      })
    }).then(r => r.json()).then(d => {
      if (d.error) { showError(d.error); return; }
      polling = setInterval(pollStatus, 1500);
    }).catch(e => showError(e));

  } else if (currentStep === 2) {
    // 使用 currentResults 中已保存的数据（从表格提取的）
    const script = currentResults.script;
    const characters = currentResults.characters;
    const scenes = currentResults.scenes;

    const deepseekKey = localStorage.getItem('deepseek_api_key') || '';

    document.getElementById('editPanel').style.display = 'none';
    document.getElementById('btnEdit').style.display = 'none';
    document.getElementById('spinner').style.display = '';
    document.getElementById('status').textContent = '正在生成分镜脚本...';

    fetch('/api/step3', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        script: script,
        characters: characters,
        scenes: scenes,
        deepseek_api_key: deepseekKey
      })
    }).then(r => r.json()).then(d => {
      if (d.error) { showError(d.error); return; }
      polling = setInterval(pollStatus, 1500);
    }).catch(e => showError(e));
  }
}

function resetTask() {
  document.getElementById('btnRun').disabled = false;
  document.getElementById('btnReset').style.display = 'none';
  document.getElementById('btnEdit').style.display = 'none';
  document.getElementById('btnGenerateImages').style.display = 'none';
  document.getElementById('btnExport').style.display = 'none';
  document.getElementById('spinner').style.display = 'none';
  document.getElementById('steps').style.display = 'none';
  document.getElementById('editPanel').style.display = 'none';
  ['result1','result2','result3','result4'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
  document.getElementById('status').textContent = '准备就绪，请粘贴剧本后点「开始生成」。';
  setStep(0);
  lastResults = {};
  currentResults = {};
  currentStep = 0;
  if (polling) clearInterval(polling);
}

function goToImagePage() {
  // 保存当前数据到 sessionStorage
  sessionStorage.setItem('characters', currentResults.characters || '');
  sessionStorage.setItem('scenes', currentResults.scenes || '');
  sessionStorage.setItem('nanobanana_api_key', localStorage.getItem('nanobanana_api_key') || '');
  // 跳转到图片生成页面
  window.location.href = '/generate-images';
}

function exportExcel() {
  // 从表格和文本框中提取当前内容
  const script = currentResults.script || '';
  const characters = currentResults.characters || '';
  const scenes = currentResults.scenes || '';
  const storyboard = currentResults.storyboard || '';

  if (!script || !characters || !scenes || !storyboard) {
    alert('内容不完整，无法导出 Excel');
    return;
  }

  document.getElementById('status').textContent = '正在生成并下载 Excel...';
  document.getElementById('btnExport').disabled = true;

  fetch('/api/regenerate_excel', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      script: script,
      characters: characters,
      scenes: scenes,
      storyboard: storyboard
    })
  }).then(r => r.json()).then(d => {
    document.getElementById('btnExport').disabled = false;
    if (d.error) {
      alert('导出失败：' + d.error);
      return;
    }
    document.getElementById('status').textContent = 'Excel 已生成';
    window.currentExcelPath = d.excel_path;
    loadHistory();
    // 自动触发下载
    window.location.href = `/api/download?path=${encodeURIComponent(d.excel_path)}`;
  }).catch(e => {
    document.getElementById('btnExport').disabled = false;
    alert('导出失败：' + e);
  });
}

function enterEditMode() {
  // 根据当前步骤显示对应的编辑内容
  document.getElementById('editPanel').style.display = 'block';
  document.getElementById('btnEdit').style.display = 'none';
  document.getElementById('btnSave').style.display = 'inline-block';
  document.getElementById('btnCancel').style.display = 'inline-block';

  // 填充推文文案到编辑框
  if (currentResults.script) {
    document.getElementById('editScript').value = currentResults.script;
  }

  // 根据步骤调整界面
  const sections = document.querySelectorAll('#editPanel .edit-section');
  const hint = document.getElementById('editHint');
  const btnSave = document.getElementById('btnSave');

  if (currentStep === 1) {
    // 只显示文案编辑
    sections[0].style.display = 'block';
    sections[1].style.display = 'none';
    sections[2].style.display = 'none';
    sections[3].style.display = 'none';
    hint.textContent = '直接编辑推文文案，修改完成后点击「保存并生成角色场景」';
    btnSave.textContent = '保存并生成角色场景';
  } else if (currentStep === 2) {
    // 显示文案编辑 + 表格可编辑
    sections[0].style.display = 'block';
    sections[1].style.display = 'none';
    sections[2].style.display = 'none';
    sections[3].style.display = 'none';
    hint.textContent = '直接在表格中编辑角色和场景，修改完成后点击「保存并生成分镜」';
    btnSave.textContent = '保存并生成分镜';

    // 渲染可编辑表格
    if (currentResults.characters) {
      renderTable('charactersTable', currentResults.characters, 'result2', true);
    }
    if (currentResults.scenes) {
      renderTable('scenesTable', currentResults.scenes, 'result3', true);
    }
  } else {
    // Step3 完成后的编辑
    sections[0].style.display = 'block';
    sections[1].style.display = 'none';
    sections[2].style.display = 'none';
    sections[3].style.display = 'none';
    hint.textContent = '直接在表格中编辑内容，修改完成后点击「保存修改」';
    btnSave.textContent = '保存修改';

    if (currentResults.characters) {
      renderTable('charactersTable', currentResults.characters, 'result2', true);
    }
    if (currentResults.scenes) {
      renderTable('scenesTable', currentResults.scenes, 'result3', true);
    }
    if (currentResults.storyboard) {
      renderTable('storyboardTable', currentResults.storyboard, 'result4', true);
    }
  }
}

function saveEdits() {
  // 保存编辑后的内容并进入下一步
  if (currentStep === 1) {
    currentResults.script = document.getElementById('editScript').value;
    renderScript(currentResults.script);
    document.getElementById('editPanel').style.display = 'none';
    nextStep();
  } else if (currentStep === 2) {
    currentResults.script = document.getElementById('editScript').value;
    currentResults.characters = extractTableData('charactersTable');
    currentResults.scenes = extractTableData('scenesTable');
    renderScript(currentResults.script);
    renderTable('charactersTable', currentResults.characters, 'result2', false);
    renderTable('scenesTable', currentResults.scenes, 'result3', false);
    document.getElementById('editPanel').style.display = 'none';
    nextStep();
  } else {
    // Step 3 完成后只是保存，不进入下一步
    currentResults.script = document.getElementById('editScript').value;
    currentResults.characters = extractTableData('charactersTable');
    currentResults.scenes = extractTableData('scenesTable');
    currentResults.storyboard = extractTableData('storyboardTable');

    renderScript(currentResults.script);
    renderTable('charactersTable', currentResults.characters, 'result2', false);
    renderTable('scenesTable', currentResults.scenes, 'result3', false);
    renderTable('storyboardTable', currentResults.storyboard, 'result4', false);

    document.getElementById('editPanel').style.display = 'none';
    document.getElementById('btnEdit').style.display = 'inline-block';
    document.getElementById('btnExport').style.display = 'inline-block';
    document.getElementById('btnSave').style.display = 'none';
    document.getElementById('btnCancel').style.display = 'none';
    document.getElementById('status').textContent = '修改已保存，点击「导出 Excel」下载文件';
  }
}

function cancelEdit() {
  // 取消编辑，返回查看模式
  document.getElementById('editPanel').style.display = 'none';
  document.getElementById('btnEdit').style.display = 'inline-block';
  document.getElementById('btnSave').style.display = 'none';
  document.getElementById('btnCancel').style.display = 'none';

  // 恢复非编辑状态的表格
  if (currentStep >= 2 && currentResults.characters) {
    renderTable('charactersTable', currentResults.characters, 'result2', false);
  }
  if (currentStep >= 2 && currentResults.scenes) {
    renderTable('scenesTable', currentResults.scenes, 'result3', false);
  }
  if (currentStep >= 3 && currentResults.storyboard) {
    renderTable('storyboardTable', currentResults.storyboard, 'result4', false);
  }

  // 显示已有的结果
  if (currentStep >= 1) document.getElementById('result1').style.display = 'block';
  if (currentStep >= 2) {
    document.getElementById('result2').style.display = 'block';
    document.getElementById('result3').style.display = 'block';
  }
  if (currentStep >= 3) document.getElementById('result4').style.display = 'block';
}

function pollStatus() {
  fetch('/api/status').then(r => r.json()).then(d => {
    document.getElementById('status').textContent = d.status;
    currentStep = d.current_step || 0;
    updateSteps(d.status);

    if (d.results) {
      if (d.results.script && !lastResults.script) {
        renderScript(d.results.script);
        currentResults.script = d.results.script;
        lastResults.script = true;
      }
      if (d.results.characters && !lastResults.characters) {
        renderTable('charactersTable', d.results.characters, 'result2', false);
        currentResults.characters = d.results.characters;
        lastResults.characters = true;
      }
      if (d.results.scenes && !lastResults.scenes) {
        renderTable('scenesTable', d.results.scenes, 'result3', false);
        currentResults.scenes = d.results.scenes;
        lastResults.scenes = true;
      }
      if (d.results.storyboard && !lastResults.storyboard) {
        renderTable('storyboardTable', d.results.storyboard, 'result4', false);
        currentResults.storyboard = d.results.storyboard;
        lastResults.storyboard = true;
      }
    }

    if (!d.running) {
      clearInterval(polling);
      document.getElementById('spinner').style.display = 'none';

      if (d.error) {
        showError(d.error);
        document.getElementById('btnRun').disabled = false;
        document.getElementById('btnReset').style.display = 'inline-block';
      } else if (currentStep === 1) {
        // Step1 完成，显示编辑按钮
        document.getElementById('btnEdit').style.display = 'inline-block';
        document.getElementById('btnEdit').textContent = '修改文案并进入下一步';
        document.getElementById('btnReset').style.display = 'inline-block';
        setStep(1);
        enterEditMode();  // 自动进入编辑模式
      } else if (currentStep === 2) {
        // Step2 完成，显示编辑按钮
        document.getElementById('btnEdit').style.display = 'inline-block';
        document.getElementById('btnEdit').textContent = '修改角色场景并进入下一步';
        document.getElementById('btnReset').style.display = 'inline-block';
        setStep(3);
        enterEditMode();  // 自动进入编辑模式
      } else if (currentStep === 3) {
        // Step3 完成，显示生成图片和导出按钮
        document.getElementById('btnRun').disabled = false;
        document.getElementById('btnReset').style.display = 'inline-block';
        document.getElementById('btnEdit').style.display = 'inline-block';
        document.getElementById('btnEdit').textContent = '修改内容';
        document.getElementById('btnGenerateImages').style.display = 'inline-block';
        document.getElementById('btnExport').style.display = 'inline-block';
        setStep(5);
        if (d.excel_path) {
          loadHistory();
        }
      }
    }
  });
}

function renderScript(text) {
  const lines = text.split('\\n').filter(l => l.trim());
  const html = lines.map(l => `<li>${escapeHtml(l)}</li>`).join('');
  document.getElementById('scriptList').innerHTML = html;
  document.getElementById('result1').style.display = 'block';
}

function renderTable(containerId, text, sectionId, editable = false) {
  const lines = text.split('\\n').filter(l => l.includes('|||'));
  if (lines.length === 0) return;

  const headers = lines[0].split('|||').map(h => h.trim());
  const rows = lines.slice(1).map(line => line.split('|||').map(c => c.trim()));

  let html = '<table><thead><tr>';
  headers.forEach(h => { html += `<th>${escapeHtml(h)}</th>`; });
  if (editable) html += '<th>操作</th>';
  html += '</tr></thead><tbody>';
  rows.forEach((row, idx) => {
    html += '<tr>';
    row.forEach(cell => {
      html += editable
        ? `<td contenteditable="true">${escapeHtml(cell)}</td>`
        : `<td>${escapeHtml(cell)}</td>`;
    });
    if (editable) {
      html += `<td><button onclick="deleteTableRow(this)" style="padding:4px 8px;font-size:0.85rem;background:#f44336">删除</button></td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table>';

  if (editable) {
    html += `<button onclick="addTableRow('${containerId}')" style="margin-top:8px;padding:6px 12px;background:#1a73e8;color:#fff;border:none;border-radius:4px;cursor:pointer">添加一行</button>`;
  }

  document.getElementById(containerId).innerHTML = html;
  document.getElementById(sectionId).style.display = 'block';
}

function deleteTableRow(btn) {
  btn.closest('tr').remove();
}

function addTableRow(containerId) {
  const table = document.querySelector(`#${containerId} table tbody`);
  const headerCount = document.querySelector(`#${containerId} table thead th`).parentElement.children.length - 1; // 减去操作列
  let html = '<tr>';
  for (let i = 0; i < headerCount; i++) {
    html += '<td contenteditable="true"></td>';
  }
  html += '<td><button onclick="deleteTableRow(this)" style="padding:4px 8px;font-size:0.85rem;background:#f44336">删除</button></td>';
  html += '</tr>';
  table.insertAdjacentHTML('beforeend', html);
}

function extractTableData(containerId) {
  const table = document.querySelector(`#${containerId} table`);
  if (!table) return '';

  const headers = Array.from(table.querySelectorAll('thead th'))
    .slice(0, -1) // 排除"操作"列
    .map(th => th.textContent.trim());

  const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => {
    return Array.from(tr.querySelectorAll('td'))
      .slice(0, -1) // 排除"操作"列
      .map(td => td.textContent.trim())
      .join(' ||| ');
  });

  return [headers.join(' ||| '), ...rows].join('\\n');
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
    if (data.results.script) {
      renderScript(data.results.script);
      currentResults.script = data.results.script;
    }
    if (data.results.characters) {
      renderTable('charactersTable', data.results.characters, 'result2', false);
      currentResults.characters = data.results.characters;
    }
    if (data.results.scenes) {
      renderTable('scenesTable', data.results.scenes, 'result3', false);
      currentResults.scenes = data.results.scenes;
    }
    if (data.results.storyboard) {
      renderTable('storyboardTable', data.results.storyboard, 'result4', false);
      currentResults.storyboard = data.results.storyboard;
    }

    document.getElementById('btnReset').style.display = 'inline-block';
    document.getElementById('btnEdit').style.display = 'inline-block';
    document.getElementById('btnGenerateImages').style.display = 'inline-block';
    document.getElementById('btnExport').style.display = 'inline-block';
    document.getElementById('status').textContent = '已加载历史记录';
    currentStep = 3;  // 设置为 Step3 完成状态
    setStep(5);

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


IMAGE_GEN_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>生成角色场景图 - 漫剧 AI</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f5; color: #222; padding: 24px; max-width: 1400px; margin: 0 auto; }
  h1 { font-size: 1.4rem; margin-bottom: 6px; }
  p.sub { color: #666; font-size: 0.9rem; margin-bottom: 20px; }
  .row { display: flex; gap: 10px; margin-top: 12px; align-items: center; }
  button { padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;
           font-size: 1rem; font-weight: 600; transition: opacity .15s; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .btn-small { padding: 6px 12px; font-size: 0.85rem; }
  #btnBack { background: #666; color: #fff; }
  .section { margin-top: 24px; padding: 16px; background: #fff; border-radius: 8px; border: 1px solid #ddd; }
  .section h2 { margin-top: 0; font-size: 1.1rem; margin-bottom: 16px; }

  .style-selector { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
  .style-option { padding: 10px 20px; border: 2px solid #ddd; border-radius: 8px; cursor: pointer;
                  background: #fff; transition: all .2s; }
  .style-option:hover { border-color: #9c27b0; }
  .style-option.selected { border-color: #9c27b0; background: #f3e5f5; font-weight: 600; }

  .item { display: flex; flex-direction: column; gap: 12px; padding: 12px; border: 1px solid #e0e0e0;
          border-radius: 8px; background: #fafafa; }
  .item-header { display: flex; align-items: center; gap: 12px; }
  .item-info { flex: 1; }
  .item-name { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; }
  .item-desc { font-size: 0.85rem; color: #666; }
  .item-actions { display: flex; gap: 8px; align-items: center; }
  .btn-generate { background: #9c27b0; color: #fff; }
  .btn-regenerate { background: #f57c00; color: #fff; }

  .prompt-editor { display: none; margin-top: 12px; padding: 12px; background: #fff; border-radius: 6px; border: 1px solid #ddd; }
  .prompt-editor.show { display: block; }
  .prompt-editor label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 6px; }
  .prompt-editor textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;
                            font-size: 0.85rem; font-family: monospace; resize: vertical; min-height: 80px; }
  .prompt-editor .controls { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
  .prompt-editor input[type="number"] { width: 60px; padding: 6px; border: 1px solid #ccc; border-radius: 4px; }

  .item-images { margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
  .image-version { padding: 10px; background: #fff; border-radius: 6px; border: 1px solid #ddd; }
  .image-version-header { font-size: 0.85rem; color: #666; margin-bottom: 8px; }
  .image-version-images { display: flex; gap: 8px; flex-wrap: wrap; }
  .image-version img { width: 150px; height: 84px; object-fit: cover; border-radius: 4px; cursor: pointer; transition: transform .2s; }
  .image-version img:hover { transform: scale(1.05); }

  .loading { color: #9c27b0; font-size: 0.85rem; }

  /* 大图查看器 */
  .image-viewer { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9);
                  z-index: 9999; justify-content: center; align-items: center; }
  .image-viewer.show { display: flex; }
  .image-viewer img { max-width: 90%; max-height: 90%; border-radius: 8px; }
  .image-viewer-close { position: absolute; top: 20px; right: 20px; color: #fff; font-size: 2rem;
                        cursor: pointer; background: rgba(0,0,0,0.5); width: 40px; height: 40px;
                        border-radius: 50%; display: flex; align-items: center; justify-content: center; }
</style>
</head>
<body>
<h1>生成角色场景图</h1>
<p class="sub">选择风格后，为每个角色和场景单独生成参考图</p>

<div class="section">
  <h2>API 配置</h2>
  <div style="display: flex; gap: 12px; align-items: center;">
    <label style="font-size: 0.9rem; font-weight: 600;">NanoBanana API Key:</label>
    <input type="text" id="nanoBananaKey" placeholder="sk-..."
           style="flex: 1; padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem;">
  </div>
</div>

<div class="row">
  <button id="btnBack" onclick="goBack()">返回主页</button>
</div>

<div class="section">
  <h2>选择生成风格</h2>
  <div class="style-selector">
    <div class="style-option" data-style="3D玄幻" onclick="selectStyle('3D玄幻')">3D 玄幻</div>
    <div class="style-option" data-style="2D动画" onclick="selectStyle('2D动画')">2D 动画</div>
    <div class="style-option" data-style="真人电影" onclick="selectStyle('真人电影')">真人电影</div>
    <div class="style-option" data-style="真人古装" onclick="selectStyle('真人古装')">真人古装</div>
    <div class="style-option" data-style="3D写实" onclick="selectStyle('3D写实')">3D 写实</div>
  </div>
</div>

<div class="section">
  <h2>选择生成模型</h2>
  <div class="style-selector">
    <div class="style-option" data-model="nano-banana-pro" onclick="selectModel('nano-banana-pro')">Pro（推荐）</div>
    <div class="style-option" data-model="nano-banana-2-4k" onclick="selectModel('nano-banana-2-4k')">2-4K</div>
    <div class="style-option" data-model="nano-banana-2-2k" onclick="selectModel('nano-banana-2-2k')">2-2K</div>
    <div class="style-option" data-model="nano-banana-2" onclick="selectModel('nano-banana-2')">2</div>
    <div class="style-option" data-model="nano-banana-hd" onclick="selectModel('nano-banana-hd')">HD</div>
    <div class="style-option" data-model="nano-banana" onclick="selectModel('nano-banana')">标准</div>
  </div>
</div>

<div class="section">
  <h2>选择图片比例</h2>
  <div class="style-selector">
    <div class="style-option" data-ratio="1:1" onclick="selectRatio('1:1')">1:1</div>
    <div class="style-option" data-ratio="16:9" onclick="selectRatio('16:9')">16:9（推荐）</div>
    <div class="style-option" data-ratio="9:16" onclick="selectRatio('9:16')">9:16</div>
    <div class="style-option" data-ratio="21:9" onclick="selectRatio('21:9')">21:9</div>
    <div class="style-option" data-ratio="4:3" onclick="selectRatio('4:3')">4:3</div>
    <div class="style-option" data-ratio="3:4" onclick="selectRatio('3:4')">3:4</div>
    <div class="style-option" data-ratio="3:2" onclick="selectRatio('3:2')">3:2</div>
    <div class="style-option" data-ratio="2:3" onclick="selectRatio('2:3')">2:3</div>
    <div class="style-option" data-ratio="5:4" onclick="selectRatio('5:4')">5:4</div>
    <div class="style-option" data-ratio="4:5" onclick="selectRatio('4:5')">4:5</div>
    <div class="style-option" data-ratio="8:1" onclick="selectRatio('8:1')">8:1</div>
    <div class="style-option" data-ratio="4:1" onclick="selectRatio('4:1')">4:1</div>
    <div class="style-option" data-ratio="1:4" onclick="selectRatio('1:4')">1:4</div>
    <div class="style-option" data-ratio="1:8" onclick="selectRatio('1:8')">1:8</div>
  </div>
</div>

<div id="characterSection" class="section">
  <h2>角色图（面部特写 + 三视图）</h2>
  <div id="characterList" class="item-list"></div>
</div>

<div id="sceneSection" class="section">
  <h2>场景图</h2>
  <div id="sceneList" class="item-list"></div>
</div>

<div class="image-viewer" id="imageViewer" onclick="closeImageViewer()">
  <div class="image-viewer-close">&times;</div>
  <img id="viewerImage" src="" alt="">
</div>

<script>
let selectedStyle = '';
let selectedModel = '';
let selectedRatio = '16:9';  // 默认 16:9
let characters = [];
let scenes = [];

window.onload = function() {
  // 从 localStorage 加载 API key
  const savedKey = localStorage.getItem('nanobanana_api_key');
  if (savedKey) {
    document.getElementById('nanoBananaKey').value = savedKey;
  }

  // 监听 API key 输入变化，自动保存
  document.getElementById('nanoBananaKey').addEventListener('input', function() {
    localStorage.setItem('nanobanana_api_key', this.value);
  });

  // 默认选中 16:9 比例
  selectRatio('16:9');

  loadData();
};

function loadData() {
  const charactersText = sessionStorage.getItem('characters') || '';
  const scenesText = sessionStorage.getItem('scenes') || '';

  if (!charactersText || !scenesText) {
    alert('没有角色和场景数据，请先在主页完成前面的步骤');
    return;
  }

  // 解析角色
  characters = [];
  for (const line of charactersText.split('\\n')) {
    if (!line.includes('|||')) continue;
    const parts = line.split('|||').map(p => p.trim());
    if (parts.length < 2 || parts[0].includes('角色名') || parts[0].includes('姓名')) continue;
    characters.push({
      name: parts[0],
      description: parts.slice(1).join(' '),
      images: [],  // 存储所有生成的图片
      generating: false,
      showPromptEditor: false,
      currentPrompt: ''
    });
  }

  // 解析场景
  scenes = [];
  for (const line of scenesText.split('\\n')) {
    if (!line.includes('|||')) continue;
    const parts = line.split('|||').map(p => p.trim());
    if (parts.length < 2 || parts[0].includes('场景名') || parts[0].includes('名称')) continue;
    scenes.push({
      name: parts[0],
      description: parts.slice(1).join(' '),
      images: [],  // 存储所有生成的图片
      generating: false,
      showPromptEditor: false,
      currentPrompt: ''
    });
  }

  renderLists();
}

function selectStyle(style) {
  selectedStyle = style;
  document.querySelectorAll('.style-option[data-style]').forEach(el => {
    if (el.getAttribute('data-style') === style) {
      el.classList.add('selected');
    } else {
      el.classList.remove('selected');
    }
  });
}

function selectModel(model) {
  selectedModel = model;
  document.querySelectorAll('.style-option[data-model]').forEach(el => {
    if (el.getAttribute('data-model') === model) {
      el.classList.add('selected');
    } else {
      el.classList.remove('selected');
    }
  });
}

function selectRatio(ratio) {
  selectedRatio = ratio;
  document.querySelectorAll('.style-option[data-ratio]').forEach(el => {
    if (el.getAttribute('data-ratio') === ratio) {
      el.classList.add('selected');
    } else {
      el.classList.remove('selected');
    }
  });
}

function selectRatio(ratio) {
  selectedRatio = ratio;
  document.querySelectorAll('.style-option[data-ratio]').forEach(el => {
    if (el.getAttribute('data-ratio') === ratio) {
      el.classList.add('selected');
    } else {
      el.classList.remove('selected');
    }
  });
}

function renderLists() {
  let html = '';
  characters.forEach((char, idx) => {
    html += `<div class="item">
      <div class="item-header">
        <div class="item-info">
          <div class="item-name">${escapeHtml(char.name)}</div>
          <div class="item-desc">${escapeHtml(char.description)}</div>
        </div>
        <div class="item-actions">
          ${char.generating ? '<span class="loading">生成中...</span>' :
            `<button class="btn-small btn-generate" onclick="showPromptEditor('character', ${idx})">生成图片</button>`
          }
        </div>
      </div>
      <div class="prompt-editor ${char.showPromptEditor ? 'show' : ''}" id="prompt-character-${idx}">
        <label>Prompt（可修改）</label>
        <textarea id="prompt-text-character-${idx}">${escapeHtml(char.currentPrompt)}</textarea>
        <div class="controls">
          <label>生成数量：</label>
          <input type="number" id="prompt-count-character-${idx}" value="1" min="1" max="4">
          <button class="btn-small btn-generate" onclick="confirmGenerate('character', ${idx})">确认生成</button>
          <button class="btn-small" onclick="cancelPromptEditor('character', ${idx})" style="background:#999;color:#fff">取消</button>
        </div>
      </div>
      ${char.images.length > 0 ? `<div class="item-images">
        ${char.images.map((img, imgIdx) => `
          <div class="image-version">
            <div class="image-version-header">版本 ${imgIdx + 1} - ${img.timestamp}</div>
            <div class="image-version-images">
              ${img.urls.map(url => `<img src="${url}" alt="${escapeHtml(char.name)}" loading="lazy" onclick="showImageViewer('${url}')">`).join('')}
            </div>
          </div>
        `).join('')}
      </div>` : ''}
    </div>`;
  });
  document.getElementById('characterList').innerHTML = html;

  html = '';
  scenes.forEach((scene, idx) => {
    html += `<div class="item">
      <div class="item-header">
        <div class="item-info">
          <div class="item-name">${escapeHtml(scene.name)}</div>
          <div class="item-desc">${escapeHtml(scene.description)}</div>
        </div>
        <div class="item-actions">
          ${scene.generating ? '<span class="loading">生成中...</span>' :
            `<button class="btn-small btn-generate" onclick="showPromptEditor('scene', ${idx})">生成图片</button>`
          }
        </div>
      </div>
      <div class="prompt-editor ${scene.showPromptEditor ? 'show' : ''}" id="prompt-scene-${idx}">
        <label>Prompt（可修改）</label>
        <textarea id="prompt-text-scene-${idx}">${escapeHtml(scene.currentPrompt)}</textarea>
        <div class="controls">
          <label>生成数量：</label>
          <input type="number" id="prompt-count-scene-${idx}" value="1" min="1" max="4">
          <button class="btn-small btn-generate" onclick="confirmGenerate('scene', ${idx})">确认生成</button>
          <button class="btn-small" onclick="cancelPromptEditor('scene', ${idx})" style="background:#999;color:#fff">取消</button>
        </div>
      </div>
      ${scene.images.length > 0 ? `<div class="item-images">
        ${scene.images.map((img, imgIdx) => `
          <div class="image-version">
            <div class="image-version-header">版本 ${imgIdx + 1} - ${img.timestamp}</div>
            <div class="image-version-images">
              ${img.urls.map(url => `<img src="${url}" alt="${escapeHtml(scene.name)}" loading="lazy" onclick="showImageViewer('${url}')">`).join('')}
            </div>
          </div>
        `).join('')}
      </div>` : ''}
    </div>`;
  });
  document.getElementById('sceneList').innerHTML = html;
}

function showPromptEditor(type, index) {
  if (!selectedStyle) {
    alert('请先选择生成风格');
    return;
  }
  if (!selectedModel) {
    alert('请先选择生成模型');
    return;
  }

  const item = type === 'character' ? characters[index] : scenes[index];

  // 生成默认 prompt
  const style_prefix = {
    "3D玄幻": "3D fantasy style, mystical atmosphere, ",
    "2D动画": "2D animation style, anime art, ",
    "真人电影": "cinematic photography, realistic, movie scene, ",
    "真人古装": "ancient Chinese costume drama, realistic photography, traditional attire, ",
    "3D写实": "3D realistic rendering, photorealistic, high detail, "
  }[selectedStyle] || "";

  if (type === 'character') {
    item.currentPrompt = `${style_prefix}Character design sheet: Large close-up portrait on the left showing detailed facial features, followed by full body character turnaround (front view, side view, back view). Character description: ${item.description}`;
  } else {
    item.currentPrompt = `${style_prefix}Scene design: ${item.description}`;
  }

  item.showPromptEditor = true;
  renderLists();
}

function cancelPromptEditor(type, index) {
  const item = type === 'character' ? characters[index] : scenes[index];
  item.showPromptEditor = false;
  renderLists();
}

function confirmGenerate(type, index) {
  const nanobananaKey = document.getElementById('nanoBananaKey').value.trim();
  if (!nanobananaKey) {
    alert('请先填写 NanoBanana API Key');
    return;
  }

  const item = type === 'character' ? characters[index] : scenes[index];
  const prompt = document.getElementById(`prompt-text-${type}-${index}`).value;
  const count = parseInt(document.getElementById(`prompt-count-${type}-${index}`).value) || 1;

  item.generating = true;
  item.showPromptEditor = false;
  renderLists();

  // 生成多张图片
  const promises = [];
  for (let i = 0; i < count; i++) {
    promises.push(
      fetch('/api/generate_single_image', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          type: type,
          name: item.name,
          prompt: prompt,  // 直接使用用户修改后的 prompt
          model: selectedModel,
          ratio: selectedRatio,
          nanobanana_api_key: nanobananaKey
        })
      }).then(r => r.json())
    );
  }

  Promise.all(promises).then(results => {
    item.generating = false;

    const urls = [];
    const errors = [];
    results.forEach(d => {
      if (d.error) {
        errors.push(d.error);
      } else if (d.url) {
        urls.push(d.url);
      }
    });

    if (urls.length > 0) {
      // 添加新版本
      item.images.push({
        timestamp: new Date().toLocaleString('zh-CN'),
        urls: urls
      });
    }

    if (errors.length > 0) {
      alert(`部分生成失败：${errors.join(', ')}`);
    }

    renderLists();
  }).catch(e => {
    item.generating = false;
    alert('生成失败：' + e);
    renderLists();
  });
}

function goBack() {
  window.location.href = '/';
}

function showImageViewer(url) {
  document.getElementById('viewerImage').src = url;
  document.getElementById('imageViewer').classList.add('show');
}

function closeImageViewer() {
  document.getElementById('imageViewer').classList.remove('show');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/generate-images", methods=["GET"])
def generate_images_page():
    return Response(IMAGE_GEN_HTML, mimetype="text/html")


@app.route("/api/step1", methods=["POST"])
def api_step1():
    """Step 1: 生成推文文案"""
    global _job
    if _job["running"]:
        return jsonify({"error": "当前有任务正在运行，请等待完成后再提交"})

    novel_text = (request.json or {}).get("script", "").strip()
    deepseek_key = (request.json or {}).get("deepseek_api_key", "").strip()

    if not novel_text:
        return jsonify({"error": "剧本内容不能为空"})

    with _job_lock:
        _job = {
            "running": True,
            "status": "Step1 生成推文文案中...",
            "excel_path": None,
            "error": None,
            "results": {},
            "current_step": 0,
            "input_text": novel_text,
            "deepseek_api_key": deepseek_key  # 保存 key
        }

    def _run_step1():
        global _job
        try:
            from pipeline import step1_novel_to_script
            from openai import OpenAI

            # 使用用户提供的 key 或环境变量
            api_key = deepseek_key or os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("缺少 DeepSeek API Key")

            clients = {
                "deepseek": OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            }

            script_text = step1_novel_to_script(clients, novel_text)

            with _job_lock:
                _job["results"]["script"] = script_text
                _job["current_step"] = 1
                _job["status"] = "Step1 完成，请修改文案后进入下一步"
                _job["running"] = False
        except Exception as e:
            with _job_lock:
                _job["error"] = str(e)
                _job["status"] = f"出错：{e}"
                _job["running"] = False

    threading.Thread(target=_run_step1, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/step2", methods=["POST"])
def api_step2():
    """Step 2: 生成角色和场景设定"""
    global _job
    if _job["running"]:
        return jsonify({"error": "当前有任务正在运行，请等待完成后再提交"})

    data = request.json or {}
    script_text = data.get("script", "").strip()
    deepseek_key = data.get("deepseek_api_key", "").strip()

    if not script_text:
        return jsonify({"error": "文案内容不能为空"})

    with _job_lock:
        _job["running"] = True
        _job["status"] = "Step2 生成角色和场景中..."
        _job["results"]["script"] = script_text
        _job["deepseek_api_key"] = deepseek_key

    def _run_step2():
        global _job
        try:
            from pipeline import step2_script_to_characters, step3_script_to_scenes
            from openai import OpenAI

            api_key = deepseek_key or _job.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("缺少 DeepSeek API Key")

            clients = {
                "deepseek": OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            }

            with _job_lock:
                _job["status"] = "Step2 生成角色设定中..."
            characters_text = step2_script_to_characters(clients, script_text)

            with _job_lock:
                _job["results"]["characters"] = characters_text
                _job["status"] = "Step2 生成场景设定中..."
            scenes_text = step3_script_to_scenes(clients, script_text)

            with _job_lock:
                _job["results"]["scenes"] = scenes_text
                _job["current_step"] = 2
                _job["status"] = "Step2 完成，请修改角色场景后进入下一步"
                _job["running"] = False
        except Exception as e:
            with _job_lock:
                _job["error"] = str(e)
                _job["status"] = f"出错：{e}"
                _job["running"] = False

    threading.Thread(target=_run_step2, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/step3", methods=["POST"])
def api_step3():
    """Step 3: 生成分镜脚本"""
    global _job
    if _job["running"]:
        return jsonify({"error": "当前有任务正在运行，请等待完成后再提交"})

    data = request.json or {}
    script_text = data.get("script", "").strip()
    characters_text = data.get("characters", "").strip()
    scenes_text = data.get("scenes", "").strip()
    deepseek_key = data.get("deepseek_api_key", "").strip()

    if not all([script_text, characters_text, scenes_text]):
        return jsonify({"error": "文案、角色、场景内容不能为空"})

    with _job_lock:
        _job["running"] = True
        _job["status"] = "Step3 生成分镜脚本中..."
        _job["results"]["script"] = script_text
        _job["results"]["characters"] = characters_text
        _job["results"]["scenes"] = scenes_text
        _job["deepseek_api_key"] = deepseek_key

    def _run_step3():
        global _job
        try:
            from pipeline import step4_scenes_to_storyboard, save_excel
            from datetime import datetime
            from pathlib import Path
            from openai import OpenAI

            api_key = deepseek_key or _job.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("缺少 DeepSeek API Key")

            clients = {
                "deepseek": OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            }

            storyboard_text = step4_scenes_to_storyboard(
                clients, script_text, characters_text, scenes_text
            )

            with _job_lock:
                _job["results"]["storyboard"] = storyboard_text
                _job["status"] = "正在生成 Excel..."

            # 保存 Excel
            excel_path = f"output/result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            save_excel(script_text, characters_text, scenes_text, storyboard_text, excel_path)

            # 保存历史记录
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_file = f"output/history_{timestamp}.json"
            Path("output").mkdir(exist_ok=True)
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp,
                    "excel_path": excel_path,
                    "results": _job["results"],
                    "input_length": len(_job.get("input_text", ""))
                }, f, ensure_ascii=False, indent=2)

            with _job_lock:
                _job["excel_path"] = excel_path
                _job["current_step"] = 3
                _job["status"] = "全部完成，可以下载 Excel"
                _job["running"] = False
        except Exception as e:
            with _job_lock:
                _job["error"] = str(e)
                _job["status"] = f"出错：{e}"
                _job["running"] = False

    threading.Thread(target=_run_step3, daemon=True).start()
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
            "current_step": _job.get("current_step", 0),
        })


@app.route("/api/generate_single_image", methods=["POST"])
def api_generate_single_image():
    """生成单个角色或场景图"""
    try:
        import requests

        data = request.json or {}
        item_type = data.get("type")  # "character" or "scene"
        name = data.get("name")
        prompt = data.get("prompt")  # 直接使用的 prompt（优先）
        description = data.get("description")  # 描述（用于自动生成 prompt）
        style = data.get("style")  # 风格选择
        model = data.get("model")  # 模型选择
        ratio = data.get("ratio", "16:9")  # 图片比例，默认 16:9
        nanobanana_key = data.get("nanobanana_api_key", "").strip()

        api_key = nanobanana_key or os.environ.get("NANOBANANA_API_KEY")
        if not api_key:
            return jsonify({"error": "缺少 NanoBanana API Key"}), 500

        if not model:
            return jsonify({"error": "请选择生成模型"}), 400

        api_url = "https://api.bltcy.ai/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 如果没有直接提供 prompt，则根据描述和风格生成
        if not prompt:
            style_prefix = {
                "3D玄幻": "3D fantasy style, mystical atmosphere, ",
                "2D动画": "2D animation style, anime art, ",
                "真人电影": "cinematic photography, realistic, movie scene, ",
                "真人古装": "ancient Chinese costume drama, realistic photography, traditional attire, ",
                "3D写实": "3D realistic rendering, photorealistic, high detail, "
            }.get(style, "")

            if item_type == "character":
                prompt = f"{style_prefix}Character design sheet: Large close-up portrait on the left showing detailed facial features, followed by full body character turnaround (front view, side view, back view). Character description: {description}"
            else:
                prompt = f"{style_prefix}Scene design: {description}"

        payload = {
            "prompt": prompt,
            "model": model,
            "n": 1
        }

        # 添加 aspect_ratio 参数（如果不是默认值）
        if ratio:
            payload["aspect_ratio"] = ratio

        response = requests.post(api_url, headers=headers, json=payload, timeout=180)

        if response.status_code == 200:
            result = response.json()
            if 'data' in result and len(result['data']) > 0:
                image_url = result['data'][0].get('url', '')
                return jsonify({"ok": True, "url": image_url})
            else:
                return jsonify({"error": "API 返回数据格式错误"}), 500
        else:
            error_msg = response.text
            return jsonify({"error": f"API 调用失败 ({response.status_code}): {error_msg}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/step4", methods=["POST"])
def api_step4():
    """Step 4: 生成角色图和场景图"""
    global _job
    if _job["running"]:
        return jsonify({"error": "当前有任务正在运行，请等待完成后再提交"})

    data = request.json or {}
    characters_text = data.get("characters", "").strip()
    scenes_text = data.get("scenes", "").strip()

    if not all([characters_text, scenes_text]):
        return jsonify({"error": "角色和场景内容不能为空"})

    with _job_lock:
        _job["running"] = True
        _job["status"] = "Step4 生成角色图和场景图中..."

    def _run_step4():
        global _job
        try:
            import requests

            api_key = os.environ.get("NANOBANANA_API_KEY")
            if not api_key:
                raise RuntimeError("缺少 NANOBANANA_API_KEY")

            api_url = "https://api.bltcy.ai/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            # 解析角色
            character_images = {}
            for line in characters_text.split('\n'):
                if '|||' not in line:
                    continue
                parts = [p.strip() for p in line.split('|||')]
                if len(parts) < 2 or any(col in line for col in ['角色名', '姓名', '名字']):
                    continue

                character_name = parts[0]
                character_desc = ' '.join(parts[1:])

                with _job_lock:
                    _job["status"] = f"正在生成角色图：{character_name}"

                response = requests.post(api_url, headers=headers, json={
                    "prompt": f"角色设定：{character_desc}",
                    "n": 1,
                    "size": "1024x1024"
                })

                if response.status_code == 200:
                    result = response.json()
                    if 'data' in result and len(result['data']) > 0:
                        character_images[character_name] = result['data'][0].get('url', '')

            # 解析场景
            scene_images = {}
            for line in scenes_text.split('\n'):
                if '|||' not in line:
                    continue
                parts = [p.strip() for p in line.split('|||')]
                if len(parts) < 2 or any(col in line for col in ['场景名', '名称']):
                    continue

                scene_name = parts[0]
                scene_desc = ' '.join(parts[1:])

                with _job_lock:
                    _job["status"] = f"正在生成场景图：{scene_name}"

                response = requests.post(api_url, headers=headers, json={
                    "prompt": f"场景设定：{scene_desc}",
                    "n": 1,
                    "size": "1024x1024"
                })

                if response.status_code == 200:
                    result = response.json()
                    if 'data' in result and len(result['data']) > 0:
                        scene_images[scene_name] = result['data'][0].get('url', '')

            with _job_lock:
                _job["results"]["character_images"] = character_images
                _job["results"]["scene_images"] = scene_images
                _job["current_step"] = 4
                _job["status"] = "Step4 完成，角色图和场景图已生成"
                _job["running"] = False

        except Exception as e:
            with _job_lock:
                _job["error"] = str(e)
                _job["status"] = f"出错：{e}"
                _job["running"] = False

    threading.Thread(target=_run_step4, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/regenerate_excel", methods=["POST"])
def api_regenerate_excel():
    """根据当前编辑的内容重新生成 Excel"""
    global _job
    data = request.json or {}
    script_text = data.get("script", "").strip()
    characters_text = data.get("characters", "").strip()
    scenes_text = data.get("scenes", "").strip()
    storyboard_text = data.get("storyboard", "").strip()

    if not all([script_text, characters_text, scenes_text, storyboard_text]):
        return jsonify({"error": "内容不完整，无法生成 Excel"})

    try:
        from pipeline import save_excel
        from datetime import datetime
        from pathlib import Path

        excel_path = f"output/result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_excel(script_text, characters_text, scenes_text, storyboard_text, excel_path)

        # 保存历史记录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        history_file = f"output/history_{timestamp}.json"
        Path("output").mkdir(exist_ok=True)
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "excel_path": excel_path,
                "results": {
                    "script": script_text,
                    "characters": characters_text,
                    "scenes": scenes_text,
                    "storyboard": storyboard_text
                },
                "input_length": len(_job.get("input_text", ""))
            }, f, ensure_ascii=False, indent=2)

        with _job_lock:
            _job["excel_path"] = excel_path

        return jsonify({"ok": True, "excel_path": excel_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["GET"])
def api_download():
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
    for f in history_files[:20]:
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

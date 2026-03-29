---
name: manga-server
description: 启动漫剧 AI 工作流服务器
tags: [server, manga, pipeline]
---

# 漫剧 AI 工作流服务器

启动漫剧 pipeline 的 Web 服务器，提供完整的剧本处理工作流。

## 功能

- **主页** (http://localhost:5000)
  - 生成推文文案（800字以内）
  - 生成角色和场景设定
  - 生成分镜脚本（语音40字以内/镜头）
  - 表格可直接编辑
  - 导出 Excel

- **图片生成页** (点击"生成角色场景图"跳转)
  - 选择风格（3D玄幻/2D动画/真人电影/真人古装/3D写实）
  - 角色图：面部特写 + 三视图
  - 场景图：场景设计
  - 单独生成控制

## 使用步骤

1. 启动服务器
2. 在浏览器中打开 http://localhost:5000
3. 填写 API Keys（DeepSeek 和 NanoBanana）
4. 粘贴剧本内容
5. 按照工作流逐步生成和编辑
6. 导出 Excel 或生成图片

## 执行

启动服务器：

```bash
cd "D:\Desktop\漫剧\pipeline" && python server.py
```

服务器将在后台运行，访问地址：http://localhost:5000

## 停止服务器

如果需要停止服务器，使用 Ctrl+C 或查找并终止 Python 进程。

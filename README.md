# 漫剧 AI 工作流

把剧本丢进网页，点一个按钮，自动生成推文文案、角色设定、场景设定、分镜脚本，还能生成角色和场景的参考图，结果打包成 Excel 下载。

```
浏览器粘贴剧本 → 点「开始生成」
        ↓
Step 1：改写成第一人称短视频解说文案（800字）
        ↓
Step 2：提取所有角色设定
        ↓
Step 3：提取所有场景设定
        ↓
Step 4：生成分镜脚本（适配 Seedance 2.0 / 即梦，语音40字/镜头）
        ↓
下载 Excel（含全部 4 个 Sheet）
        ↓
（可选）生成角色图和场景图（支持多种风格）
```

---

## 快速开始（3 步）

### 第一步：安装依赖

```bash
git clone https://github.com/mokscreate/manga-pipeline.git
cd manga-pipeline
pip install -r requirements.txt
```

---

### 第二步：启动服务器

```bash
python server.py
```

启动后打开浏览器访问：**http://localhost:5000**

---

### 第三步：填写 API Key 并使用

1. **在网页顶部填写 API Keys**：
   - **DeepSeek API Key**：用于生成文案、角色、场景、分镜
     - 注册地址：https://platform.deepseek.com/
   - **NanoBanana API Key**（可选）：用于生成角色和场景图片
     - API 地址：https://api.bltcy.ai

2. **粘贴剧本内容**（完整剧本或草稿均可）

3. **点「开始生成」**，等待进度条走完（约 2–5 分钟）

4. **逐步编辑**：
   - 生成推文文案后可以修改
   - 生成角色场景后可以在表格中直接编辑
   - 生成分镜后可以在表格中直接编辑

5. **点「导出 Excel」**获取结果

6. **（可选）生成图片**：
   - 点击「生成角色场景图」跳转到图片生成页面
   - 选择风格（3D玄幻/2D动画/真人电影/真人古装/3D写实）
   - 为每个角色和场景单独生成图片
   - 角色图包含：面部特写 + 三视图（正面/侧面/背面）

> **输入字数说明**
> | 输入类型 | 说明 |
> |---------|------|
> | 完整剧本（800字以上） | 直接改写成解说文案 |
> | 不完整构思（800字以下） | AI 自动展开创作 |

> **API Key 说明**
> - API Key 保存在浏览器本地（localStorage），不会上传到服务器
> - 每次打开页面会自动填充之前保存的 Key
> - 如果不想在网页填写，也可以在 `.env` 文件中配置（见下方）

---

## 可选：在 .env 文件中配置 API Key

如果不想每次在网页填写 API Key，可以创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`，填写：

```
DEEPSEEK_API_KEY=sk-你的DeepSeekKey
NANOBANANA_API_KEY=sk-你的NanoBananaKey
```

---

## 也可以命令行运行（不启动服务器）

```bash
# 从 txt 文件运行
python pipeline.py 你的剧本.txt
```

结果保存在 `output/` 目录下的 Excel 文件里。

---

## 使用 Claude Code Skill（可选）

如果你使用 [Claude Code](https://claude.ai/code)，项目已包含一个便捷的 skill：

```
/manga-server
```

这个命令会显示：
- 完整的功能说明
- 启动命令
- 使用步骤

Skill 文件位置：`.claude/skills/manga-server.md`

---

## 功能特性

### 主页功能
- ✅ 推文文案生成（严格控制 800 字以内）
- ✅ 角色和场景设定提取
- ✅ 分镜脚本生成（语音时长控制在 40 字/镜头）
- ✅ 表格可直接编辑（点击单元格修改，可添加/删除行）
- ✅ 分步工作流（每步完成后可编辑再进入下一步）
- ✅ 历史记录查看
- ✅ 导出 Excel

### 图片生成页功能
- ✅ 5 种风格选择（3D玄幻/2D动画/真人电影/真人古装/3D写实）
- ✅ 角色图：面部特写 + 全身三视图
- ✅ 场景图：场景设计
- ✅ 单独生成控制（每个角色/场景独立生成按钮）
- ✅ 支持重新生成

---

## 修改 AI Prompt

prompt 存储在 `prompts/` 目录下，直接编辑对应文件即可：

| 文件 | 对应步骤 |
|------|----------|
| `prompts/step1_novel_to_script.py` | 推文文案改写 |
| `prompts/step2_script_to_characters.py` | 角色提取 |
| `prompts/step3_script_to_scenes.py` | 场景提取 |
| `prompts/step4_scenes_to_storyboard.py` | 分镜生成 |

---

## 可选：飞书多维表格集成

如果需要把结果自动写入飞书多维表格，额外配置以下内容：

### 创建飞书机器人

1. 打开 https://open.feishu.cn/app
2. 点「创建企业自建应用」，填写名称
3. 进入应用 → **凭证与基础信息**，复制 `App ID` 和 `App Secret`
4. **权限管理** → 开启 `bitable:app` 权限
5. **版本管理与发布** → 发布应用

### 创建飞书多维表格

1. 新建一个多维表格，URL 里的 `xxxxxxxx` 就是 `FEISHU_APP_TOKEN`
2. 右上角「···」→「添加文档应用」→ 搜索刚才创建的应用，设为**可管理**
3. 手动创建「**输入**」数据表，添加字段：`剧本内容`（文本）、`状态`（文本）

### 补充 .env 配置

```
FEISHU_APP_ID=cli_你的AppID
FEISHU_APP_SECRET=你的AppSecret
FEISHU_APP_TOKEN=你的多维表格Token
```

### 配置飞书自动化按钮（需要 ngrok）

1. 注册 https://ngrok.com/ 免费账号，申请固定域名
2. 启动 ngrok：
   ```bash
   ./ngrok http --domain=你的固定域名.ngrok-free.app 5000
   ```
3. 在飞书多维表格「自动化」里新建规则：
   - 触发条件：**点击按钮时**
   - 执行动作：**发送 HTTP 请求**
   - URL：`https://你的固定域名.ngrok-free.app/webhook`
   - 方法：POST，Body：`{"source": "feishu"}`

也可以直接命令行触发飞书模式：
```bash
python pipeline.py --feishu
```

---

## 常见问题

**Q：浏览器打开 localhost:5000 没反应？**
A：确认 `python server.py` 已经在运行，检查终端有无报错。

**Q：生成失败，提示缺少 API Key？**
A：检查 `.env` 文件是否存在，`DEEPSEEK_API_KEY` 是否正确填写（以 `sk-` 开头）。

**Q：飞书写入报错 FieldNameNotFound？**
A：删掉飞书里的「分镜」表，下次运行会用新字段自动重建。

**Q：状态字段没有变化？**
A：检查飞书机器人是否有 `bitable:app` 权限，以及是否已添加为表格的可管理成员。

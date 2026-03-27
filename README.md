# 漫剧 AI 工作流

把剧本丢进网页，点一个按钮，自动生成推文文案、角色设定、场景设定、分镜脚本，结果打包成 Excel 下载。

```
浏览器粘贴剧本 → 点「开始生成」
        ↓
Step 1：改写成第一人称短视频解说文案
        ↓
Step 2：提取所有角色设定
        ↓
Step 3：提取所有场景设定
        ↓
Step 4：生成分镜脚本（适配 Seedance 2.0 / 即梦）
        ↓
下载 Excel（含全部 4 个 Sheet）
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

### 第二步：填写 API Key

1. 打开 https://platform.deepseek.com/ 注册并创建一个 API Key
2. 复制项目里的 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

3. 编辑 `.env`，只需填一行：

```
DEEPSEEK_API_KEY=sk-你的DeepSeekKey
```

---

### 第三步：启动并使用

```bash
python server.py
```

启动后打开浏览器访问：**http://localhost:5000**

1. 粘贴剧本内容（完整剧本或草稿均可）
2. 点「开始生成」
3. 等待进度条走完（约 2–5 分钟，取决于剧本长度）
4. 点「下载 Excel」获取结果

> **输入字数说明**
> | 输入类型 | 说明 |
> |---------|------|
> | 完整剧本（800字以上） | 直接改写成解说文案 |
> | 不完整构思（800字以下） | AI 自动展开创作 |

---

## 也可以命令行运行（不启动服务器）

```bash
# 从 txt 文件运行
python pipeline.py 你的剧本.txt
```

结果保存在 `output/` 目录下的 Excel 文件里。

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

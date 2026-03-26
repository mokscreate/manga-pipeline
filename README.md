# 漫剧 AI 工作流

把剧本丢进去，自动生成推文文案、角色设定、场景设定、分镜脚本，直接写入飞书多维表格，队友可在线协同。

---

## 这个流程干什么的

```
你输入剧本（或构思）
        ↓
Step 1：改写成第一人称短视频解说文案
        ↓
Step 2：提取所有角色设定
        ↓
Step 3：提取所有场景设定
        ↓
Step 4：生成分镜脚本（适配 Seedance 2.0 / 即梦）
        ↓
写入飞书多维表格 + 保存 Excel 备份
```

---

## 第一次使用前的准备

### 1. 安装依赖

```bash
cd D:/Desktop/漫剧/pipeline
pip install -r requirements.txt
pip install requests
```

### 2. 配置 API Key

打开 `config.py`，填入你的 DeepSeek API Key：

```python
# 找到这一行，改成你自己的 key
DEEPSEEK_API_KEY = "sk-你的key"
```

> 飞书配置已经填好，不用动。

---

## 怎么用

### 方式一：直接粘贴剧本（推荐）

```bash
cd D:/Desktop/漫剧/pipeline
DEEPSEEK_API_KEY=sk-你的key python pipeline.py
```

运行后会提示你粘贴内容，粘贴完成后：
- Windows：按 `Ctrl+Z`，然后回车
- Mac/Linux：按 `Ctrl+D`

### 方式二：传入 txt 文件

把剧本保存成 txt 文件，然后：

```bash
DEEPSEEK_API_KEY=sk-你的key python pipeline.py 你的剧本.txt
```

---

## 输入支持两种情况

| 情况 | 说明 |
|------|------|
| 完整剧本（800字以上） | 直接改写成解说文案 |
| 不完整构思（800字以下） | AI 自动展开创作成完整文案 |

不用手动区分，程序会自动判断。

---

## 结果在哪里看

**飞书多维表格（推荐，可协同）：**
https://ix6mi6ge1v7.feishu.cn/base/I4AibJ2IDa2yVisgPOjc5A8AnJc

**本地 Excel 备份：**
`pipeline/output/` 文件夹里，文件名带时间戳，例如 `result_20260326_173059.xlsx`

两个地方内容一样，飞书是给队友看的，Excel 是本地备份。

---

## 飞书表格里有哪些内容

| Sheet | 内容 |
|-------|------|
| 推文文案 | 第一人称短视频解说文案，每段一行 |
| 角色 | 所有角色的性别、年龄、性格、外貌、服装道具 |
| 场景 | 所有场景的环境、氛围、道具清单 |
| 分镜 | 每个镜头的景别、运镜、画面描述、对白、时长 |

每次运行会清空旧数据，写入新内容。

---

## 文件说明

```
pipeline/
├── pipeline.py        主程序，运行这个
├── config.py          配置文件（API Key、飞书配置）
├── feishu.py          飞书写入模块
├── prompts/           每个步骤的 AI 提示词
│   ├── step1_novel_to_script.py     剧本→文案
│   ├── step2_script_to_characters.py 文案→角色
│   ├── step3_script_to_scenes.py    文案→场景
│   └── step4_scenes_to_storyboard.py 文案→分镜
├── output/            Excel 备份输出目录
└── requirements.txt   依赖列表
```

---

## 常见问题

**Q：运行报错 `DEEPSEEK_API_KEY` 缺失？**
A：在命令前加上 `DEEPSEEK_API_KEY=sk-你的key`，或者直接在 `config.py` 里写死。

**Q：飞书写入报错 Forbidden？**
A：确认飞书多维表格已将应用添加为可编辑成员（表格右上角「分享」→添加应用）。

**Q：分镜 Sheet 是空的？**
A：DeepSeek 偶尔不按格式输出，重新跑一次通常能解决。

**Q：Excel 报错 PermissionError？**
A：把 output 文件夹里的 xlsx 文件关掉（不要在 Excel 里打开着），再重新跑。

# ============================================================
# config.py  —  全局配置，按需修改
# ============================================================

# ── 每个步骤的模型配置 ──────────────────────────────────────
# provider: "claude" 或 "deepseek"
# model:    对应的模型名称
STEP_CONFIG = {
    "novel_to_script": {
        "provider": "deepseek",
        "model":    "deepseek-chat",   # 或 "deepseek-reasoner"
        "max_tokens": 8000,
    },
    "script_to_characters": {
        "provider": "deepseek",
        "model":    "deepseek-chat",
        "max_tokens": 4000,
    },
    "script_to_scenes": {
        "provider": "deepseek",
        "model":    "deepseek-chat",
        "max_tokens": 4000,
    },
    "scenes_to_storyboard": {
        "provider": "deepseek",
        "model":    "deepseek-chat",
        "max_tokens": 8000,
    },
}

# ── 输出路径 ─────────────────────────────────────────────────
import datetime as _dt
OUTPUT_EXCEL = f"output/result_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

# ── 飞书多维表格配置 ──────────────────────────────────────────
FEISHU_APP_ID    = "cli_a926dc4074389bca"
FEISHU_APP_SECRET = "q4WMKWj7ZBF7vzFUflMusZJ1fY7q8gqy"
FEISHU_APP_TOKEN = "I4AibJ2IDa2yVisgPOjc5A8AnJc"

# ── Excel 列定义（Step2/3/4 结构化表格） ─────────────────────
SHEET_COLUMNS = {
    "角色": ["序号", "角色名", "性别", "年龄", "性格特点", "外貌描述", "服装道具", "备注"],
    "场景": ["序号", "场景名", "室内外", "时间", "环境描述", "氛围", "道具清单", "备注"],
    "分镜": ["镜头编号", "所属场次", "时间段", "运镜", "画面描述", "对白/音效", "备注"],
}

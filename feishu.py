"""
feishu.py — 飞书多维表格读写模块
- 从「输入」表读取剧本
- 将四个步骤的输出写入对应数据表
"""

import os
import time
import requests

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import SHEET_COLUMNS

FEISHU_APP_ID     = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_APP_TOKEN  = os.environ.get("FEISHU_APP_TOKEN", "")


# ── Token 管理 ────────────────────────────────────────────────

def get_token() -> str:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 Token 失败：{data}")
    return data["tenant_access_token"]


# ── 数据表管理 ────────────────────────────────────────────────

def list_tables(token: str) -> dict:
    """返回 {表名: table_id} 映射。"""
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    items = resp.json().get("data", {}).get("items", [])
    return {item["name"]: item["table_id"] for item in items}


def create_table(token: str, name: str, fields: list) -> str:
    """创建数据表，返回 table_id。"""
    field_defs = [{"field_name": f, "type": 1} for f in fields]  # type=1 文本
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"table": {"name": name, "fields": field_defs}},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建数据表 [{name}] 失败：{data}")
    return data["data"]["table_id"]


def ensure_table(token: str, name: str, fields: list, existing: dict) -> str:
    """存在则返回 table_id，不存在则创建。"""
    if name in existing:
        return existing[name]
    return create_table(token, name, fields)


def clear_table(token: str, table_id: str):
    """删除表内所有记录。"""
    while True:
        resp = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 100},
            timeout=10,
        )
        items = resp.json().get("data", {}).get("items", [])
        if not items:
            break
        record_ids = [item["record_id"] for item in items]
        requests.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/batch_delete",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"records": record_ids},
            timeout=10,
        )
        time.sleep(0.3)


def batch_insert(token: str, table_id: str, rows: list):
    """分批写入记录，每批 100 条。"""
    for i in range(0, len(rows), 100):
        batch = rows[i:i + 100]
        records = [{"fields": {k: str(v) for k, v in row.items()}} for row in batch]
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/batch_create",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"records": records},
            timeout=15,
        )
        if resp.json().get("code") != 0:
            print(f"  ⚠ 写入第 {i+1}-{i+len(batch)} 条时出错：{resp.json()}")
        time.sleep(0.3)


# ── 从「输入」表读取剧本 ──────────────────────────────────────

def read_input_from_feishu(token: str) -> tuple[str, str]:
    """
    读取「输入」表中状态为空或「待处理」的第一条记录。
    返回 (record_id, 剧本内容)。
    """
    tables = list_tables(token)
    table_id = tables.get("输入")
    if not table_id:
        raise RuntimeError("飞书多维表格中未找到「输入」表，请先创建。")

    resp = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 10},
        timeout=10,
    )
    items = resp.json().get("data", {}).get("items", [])
    if not items:
        raise RuntimeError("「输入」表中没有记录，请先在飞书填入剧本内容。")

    # 找第一条状态不是「已完成」的记录
    for item in items:
        fields = item.get("fields", {})
        status = str(fields.get("状态", "")).strip()
        content = str(fields.get("剧本内容", "")).strip()
        if status != "已完成" and content:
            return item["record_id"], content

    raise RuntimeError("「输入」表中所有记录状态均为「已完成」，没有待处理的剧本。")


def mark_input_done(token: str, record_id: str, status: str = "已完成", field: str = "状态"):
    """更新该条记录的指定状态字段。"""
    tables = list_tables(token)
    table_id = tables["输入"]
    requests.put(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/{record_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"fields": {field: status}},
        timeout=10,
    )




def parse_table(raw: str, columns: list) -> list:
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|||" not in line:
            continue
        if any(col in line for col in columns[:3]):
            continue
        parts = [p.strip() for p in line.split("|||")]
        while len(parts) < len(columns):
            parts.append("")
        rows.append(dict(zip(columns, parts[:len(columns)])))
    return rows


def parse_script_paragraphs(script_text: str) -> list:
    paras = [p.strip() for p in script_text.splitlines() if p.strip()]
    return [{"序号": str(i + 1), "段落内容": p} for i, p in enumerate(paras)]


# ── Prompt 表管理 ─────────────────────────────────────────────

PROMPT_STEPS = [
    "step1_novel_to_script",
    "step2_script_to_characters",
    "step3_script_to_scenes",
    "step4_scenes_to_storyboard",
]


def read_prompts_from_feishu(token: str) -> dict:
    """从飞书「prompt」表读取所有步骤的prompt，返回 {步骤名: prompt内容}。"""
    tables = list_tables(token)
    table_id = tables.get("prompt")
    if not table_id:
        return {}
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 20},
        timeout=10,
    )
    items = resp.json().get("data", {}).get("items", [])
    result = {}
    for item in items:
        fields = item.get("fields", {})
        step = str(fields.get("步骤名", "")).strip()
        content = str(fields.get("prompt内容", "")).strip()
        if step and content:
            result[step] = content
    return result


def init_prompts_to_feishu(token: str, prompts: dict):
    """将本地prompt初始化写入飞书「prompt」表（仅首次，表不存在时创建）。"""
    existing = list_tables(token)
    table_id = ensure_table(token, "prompt", ["步骤名", "prompt内容"], existing)
    # 清空后重写
    clear_table(token, table_id)
    rows = [{"步骤名": k, "prompt内容": v} for k, v in prompts.items()]
    batch_insert(token, table_id, rows)
    print(f"  ✓ 飞书[prompt]表已初始化，{len(rows)} 个步骤")


# ── 主写入入口 ────────────────────────────────────────────────

def save_to_feishu(script_text, characters_text, scenes_text, storyboard_text):
    print("\n📡 正在写入飞书多维表格...")
    token = get_token()
    existing = list_tables(token)

    sheets = [
        ("推文文案",  ["序号", "段落内容"],              parse_script_paragraphs(script_text)),
        ("角色",      SHEET_COLUMNS["角色"],             parse_table(characters_text, SHEET_COLUMNS["角色"])),
        ("场景",      SHEET_COLUMNS["场景"],             parse_table(scenes_text,     SHEET_COLUMNS["场景"])),
        ("分镜",      SHEET_COLUMNS["分镜"],             parse_table(storyboard_text, SHEET_COLUMNS["分镜"])),
    ]

    for name, fields, rows in sheets:
        table_id = ensure_table(token, name, fields, existing)
        clear_table(token, table_id)
        batch_insert(token, table_id, rows)
        print(f"  ✓ [{name}]：{len(rows)} 条记录已写入")

    print(f"\n✅ 飞书多维表格更新完成：https://ix6mi6ge1v7.feishu.cn/base/{FEISHU_APP_TOKEN}")

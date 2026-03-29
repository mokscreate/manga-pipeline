import requests
import json
import os

# 从环境变量读取 API key
api_key = os.environ.get("NANOBANANA_API_KEY")
if not api_key:
    print("请先设置 NANOBANANA_API_KEY 环境变量")
    exit(1)

api_url = "https://api.bltcy.ai/v1/images/generations"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 测试请求 - 先试 nanobanana-2
payload = {
    "prompt": "a cute cat",
    "model": "nanobanana-2",
    "n": 1,
    "size": "1024x1024"
}

print("正在调用 API (model: nanobanana-2)...")
print(f"请求参数: {json.dumps(payload, indent=2, ensure_ascii=False)}")
print()

try:
    response = requests.post(api_url, headers=headers, json=payload, timeout=60)

    print(f"状态码: {response.status_code}")
    print()

    if response.status_code == 200:
        result = response.json()
        print("完整响应:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"错误响应: {response.text}")
        print()
        print("尝试 nanobanana-pro...")

        payload["model"] = "nanobanana-pro"
        response2 = requests.post(api_url, headers=headers, json=payload, timeout=60)
        print(f"状态码: {response2.status_code}")
        if response2.status_code == 200:
            result2 = response2.json()
            print("完整响应:")
            print(json.dumps(result2, indent=2, ensure_ascii=False))
        else:
            print(f"错误响应: {response2.text}")

except Exception as e:
    print(f"请求失败: {e}")

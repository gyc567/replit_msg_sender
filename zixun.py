"""
Mlion 新闻监控模块
⚠️ 此模块已禁用，如需启用请重命名为 zixun.py
"""

# 功能已禁用
import sys

print("⚠️ zixun.py 已禁用，如需启用请重命名文件")
sys.exit(0)

# 以下代码保留但不会执行
import os
import requests
import time
import schedule
import json

# ================= 配置区域 =================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TOPIC_ID = int(os.environ.get("ZIXUN_TOPIC_ID", "4"))

API_URL = os.environ.get(
    "MLION_API_URL",
    "https://api.mlion.ai/v2/api/news/real/time?language=cn&time_zone=Asia%2FShanghai&num=100&page=1&client=mlion&is_hot=Y",
)
MLION_API_KEY = os.environ.get("MLION_API_KEY")

# ✅ 修复 4001 错误：添加 Authorization 头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    # 大多数 API 使用 Bearer Token 格式，如果 Mlion 文档不一样，请修改这里
    "Authorization": f"Bearer {MLION_API_KEY}",
    "token": MLION_API_KEY,  # 为了保险，有些API直接用 token 字段，我都加上
}

# ======================= 验证配置 =======================
if not os.environ.get("TELEGRAM_BOT_TOKEN"):
    raise EnvironmentError("缺少必要配置: TELEGRAM_BOT_TOKEN")
if not os.environ.get("TELEGRAM_CHAT_ID"):
    raise EnvironmentError("缺少必要配置: TELEGRAM_CHAT_ID")
if not MLION_API_KEY:
    raise EnvironmentError("缺少必要配置: MLION_API_KEY")
# ========================================================

# 用于记录上一条新闻的 ID 或时间，防止重复发送
STATE_FILE = ".zixun_state.json"


def load_last_fingerprint():
    """从文件加载上一条新闻指纹"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_fingerprint")
    except Exception as e:
        print(f"加载状态文件失败: {e}")
    return None


def save_last_fingerprint(fingerprint):
    """保存新闻指纹到文件"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_fingerprint": fingerprint}, f)
    except Exception as e:
        print(f"保存状态文件失败: {e}")


last_news_fingerprint = load_last_fingerprint()
if last_news_fingerprint:
    print(f"已加载上次记录: {last_news_fingerprint}")


def get_latest_news():
    """
    获取新闻数据的函数
    """
    global last_news_fingerprint

    # 检查是否配置了 Key，如果没有，直接报错提醒
    if not MLION_API_KEY:
        print(
            "❌ 错误：你还没有配置 MLION_API_KEY！请在 Secrets 中配置或直接修改代码。"
        )
        return None

    try:
        print(f"[DEBUG] 正在请求 Mlion API... URL: {API_URL}")
        # ✅ 使用修复后的 headers 发送请求
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        print(f"[DEBUG] API 响应状态码: {response.status_code}")

        if response.status_code != 200:
            # 如果还是 4001，说明 Key 可能是错的，或者格式不对
            print(f"API 请求失败: {response.status_code} - {response.text}")
            return None

        data = response.json()

        # 双重检查 API 内部错误码
        if (
            isinstance(data, dict)
            and data.get("code") != 0
            and data.get("code", 0) != 200
        ):
            print(
                f"API 错误: code={data.get('code')}, message={data.get('message', data.get('msg', 'Unknown'))}"
            )
            return None

        # 数据解析逻辑 (v2 接口)
        latest_news = None
        if isinstance(data, dict) and "data" in data:
            content_list = data["data"]
            if isinstance(content_list, list) and len(content_list) > 0:
                latest_news = content_list[0]
        elif isinstance(data, list) and len(data) > 0:
            latest_news = data[0]

        if not latest_news:
            return None

        # 简单去重
        current_fingerprint = (
            latest_news.get("id")
            or latest_news.get("pub_time")
            or latest_news.get("title")
        )

        # 调试打印，方便你看数据结构（正式运行时可注释掉）
        # print(f"DEBUG: 获取到的最新新闻指纹: {current_fingerprint}")

        if current_fingerprint == last_news_fingerprint:
            return None  # 没有新消息

        last_news_fingerprint = current_fingerprint
        save_last_fingerprint(current_fingerprint)  # 保存到文件
        return latest_news

    except Exception as e:
        print(f"获取新闻出错: {e}")
        return None


def format_message(news):
    """
    核心美化函数
    """
    if not news:
        return None

    title = news.get("title", "无标题")
    content = news.get("content", "暂无摘要")
    time_str = news.get("pub_time", "")

    # 有些 API 返回的时间戳是数字，处理一下
    if isinstance(time_str, (int, float)):
        # 这里假设是秒级时间戳，如果是毫秒需 /1000
        import datetime

        try:
            time_str = datetime.datetime.fromtimestamp(int(time_str)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except:
            pass

    # 处理标签
    tags_list = news.get("tags", [])
    if isinstance(tags_list, str):
        tags = tags_list
    elif isinstance(tags_list, list):
        tags = " ".join([f"#{t}" for t in tags_list])
    else:
        tags = ""

    link = news.get("url", "")

    message = (
        f"<b>📰 Mlion 快讯</b>\n\n"
        f"<b>• {title}</b>\n\n"
        f"🗓 {time_str} | {tags}\n\n"
        f"{content}\n\n"
    )

    if link:
        message += f"<a href='{link}'>🔗 查看详情</a>"

    return message


def send_telegram_message(text):
    if not text:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    if TOPIC_ID:
        payload["message_thread_id"] = TOPIC_ID

    try:
        print(f"[DEBUG] 正在发送 Telegram 消息到 Chat: {CHAT_ID}, Topic: {TOPIC_ID}")
        resp = requests.post(url, json=payload, timeout=10)
        resp_json = resp.json()

        if resp.status_code == 200 and resp_json.get("ok"):
            print(f"✅ 消息发送成功 (Topic: {TOPIC_ID})")
        else:
            print(f"❌ 发送失败: HTTP {resp.status_code}, 响应: {resp_json}")
            # 如果是话题ID错误，提示可能的解决方案
            if "message thread not found" in str(resp_json):
                print(f"💡 提示: 话题 ID {TOPIC_ID} 无效，请确认话题是否存在")
    except Exception as e:
        print(f"❌ 发送报错: {e}")


def job():
    print(f"[{time.strftime('%H:%M:%S')}] 正在检查 Mlion 新闻...")
    news_data = get_latest_news()
    if news_data:
        print("发现新新闻，准备发送...")
        msg = format_message(news_data)
        send_telegram_message(msg)
    else:
        print("暂无新内容或 API 异常")


# --- 主程序 ---
if __name__ == "__main__":
    print("Mlion 监控机器人已启动...")

    # 立即执行一次
    job()

    # 每 60 秒检查一次
    schedule.every(60).seconds.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

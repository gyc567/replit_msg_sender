import os
import time
import requests
import schedule
from datetime import datetime, timedelta

# ======================= ⚙️ 配置区域 =======================

# Telegram 配置
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TOPIC_ID = int(os.environ.get('ARKHAM_TOPIC_ID', '1'))  # 话题 ID

# Arkham 配置
ARKHAM_API_KEY = os.environ.get('ARKHAM_API_KEY')
ARKHAM_BASE_URL = os.environ.get('ARKHAM_BASE_URL', 'https://api.arkhamintelligence.com')

# 监控阈值 (美元)
MIN_VALUE_USD = int(os.environ.get('ARKHAM_MIN_VALUE_USD', '1000000'))  # 只推送大于 100万美金 的交易

# 监控目标 (Arkham Entity ID 或 Label)
TARGET_ENTITIES = os.environ.get('ARKHAM_ENTITIES', 'binance,blackrock,jump-trading,falconx,us-government,vitalik-buterin').split(',')

# ======================= 验证配置 =======================
def check_config():
    missing = []
    if not BOT_TOKEN:
        missing.append('TELEGRAM_BOT_TOKEN')
    if not TG_CHAT_ID:
        missing.append('TELEGRAM_CHAT_ID')
    if not ARKHAM_API_KEY:
        missing.append('ARKHAM_API_KEY')
    if missing:
        raise EnvironmentError(f"缺少必要配置: {', '.join(missing)}")

check_config()
# ========================================================

# ======================= 🚀 核心代码 =======================

# 用于记录已处理的交易哈希，防止重复推送
processed_txs = set()

# 伪装成 Chrome 浏览器的请求头
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def log(msg):
    """打印带时间戳的日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send_tg(text):
    """发送 Telegram 消息 (包含自动修复话题ID错误的逻辑)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    # 如果配置了话题ID，尝试加入参数
    if TOPIC_ID:
        payload["message_thread_id"] = TOPIC_ID

    try:
        # 第一次尝试发送
        resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=10)
        result = resp.json()

        # === 关键修复：自动处理话题 ID 错误 ===
        if not result.get("ok") and "message thread not found" in result.get("description", ""):
            log(f"⚠️ 话题 ID ({TOPIC_ID}) 无效或不存在，正在尝试发送到主群组...")

            # 移除错误的 ID，重新发送
            payload.pop("message_thread_id", None)
            resp = requests.post(url, json=payload, headers=COMMON_HEADERS, timeout=10)
            result = resp.json()

        # 检查最终结果
        if result.get("ok"):
            log("✅ TG 消息发送成功")
        else:
            log(f"⚠️ TG 发送失败: {resp.status_code} - {resp.text}")

    except Exception as e:
        log(f"⚠️ TG 网络错误 (可能是Replit IP被封): {e}")

def get_arkham_transfers(entity_id):
    """获取 Arkham 交易数据"""
    endpoint = "/transfers"
    url = ARKHAM_BASE_URL + endpoint

    # 只查询过去 10 分钟的数据
    now = datetime.now()
    time_window = now - timedelta(minutes=10)

    params = {
        "base": entity_id,
        "limit": 20,
        "time_gte": int(time_window.timestamp() * 1000),
        "value_gte": MIN_VALUE_USD,
        "sort": "time",
        "order": "desc"
    }

    headers = COMMON_HEADERS.copy()
    headers["API-Key"] = ARKHAM_API_KEY
    headers["Content-Type"] = "application/json"

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "transfers" in data:
                return data["transfers"]
            elif isinstance(data, list):
                return data
            return []

        elif response.status_code == 401:
            log(f"❌ Arkham API Key 无效或过期")
        elif response.status_code == 403:
            log(f"❌ Arkham 拒绝访问 (403) - 可能是 IP 问题")
        else:
            log(f"⚠️ Arkham API 报错 [{entity_id}]: {response.status_code}")

        return []

    except Exception as e:
        log(f"Arkham 请求异常: {e}")
        return []

def analyze_and_alert(entity, txs):
    """分析交易并推送"""
    if not txs: return

    count = 0
    # 倒序处理
    for tx in reversed(txs):
        tx_hash = tx.get('transactionHash')

        if tx_hash in processed_txs:
            continue

        processed_txs.add(tx_hash)

        if len(processed_txs) > 5000:
            processed_txs.clear()

        count += 1

        token_symbol = tx.get('tokenSymbol', 'Unknown')
        token_amount = float(tx.get('unitValue', 0))
        usd_value = float(tx.get('historicalUSD', 0))
        block_time = tx.get('blockTimestamp', 'Unknown Time')

        sender_info = tx.get('fromAddress') or {}
        receiver_info = tx.get('toAddress') or {}

        def get_label(info):
            if not info: return "Unknown"
            if isinstance(info.get('arkhamLabel'), dict):
                return info['arkhamLabel'].get('name', info.get('address'))
            return info.get('address', 'Unknown')[:8] + "..."

        msg = (
            f"🚨 <b>Arkham 大额异动监控</b>\n\n"
            f"🏢 <b>监控对象:</b> #{entity}\n"
            f"💰 <b>价值:</b> ${usd_value:,.0f}\n"
            f"🪙 <b>代币:</b> {token_amount:,.2f} {token_symbol}\n"
            f"📤 <b>发送方:</b> {get_label(sender_info)}\n"
            f"📥 <b>接收方:</b> {get_label(receiver_info)}\n"
            f"⏰ <b>时间:</b> {block_time}\n"
            f"🔗 <a href='https://platform.arkhamintelligence.com/explorer/tx/{tx_hash}'>查看 Arkham 详情</a>"
        )

        send_tg(msg)
        time.sleep(2) 

    if count > 0:
        log(f"✅ [{entity}] 推送了 {count} 条新交易")

def job():
    """定时任务主体"""
    log("⏳ 开始新一轮扫描...")
    for entity in TARGET_ENTITIES:
        try:
            txs = get_arkham_transfers(entity)
            analyze_and_alert(entity, txs)
            time.sleep(1)
        except Exception as e:
            log(f"⚠️ 处理实体 {entity} 时出错: {e}")

if __name__ == "__main__":
    print("="*30)
    print("🤖 Arkham 监控机器人已启动 (自动修复版)")
    print("="*30)

    # 1. 启动时先测试一条消息
    log("📧 正在发送启动测试消息...")
    send_tg(f"🚀 <b>Arkham 监控机器人已启动</b>\n配置检测中...")

    # 2. 立即运行一次
    job()

    # 3. 设置定时任务 (每 2 分钟运行一次)
    schedule.every(2).minutes.do(job)

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            log(f"❌ 主循环发生错误: {e}")
            time.sleep(10)
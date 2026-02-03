import os
import asyncio
import aiohttp
import json
import logging
import datetime
import time
import sys
from collections import deque, defaultdict

# ================= 配置区域 =================

# Telegram 配置
TG_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TG_THREAD_ID = int(os.environ.get('BINANCE_TOPIC_ID', '3'))

# 监控币种列表 (小写)
SYMBOLS = [s.strip().lower() for s in os.environ.get('BINANCE_SYMBOLS', 'btcusdt,ethusdt').split(',')]

# 1. 实时成交监控阈值 (单笔数量)
THRESHOLD_SINGLE_QTY = {
    'BTCUSDT': float(os.environ.get('BINANCE_BTC_THRESHOLD', '1.0')),
    'ETHUSDT': float(os.environ.get('BINANCE_ETH_THRESHOLD', '50.0'))
}

# 2. 1分钟突发监控设置
BURST_AMOUNT_USD = float(os.environ.get('BINANCE_BURST_AMOUNT_USD', '100000'))
BURST_COUNT_TRIGGER = int(os.environ.get('BINANCE_BURST_COUNT_TRIGGER', '1'))
BURST_WINDOW_MS = 60 * 100

# 3. 场内异动 - 交易量异常设置
VOLUME_ANOMALY_MULTIPLIER = float(os.environ.get('BINANCE_VOLUME_ANOMALY_MULTIPLIER', '3.0'))

# 4. 场内异动 - 巨额挂单设置 (订单簿)
ORDER_BOOK_WALL_THRESHOLD = float(os.environ.get('BINANCE_ORDER_BOOK_WALL_THRESHOLD', '5000000'))
WALL_ALERT_COOLDOWN = 300

MARKET_TYPE = os.environ.get('BINANCE_MARKET_TYPE', '现货')

# ======================= 验证配置 =======================
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    raise EnvironmentError("缺少必要配置: TELEGRAM_BOT_TOKEN")
if not os.environ.get('TELEGRAM_CHAT_ID'):
    raise EnvironmentError("缺少必要配置: TELEGRAM_CHAT_ID")
# ========================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# 全局状态存储
burst_monitor = defaultdict(lambda: {'BUY': deque(), 'SELL': deque()})
volume_baseline = {} 
wall_alert_history = {} 

async def send_telegram_message(session, text):
    """发送消息到 Telegram (包含自动修复话题ID错误的逻辑)"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    payload = {
        'chat_id': TG_CHAT_ID, 
        'text': text, 
        'parse_mode': 'HTML'
    }

    # 只有当 ID 有效时才添加该参数
    if TG_THREAD_ID is not None:
        payload['message_thread_id'] = TG_THREAD_ID

    try:
        async with session.post(url, json=payload) as response:
            # 获取响应内容
            resp_json = await response.json()

            # === 关键修复：自动处理话题 ID 错误 ===
            if not resp_json.get("ok") and "message thread not found" in resp_json.get("description", ""):
                logging.warning(f"⚠️ 话题 ID ({TG_THREAD_ID}) 无效，正在尝试发送到主群组...")

                # 移除错误的 ID，重新发送
                payload.pop("message_thread_id", None)
                async with session.post(url, json=payload) as retry_resp:
                    retry_json = await retry_resp.json()
                    if not retry_json.get("ok"):
                        logging.error(f"TG 重试发送失败: {retry_json}")

            elif not resp_json.get("ok"):
                logging.error(f"TG 发送失败 (Code {response.status}): {resp_json}")

    except Exception as e:
        logging.error(f"TG 请求错误: {e}")

def format_amount(amount):
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"{amount / 1_000:.2f}K"
    else:
        return f"{amount:.2f}"

def get_time_str(ts_ms=None):
    if ts_ms:
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000)
    else:
        dt = datetime.datetime.now()
    return dt.strftime('%H:%M:%S')

async def init_volume_baseline(session):
    """初始化历史成交量基准"""
    logging.info("正在初始化历史成交量基准...")
    base_url = "https://api.binance.com/api/v3/klines"

    for symbol in SYMBOLS:
        symbol_upper = symbol.upper()
        try:
            params = {'symbol': symbol_upper, 'interval': '5m', 'limit': 288}
            async with session.get(base_url, params=params) as resp:
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    total_vol = sum(float(k[5]) for k in data)
                    avg_vol = total_vol / len(data)
                    volume_baseline[symbol_upper] = avg_vol
                    logging.info(f"[{symbol_upper}] 24h平均5min成交量: {avg_vol:.2f}")
                else:
                    volume_baseline[symbol_upper] = 99999999
        except Exception as e:
            logging.error(f"初始化成交量失败: {e}")
            volume_baseline[symbol_upper] = 99999999

async def process_kline_logic(session, data, symbol_upper):
    """处理 K线数据"""
    k = data['k']
    if not k['x']: 
        return

    current_vol = float(k['v'])
    close_price = float(k['c'])

    avg_vol = volume_baseline.get(symbol_upper, 0)

    if avg_vol > 0 and current_vol > (avg_vol * VOLUME_ANOMALY_MULTIPLIER):
        multiple = current_vol / avg_vol
        amount_usd = current_vol * close_price

        msg = (
            f"📈 <b>成交量异常飙升</b>\n"
            f"币对: {symbol_upper}\n"
            f"时间: {get_time_str(data['E'])}\n"
            f"当前量: {format_amount(current_vol)} (均量 {format_amount(avg_vol)})\n"
            f"倍数: <b>{multiple:.1f}倍</b> 🔥\n"
            f"成交额: {format_amount(amount_usd)}\n"
        )
        logging.info(f"触发成交量异常: {symbol_upper} {multiple:.1f}倍")
        await send_telegram_message(session, msg)

async def process_depth_logic(session, data, symbol_upper):
    """处理深度数据 (检测大额挂单)"""
    bids = data.get('bids') or data.get('b', [])
    asks = data.get('asks') or data.get('a', [])

    current_time = time.time()

    for price_str, qty_str in bids:
        await check_wall(session, symbol_upper, "买入挂单", float(price_str), float(qty_str), current_time)

    for price_str, qty_str in asks:
        await check_wall(session, symbol_upper, "卖出挂单", float(price_str), float(qty_str), current_time)

async def check_wall(session, symbol, direction_str, price, qty, current_time):
    amount_usd = price * qty
    if amount_usd >= ORDER_BOOK_WALL_THRESHOLD:
        alert_key = f"{symbol}_{direction_str}_{int(price)}"
        last_alert_time = wall_alert_history.get(alert_key, 0)

        if current_time - last_alert_time < WALL_ALERT_COOLDOWN:
            return

        wall_alert_history[alert_key] = current_time
        emoji = "🧱" if "买" in direction_str else "🧗"

        msg = (
            f"{emoji} <b>发现巨额挂单 (Order Wall)</b>\n"
            f"币对: {symbol}\n"
            f"方向: <b>{direction_str}</b>\n"
            f"价格: {price}\n"
            f"金额: <b>{format_amount(amount_usd)}</b>\n"
        )
        logging.info(f"触发挂单报警: {symbol} {direction_str} {format_amount(amount_usd)}")
        await send_telegram_message(session, msg)

async def process_trade_logic(session, data, symbol_upper):
    """处理实时成交"""
    price = float(data['p'])
    quantity = float(data['q'])
    trade_time = data['T']
    is_buyer_maker = data['m']
    amount_usd = price * quantity
    direction_str = "🔴 主动卖出" if is_buyer_maker else "🟢 主动买入"

    # 逻辑 A: 单笔巨量
    threshold = THRESHOLD_SINGLE_QTY.get(symbol_upper)
    if threshold and quantity >= threshold:
        msg_text = (
            f"⚡ <b>大额成交监控</b>\n"
            f"币对: {symbol_upper}\n"
            f"方向: <b>{direction_str}</b>\n"
            f"数量: {quantity:.3f}\n"
            f"价格: {price}\n"
            f"金额: <b>{format_amount(amount_usd)}</b>\n"
            f"时间: {get_time_str(trade_time)}"
        )
        logging.info(f"触发单笔报警: {symbol_upper} {format_amount(amount_usd)}")
        await send_telegram_message(session, msg_text)

    # 逻辑 B: 1分钟突发
    if amount_usd >= BURST_AMOUNT_USD:
        dir_key = "SELL" if is_buyer_maker else "BUY"
        queue = burst_monitor[symbol_upper][dir_key]
        queue.append({'t': trade_time, 'v': amount_usd})

        while queue and (trade_time - queue[0]['t'] > BURST_WINDOW_MS):
            queue.popleft()

        if len(queue) > BURST_COUNT_TRIGGER:
            total_volume = sum(item['v'] for item in queue)
            msg = (
                f"🚨 <b>密集大单报警 (1分钟内)</b>\n"
                f"币对: {symbol_upper}\n"
                f"方向: <b>{direction_str}</b>\n"
                f"频次: {len(queue)}笔\n"
                f"总金额: <b>{format_amount(total_volume)}</b>\n"
                f"当前价: {price}"
            )
            logging.info(f"触发突发报警: {symbol_upper}")
            await send_telegram_message(session, msg)
            queue.clear()

async def connect_binance():
    streams = []
    for s in SYMBOLS:
        streams.append(f"{s}@aggTrade")
        streams.append(f"{s}@kline_5m")
        streams.append(f"{s}@depth20@100ms")

    stream_str = '/'.join(streams)
    ws_url = f"wss://stream.binance.com:9443/stream?streams={stream_str}"

    async with aiohttp.ClientSession() as session:
        await init_volume_baseline(session)
        await send_telegram_message(session, f"🤖 <b>币安监控机器人已启动</b>\n监控项: 实时大单 / 密集交易 / 3倍放量 / 挂单墙")

        while True:
            try:
                async with session.ws_connect(ws_url) as ws:
                    logging.info(f"✅ WebSocket 连接成功，监听 {len(SYMBOLS)} 个币种...")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            raw_data = json.loads(msg.data)

                            if 'data' in raw_data:
                                payload = raw_data['data']
                                stream_name = raw_data['stream']

                                # 从 stream 名称中提取 symbol
                                symbol_part = stream_name.split('@')[0]
                                symbol_upper = symbol_part.upper()

                                if 'aggTrade' in stream_name:
                                    await process_trade_logic(session, payload, symbol_upper)
                                elif 'kline' in stream_name:
                                    await process_kline_logic(session, payload, symbol_upper)
                                elif 'depth' in stream_name:
                                    await process_depth_logic(session, payload, symbol_upper)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
            except Exception as e:
                logging.error(f"⚠️ 连接断开，5秒后重连: {e}")
                await asyncio.sleep(5)

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(connect_binance())
    except KeyboardInterrupt:
        print("程序已停止")
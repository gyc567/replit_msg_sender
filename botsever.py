import os
import requests
from flask import Flask, request, jsonify
import json
import socket
import sys
import threading

app = Flask(__name__)

# ==========================================
# 1. 必填配置
# ==========================================

# 你的机器人 Token
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 你的群组 ID
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 话题 ID
TOPIC_ID = int(os.environ.get('BOTSEVER_TOPIC_ID', '13'))

# Webhook 监听路径
ROUTE_PATH = os.environ.get('WEBHOOK_ROUTE_PATH', '/twitter-webhook')

# 初始端口号
START_PORT = int(os.environ.get('WEBHOOK_START_PORT', '5006'))

# ======================= 验证配置 =======================
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    raise EnvironmentError("缺少必要配置: TELEGRAM_BOT_TOKEN")
if not os.environ.get('TELEGRAM_CHAT_ID'):
    raise EnvironmentError("缺少必要配置: TELEGRAM_CHAT_ID")
# ========================================================

# ==========================================
# 2. 端口检查与获取函数 (纯 Python 实现)
# ==========================================

def get_available_port(start_port):
    """
    从 start_port 开始寻找可用的端口
    """
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # 尝试绑定端口，如果成功说明端口空闲
            if s.connect_ex(('localhost', port)) != 0:
                return port
            else:
                print(f"⚠️ 端口 {port} 被占用，尝试下一个...")
                port += 1
    return None

# ==========================================
# 3. Telegram 发送函数
# ==========================================

def send_to_telegram(message):
    if not BOT_TOKEN:
        print("[错误] BOT_TOKEN 未设置")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    if TOPIC_ID:
        payload["message_thread_id"] = TOPIC_ID

    try:
        response = requests.post(url, json=payload)
        resp_data = response.json()

        if response.status_code == 200 and resp_data.get("ok"):
            print("[成功] 消息已推送到 Telegram")
            return True
        else:
            print(f"[失败] Telegram API 报错: {resp_data}")
            return False
    except Exception as e:
        print(f"[异常] 发送 Telegram 失败: {e}")
        return False

# ==========================================
# 4. Webhook 接收服务
# ==========================================

@app.route(ROUTE_PATH, methods=['POST'])
def handle_twitter_webhook():
    print(f"\n[系统] 收到 Webhook 请求: {ROUTE_PATH}")

    # 1. 获取数据
    data = request.json
    if not data:
        data = request.form.to_dict()

    # 🚨 握手/测试请求处理
    if not data:
        print(">>> [握手/测试] 收到空数据，返回 200 以通过验证")
        return jsonify({"status": "success", "msg": "Handshake received"}), 200

    print(">>> 收到原始数据:", json.dumps(data, ensure_ascii=False))

    # 2. 解析推文内容
    try:
        tweet_text = data.get('text', data.get('content', data.get('full_text', '无正文内容')))
        tweet_link = data.get('link', data.get('url', data.get('tweet_url', '')))
        tweet_user = data.get('user', data.get('author', data.get('screen_name', '未知用户')))

        if tweet_text == '无正文内容' and tweet_link == '':
            print(">>> [忽略] 数据有效但不包含内容，跳过发送")
            return jsonify({"status": "ignored"}), 200

        # 3. 拼接消息
        tg_message = (
            f"🚨 <b>新推文提醒</b>\n\n"
            f"👤 <b>用户:</b> {tweet_user}\n"
            f"📝 <b>内容:</b> {tweet_text}\n\n"
            f"🔗 <a href='{tweet_link}'>点击查看推文</a>"
        )

        # 4. 发送
        send_to_telegram(tg_message)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"[出错] 处理数据异常: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 200

# ==========================================
# 5. 启动入口
# ==========================================

def run_server():
    """在后台线程中运行 Flask 服务器"""
    print("-" * 40)
    print("🔄 正在初始化 Webhook 服务器...")

    # 自动寻找可用端口
    final_port = get_available_port(START_PORT)

    if final_port is None:
        print("❌ 无法找到可用端口，请检查系统环境。")
        return None

    print(f"✅ 成功锁定端口: {final_port}")
    print("-" * 40)
    print(f"🚀 Webhook 服务正在启动...")
    print(f"👉 请注意：如果端口变了，记得更新 Ngrok 命令：")
    print(f"   ngrok http {final_port}")
    print("-" * 40)

    # 在线程中启动 Flask，这样不会阻塞主程序
    def flask_thread():
        app.run(host='0.0.0.0', port=final_port, debug=False, threaded=True)
    
    server_thread = threading.Thread(target=flask_thread, daemon=True)
    server_thread.start()
    return final_port

if __name__ == '__main__':
    # 直接运行时，也使用线程方式启动，保持一致性
    run_server()
    # 防止主线程立即退出
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Webhook 服务器已停止")
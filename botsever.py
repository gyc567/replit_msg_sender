import os
import requests
from flask import Flask, request, jsonify
import json
import socket
import sys
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

app = Flask(__name__)

# ==========================================
# 0. 监控日志系统
# ==========================================


class MonitorLogger:
    """监控日志记录器 - 追踪接口联通性和功能性"""

    def __init__(self):
        self.start_time = datetime.now()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time: Optional[datetime] = None
        self.last_error_time: Optional[datetime] = None
        self.last_error_msg: Optional[str] = None
        self.telegram_success_count = 0
        self.telegram_error_count = 0
        self.webhook_received_count = 0
        self.webhook_ignored_count = 0

        # 接口健康状态 (True=健康, False=不健康)
        self.interface_status = {
            "telegram_api": None,  # 未知
            "webhook_endpoint": True,
            "flask_server": True,
        }

    def log_request(
        self, endpoint: str, success: bool, error_msg: Optional[str] = None
    ):
        """记录请求日志"""
        self.request_count += 1
        self.last_request_time = datetime.now()

        if success:
            self.success_count += 1
            self.interface_status["webhook_endpoint"] = True
        else:
            self.error_count += 1
            self.last_error_time = datetime.now()
            self.last_error_msg = error_msg
            self.interface_status["webhook_endpoint"] = False

    def log_telegram_result(self, success: bool, error_msg: Optional[str] = None):
        """记录 Telegram 发送结果"""
        if success:
            self.telegram_success_count += 1
            self.interface_status["telegram_api"] = True
        else:
            self.telegram_error_count += 1
            self.last_error_time = datetime.now()
            self.last_error_msg = error_msg
            self.interface_status["telegram_api"] = False

    def log_webhook_received(self, ignored: bool = False):
        """记录 Webhook 接收"""
        if ignored:
            self.webhook_ignored_count += 1
        else:
            self.webhook_received_count += 1

    def get_uptime(self) -> str:
        """获取运行时间"""
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

    def get_status_report(self) -> dict:
        """获取状态报告"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            "status": "healthy" if self.error_count == 0 else "degraded",
            "uptime": self.get_uptime(),
            "uptime_seconds": uptime_seconds,
            "metrics": {
                "total_requests": self.request_count,
                "successful_requests": self.success_count,
                "failed_requests": self.error_count,
                "success_rate": f"{(self.success_count / self.request_count * 100) if self.request_count > 0 else 0:.1f}%",
                "telegram_success": self.telegram_success_count,
                "telegram_errors": self.telegram_error_count,
                "webhook_received": self.webhook_received_count,
                "webhook_ignored": self.webhook_ignored_count,
            },
            "interface_status": self.interface_status,
            "last_request": self.last_request_time.isoformat()
            if self.last_request_time
            else None,
            "last_error": {
                "time": self.last_error_time.isoformat()
                if self.last_error_time
                else None,
                "message": self.last_error_msg,
            }
            if self.last_error_time
            else None,
            "start_time": self.start_time.isoformat(),
        }

    def log_health_check(self):
        """执行健康检查并记录"""
        # 检查 Telegram API
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                self.interface_status["telegram_api"] = True
            else:
                self.interface_status["telegram_api"] = False
        except Exception as e:
            self.interface_status["telegram_api"] = False

    def print_status(self):
        """打印当前状态"""
        report = self.get_status_report()
        print("\n" + "=" * 60)
        print("📊 监控状态报告")
        print("=" * 60)
        print(f"🟢 运行时间: {report['uptime']}")
        print(f"📈 总请求数: {report['metrics']['total_requests']}")
        print(f"✅ 成功率: {report['metrics']['success_rate']}")
        print(
            f"📤 Telegram 发送: {report['metrics']['telegram_success']} 成功, {report['metrics']['telegram_errors']} 失败"
        )
        print(
            f"🔗 Webhook 接收: {report['metrics']['webhook_received']} 条, {report['metrics']['webhook_ignored']} 条忽略"
        )
        print(f"🟡 接口状态:")
        for interface, status in report["interface_status"].items():
            status_icon = "✅" if status else "❌" if status is False else "⚪"
            print(f"   {status_icon} {interface}: {status}")
        print("=" * 60)


# 初始化监控日志器
monitor = MonitorLogger()

# ==========================================
# 1. 必填配置
# ==========================================

# 你的机器人 Token
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# 你的群组 ID
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 话题 ID
TOPIC_ID = int(os.environ.get("BOTSEVER_TOPIC_ID", "13"))

# Webhook 监听路径
ROUTE_PATH = os.environ.get("WEBHOOK_ROUTE_PATH", "/twitter-webhook")

# 初始端口号 (Replit部署强制使用5000端口)
START_PORT = 5000

# ======================= 验证配置 =======================
if not os.environ.get("TELEGRAM_BOT_TOKEN"):
    raise EnvironmentError("缺少必要配置: TELEGRAM_BOT_TOKEN")
if not os.environ.get("TELEGRAM_CHAT_ID"):
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
            if s.connect_ex(("localhost", port)) != 0:
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
        monitor.log_telegram_result(False, "BOT_TOKEN 未设置")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    if TOPIC_ID:
        payload["message_thread_id"] = TOPIC_ID

    try:
        response = requests.post(url, json=payload)
        resp_data = response.json()

        if response.status_code == 200 and resp_data.get("ok"):
            print("[成功] 消息已推送到 Telegram")
            monitor.log_telegram_result(True)
            return True
        else:
            error_msg = str(resp_data)
            print(f"[失败] Telegram API 报错: {resp_data}")
            monitor.log_telegram_result(False, error_msg)
            return False
    except Exception as e:
        error_msg = str(e)
        print(f"[异常] 发送 Telegram 失败: {e}")
        monitor.log_telegram_result(False, error_msg)
        return False


# ==========================================
# 4. Webhook 接收服务 + 监控端点
# ==========================================


@app.route("/health", methods=["GET"])
def health_check():
    """健康检查端点 - 返回服务状态"""
    monitor.log_health_check()
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "botsever",
            "port": START_PORT,
        }
    )


@app.route("/status", methods=["GET"])
def status_check():
    """状态检查端点 - 返回详细监控数据"""
    return jsonify(monitor.get_status_report())


@app.route("/status/print", methods=["GET"])
def status_print():
    """打印状态端点 - 控制台输出状态"""
    monitor.print_status()
    return jsonify({"status": "printed", "message": "状态已打印到控制台"})


@app.route("/metrics", methods=["GET"])
def metrics_check():
    """指标端点 - 返回 Prometheus 格式指标"""
    report = monitor.get_status_report()
    metrics = [
        f"# HELP botsever_uptime_seconds 服务运行时间（秒）",
        f"# TYPE botsever_uptime_seconds gauge",
        f"botsever_uptime_seconds {report['uptime_seconds']}",
        f"# HELP botsever_requests_total 总请求数",
        f"# TYPE botsever_requests_total counter",
        f"botsever_requests_total {report['metrics']['total_requests']}",
        f"# HELP botsever_requests_success_total 成功请求数",
        f"# TYPE botsever_requests_success_total counter",
        f"botsever_requests_success_total {report['metrics']['successful_requests']}",
        f"# HELP botsever_requests_failed_total 失败请求数",
        f"# TYPE botsever_requests_failed_total counter",
        f"botsever_requests_failed_total {report['metrics']['failed_requests']}",
        f"# HELP botsever_telegram_success_total Telegram发送成功次数",
        f"# TYPE botsever_telegram_success_total counter",
        f"botsever_telegram_success_total {report['metrics']['telegram_success']}",
        f"# HELP botsever_telegram_error_total Telegram发送失败次数",
        f"# TYPE botsever_telegram_error_total counter",
        f"botsever_telegram_error_total {report['metrics']['telegram_errors']}",
        f"# HELP botsever_webhook_received_total Webhook接收次数",
        f"# TYPE botsever_webhook_received_total counter",
        f"botsever_webhook_received_total {report['metrics']['webhook_received']}",
    ]
    return "\n".join(metrics), 200, {"Content-Type": "text/plain"}


@app.route(ROUTE_PATH, methods=["POST"])
def handle_twitter_webhook():
    """处理 Twitter Webhook 请求"""
    print(f"\n[系统] 收到 Webhook 请求: {ROUTE_PATH}")
    monitor.log_request(ROUTE_PATH, True)

    # 1. 获取数据
    data = request.json
    if not data:
        data = request.form.to_dict()

    # 🚨 握手/测试请求处理
    if not data:
        print(">>> [握手/测试] 收到空数据，返回 200 以通过验证")
        monitor.log_webhook_received(ignored=True)
        return jsonify({"status": "success", "msg": "Handshake received"}), 200

    print(">>> 收到原始数据:", json.dumps(data, ensure_ascii=False))
    monitor.log_webhook_received(ignored=False)

    # 2. 解析推文内容
    try:
        tweet_text = data.get(
            "text", data.get("content", data.get("full_text", "无正文内容"))
        )
        tweet_link = data.get("link", data.get("url", data.get("tweet_url", "")))
        tweet_user = data.get(
            "user", data.get("author", data.get("screen_name", "未知用户"))
        )

        if tweet_text == "无正文内容" and tweet_link == "":
            print(">>> [忽略] 数据有效但不包含内容，跳过发送")
            monitor.log_webhook_received(ignored=True)
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
        monitor.log_request(ROUTE_PATH, False, str(e))
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
        app.run(host="0.0.0.0", port=final_port, debug=False, threaded=True)

    server_thread = threading.Thread(target=flask_thread, daemon=True)
    server_thread.start()
    return final_port


if __name__ == "__main__":
    # 直接运行时，也使用线程方式启动，保持一致性
    run_server()
    # 防止主线程立即退出
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Webhook 服务器已停止")

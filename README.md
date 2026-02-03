# Replit 加密货币监控机器人

## 项目概述

加密货币实时监控和 Telegram 告警系统，支持:
- 🏦 **Arkham Intelligence** - 大额转账监控
- 📈 **Binance** - 市场异动监控 (WebSocket)
- 📰 **Mlion News** - 快讯监控
- 🐦 **Twitter Webhook** - 推文通知

## 快速部署

### 步骤 1: 创建 Replit 项目

1. 登录 [Replit](https://replit.com)
2. 点击 "Create" → "Import from GitHub"
3. 导入此仓库 或 创建新的 Replit

### 步骤 2: 配置 Secrets (敏感信息)

> ⚠️ **重要**: 不要将 `.env` 文件提交到公开仓库!

在 Replit 面板中:

1. 点击 **Tools** → **Secrets**
2. 添加以下配置项 (key = value):

```bash
# Telegram 配置
TELEGRAM_BOT_TOKEN=你的BotToken
TELEGRAM_CHAT_ID=你的群组ID

# Arkham 配置
ARKHAM_API_KEY=你的ArkhamKey
ARKHAM_BASE_URL=https://api.arkhamintelligence.com
ARKHAM_MIN_VALUE_USD=1000000
ARKHAM_ENTITIES=binance,blackrock,jump-trading,falconx,us-government,vitalik-buterin

# Binance 配置
BINANCE_SYMBOLS=btcusdt,ethusdt
BINANCE_BTC_THRESHOLD=1.0
BINANCE_ETH_THRESHOLD=50.0
BINANCE_BURST_AMOUNT_USD=100000
BINANCE_BURST_COUNT_TRIGGER=1
BINANCE_VOLUME_ANOMALY_MULTIPLIER=3.0
BINANCE_ORDER_BOOK_WALL_THRESHOLD=5000000

# Mlion 配置
MLION_API_KEY=你的MlionKey
MLION_API_URL=https://api.mlion.ai/v2/api/news/real/time?language=cn&time_zone=Asia%2FShanghai&num=100&page=1&client=mlion&is_hot=Y

# Webhook 服务器
WEBHOOK_ROUTE_PATH=/twitter-webhook
WEBHOOK_START_PORT=5006
```

### 步骤 3: 运行项目

1. 点击 Replit 顶部的 **Run** 按钮
2. 或在 Shell 中执行:
```bash
python main.py
```

### 步骤 4: 配置 Twitter Webhook (可选)

1. 安装 ngrok:
```bash
brew install ngrok  # macOS
# 或从 https://ngrok.com/download 下载
```

2. 启动隧道:
```bash
ngrok http 5006
```

3. 复制 ngrok 提供的 URL (如 `https://xxx.ngrok.io`)
4. 在 Twitter Developer Portal 配置 Webhook URL:
   ```
   https://xxx.ngrok.io/twitter-webhook
   ```

## 监控功能

| 监控项 | 频率 | 说明 |
|--------|------|------|
| Arkham | 每 2 分钟 | >$1M 转账 |
| Binance | 实时 | 大额交易/放量/挂单墙 |
| Mlion | 每 60 秒 | 快讯 |
| Twitter | 实时 | Webhook |

## 目录结构

```
├── main.py           # 主程序 (进程守护)
├── arkm.py           # Arkham 监控
├── bianjk.py         # Binance 监控 (WebSocket)
├── zixun.py          # Mlion 新闻
├── botsever.py       # Twitter Webhook 服务器
├── .env              # 本地配置 (敏感)
├── .env.example      # 配置模板
├── .replit           # Replit 配置
├── replit.nix        # Nix 环境
├── pyproject.toml    # Python 依赖
└── tests/            # 单元测试
```

## 本地开发

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate   # Windows

# 安装依赖
pip install -e .

# 运行测试
pytest tests/ -v

# 运行主程序
python main.py
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单个模块测试
pytest tests/test_zixun.py -v
```

## 故障排除

### Q: 进程启动失败?
A: 检查 Secrets 是否正确配置，特别是 `TELEGRAM_BOT_TOKEN`

### Q: Twitter Webhook 不工作?
A: 确认 ngrok 隧道已启动，且 URL 正确配置到 Twitter

### Q: API 返回 401/4001?
A: API Key 可能过期，需要更新 Secrets 中的 key

## 许可证

MIT

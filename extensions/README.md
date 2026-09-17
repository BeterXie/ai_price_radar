# PriceMemo 机器人扩展模块 (Extensions)

本目录开源了 **PriceMemo (AI 比价雷达)** 的核心机器人集成与推送扩展组件，包含：
1. **Telegram 管理员机器人 (`telegram_bot.py`)**：用于向站点所有者/管理员推送调价快报、系统健康报警以及响应管理指令。
2. **QQ 机器人套件 (`qq_bot.py`, `qq_connector.py`, `qq_gateway.py`)**：
   - 支持腾讯官方开放平台 QQ 机器人标准 Open API (C2C 与群聊)。
   - 原生支持基于 AES-256-GCM 与手机 QQ「扫一扫」快速绑定的零门槛腾讯官方 Connector 协议 (`qq_connector.py`)。
   - 提供基于 Python 原生 WebSocket (`websockets`) 的持久长连接 Gateway 网关服务 (`qq_gateway.py`)，无需本地额外部署重型 Node.js 进程。
   - 兼容可选的本地 Node.js SDK Bridge (`extensions/qqbot_bridge/`)。
3. **自然语言比价指令解析引擎 (`chat_commands.py`)**：
   - 响应群聊/私聊自然语言比价查询（如 `chatgpt plus`, `claude 20x`, `cursor`, `智谱清言` 等）。
   - 自动聚合最低价、各店铺现货分布、质保周期与交付形态，输出排版优雅的回复。
4. **个性化变动调度中心 (`dispatcher.py`)**：
   - 当快照比价流水发现降价/涨价时，智能匹配 `user_product_subscriptions`。
   - 通过邮件 (Email) 与绑定的机器人 (QQ / Telegram) 发送毫秒级个性化到价提醒与降价战报。
5. **消息渲染格式化工具 (`formatter.py`)**：
   - 支持 Telegram HTML 富文本格式与 QQ 纯文本/Markdown 格式自适应排版。

---

## 目录结构

```
extensions/
├── README.md               # 模块说明与配置指南
├── __init__.py
├── bots/
│   ├── __init__.py
│   ├── telegram_bot.py     # Telegram Bot 客户端与管理员推送
│   ├── qq_bot.py           # 腾讯 QQ 机器人客户端 (Open API + 桥接)
│   ├── qq_connector.py     # 腾讯 QQ Connector 免配置扫码绑定协议
│   ├── qq_gateway.py       # QQ 机器人原生 WebSocket 长连接网关
│   ├── clawbot_client.py   # 腾讯 iLink 协议客户端
│   ├── chat_commands.py    # 智能比价与查询指令解析引擎
│   ├── dispatcher.py       # 价格变动与订阅事件调度器
│   └── formatter.py        # 消息模版与格式化渲染器
└── qqbot_bridge/           # 可选的 Node.js 兼容桥接层
    ├── package.json
    ├── qq_bot_bridge.mjs
    └── qq_bot_login.mjs
```

---

## 环境变量配置

在根目录或 `apps/api` 的 `.env` 中配置以下环境变量即可启用对应机器人的功能：

### 1. Telegram Bot (管理员报警与通知)
```bash
# Telegram Bot Token (从 @BotFather 获取)
TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
# 接收通知的管理员 Chat ID (从 @userinfobot 获取)
TELEGRAM_ADMIN_CHAT_ID="987654321"
# 可选：代理地址（国内服务器访问 Telegram API 时需配置）
TELEGRAM_PROXY="http://127.0.0.1:7890"
# 可选：自定义 API 网关反代地址（默认 https://api.telegram.org）
TELEGRAM_API_BASE_URL="https://api.telegram.org"
```

### 2. 腾讯 QQ 机器人 (QQ Bot)
PriceMemo 支持两种配置方式：

#### 模式 A：用户手机 QQ 扫码即用（推荐，无需自己申请官方机器人）
系统前台/后台内置「手机 QQ 扫码绑定」页面，利用 `qq_connector.py` 动态生成官方授权二维码，用户扫描后即时完成与官方机器人通讯的建立。

#### 模式 B：自建官方 QQ 机器人（开发者自有 AppID）
```bash
QQ_BOT_APP_ID="102xxxxxx"
QQ_BOT_APP_SECRET="xxxxxx"
```

#### 模式 C：使用本地 Node.js Bridge (可选)
```bash
QQ_BOT_BRIDGE_URL="http://127.0.0.1:18081"
QQ_BOT_BRIDGE_TOKEN="your-32-chars-secret-token"
```

---

## 常用指令与测试

### 比价与查询指令
机器人接收到消息后会自动路由至 `chat_commands.py` 进行模糊匹配：
- `plus` / `chatgpt plus`：查询当前各店铺 ChatGPT Plus 的最低价、现货与店铺排名。
- `claude` / `20x`：查询 Claude 系列型号及 Pro 20x 现货与价格区间。
- `cursor` / `cursor pro`：查询 Cursor Pro 及商业版当前报价。
- `智谱` / `清言` / `glm`：查询智谱清言会员及 GLM API 资源包报价。
- `/status`：查看比价雷达系统的实时监控统计（爬取快照、店铺数、在售商品数）。
- `/help`：获取当前机器人支持的指令菜单。

### 本地测试
```bash
# 在 apps/api 下执行测试套件
cd apps/api
python -m pytest tests/test_auth_and_bot.py tests/test_user_subscriptions.py -v
```

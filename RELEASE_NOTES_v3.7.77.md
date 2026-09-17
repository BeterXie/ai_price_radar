# Release Notes - v3.7.77

## Overview
v3.7.77 彻底修复了绑定 QQ 机器人后在 QQ 私聊窗口中发送消息提示“无法对话，提示服务异常”的通信层缺陷。

## Key Changes
1. **纯 Python 原生 QQ WebSocket Gateway 守护进程 (`extensions/bots/qq_gateway.py`)**:
   - 接入腾讯 QQ 开放平台 WebSocket 网关（`wss://api.sgroup.qq.com/websocket`）；
   - 维护动态心跳、IDENTIFY 与 RESUME 会话恢复，机器人全天候保持在线状态；
   - 接收 `C2C_MESSAGE_CREATE` 入向私聊事件，调用 `handle_chat_command` 解析用户指令（`plus`, `pro`, `gemini`, `行情`, `关注`, `帮助` 等）；
   - 附带 `msg_id` 调用 OpenAPI 快速完成被动回复，彻底消除“服务异常”错误。
2. **FastAPI Lifespan 自动托管**:
   - 在应用启动时自动启动 Gateway 监听任务，动态扫描当前有效绑定的 QQ 机器人账号；
   - 遵从全局 `bot_enabled` 开关，关闭时自动释放长连接。
3. **依赖规范化**:
   - 在 `apps/api/requirements.txt` 中显式固化 `websockets>=13.0`。

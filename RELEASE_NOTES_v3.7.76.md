# Release Notes - v3.7.76

## 变更摘要

1. **全面接入腾讯官方 QQ Bot Connector 扫码协议**:
   - 严格对齐 `Dota AI Decision Lab` 底层依赖（`@tencent-connect/qqbot-connector` 官方协议）；
   - 彻底修复因此前微信 ilinkai 协议导致的“手机 QQ 扫码提示请在微信打开”问题；
   - 采用腾讯官方 QQ 网关（`q.qq.com`）：通过 `https://q.qq.com/lite/create_bind_task` 创建扫码任务，生成原生手机 QQ 授权地址：`https://q.qq.com/qqbot/openclaw/connect.html?task_id=...&source=&_wv=2`；
   - 手机 QQ 扫描后直接调起 QQ 官方机器人授权绑定界面，点击确认即可绑定！
   - 轮询 `https://q.qq.com/lite/poll_bind_result`，采用 AES-256-GCM 算法解密官方凭据，自动提取 `app_id`、`app_secret` 与用户的 `user_openid` 完成账号绑定；
   - 绑定成功后立即通过 QQ 官方 OpenAPI 向用户下发欢迎消息与使用指南。

2. **跨项目资产同步与依赖增强**:
   - 将 `Dota AI Decision Lab` 中的完整 Node 桥接组件复制至私有 `extensions/qqbot_bridge/`，提供本地 Node 与纯 Python 双重运行兼容；
   - API 基础依赖新增 `cryptography>=43.0.0`，原生支持标准 AES-256-GCM 高效加解密。

# Release Notes v3.7.56

## 变更摘要

- **全站搜索引擎爬虫指令增强（Root Metadata Robots）**：
  - 在 pps/web/app/layout.tsx 的全局 Metadata 中显式增加 
obots 与 googleBot 指令，包括 index: true, ollow: true, max-image-preview: large, max-snippet: -1, max-video-preview: -1。
  - 确保 Googlebot 与其他搜索引擎抓取全站任意动态与静态页面时均能获得最高优先级的显式收录指引，避免因缺失全局 robots 声明而被爬虫算法延迟编入索引。

## 验证

- 后端 API 测试（包含版本报告与契约）全部通过。
- 前端 TypeScript 类型检查与全量单元测试（60 项）全部通过。

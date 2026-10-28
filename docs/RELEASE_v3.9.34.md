# v3.9.34

- 首页增加中转站目录前三展示，使用公开目录顺序并保留站点健康指标与详情锚点。
- 首页中转站区块位于当前报价区块之后。
- Grok、Cursor、MUSE、JEV 使用核实的品牌图标；MUSE 与 JEV 使用统一单色呈现。
- 手机接码独立为商品分类，保留 `chatgpt-access-service` 稳定 slug、既有报价关联和旧链接兼容。
- 无数据库结构迁移。

验证：Web 类型检查、Web 测试、Web 生产构建、API 测试和 pipeline 测试通过后，按 `docs/QUICK_DEPLOY.md` 发布。由于本版本修改 `pipeline/`，部署后需要完成一次完整目录发布并确认失败数为 0。

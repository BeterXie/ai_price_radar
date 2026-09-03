# Release Notes - v3.7.29

## Highlights

- **受限商品看板与重新分类**：
  - 在管理页面 `/admin` 增加了专门针对「受限/已隐藏」及「未分类」商品的筛选视图，概览数据条增加相应统计徽章。
  - 支持在管理页面对商品进行手动重新分类（选择 22 种标准产品之一或设为未分类），并支持一键调用分类器进行单品重新识别。
  - 卡片高亮展示商家原始分类与具体的受限原因（如非 OpenAI Plus 账号原因）。
- **分类器排他规则加固**：
  - 拦截 API 中转模型分组（`plus分组` 等）、混合中转模型渠道代号（`(cx,5,4)` 等）、`不限时` 额度以及非官方 20 刀额度面额的商品误归类入 `chatgpt-plus`、`chatgpt-pro`、`codex-access`。

## Verification

- `apps/api`: 202 unit tests passing.
- `pipeline`: 219 unit tests passing.
- `detector`: 67 unit tests passing.
- `crawler/ldxp`: 78 unit tests and self-test passing.
- `apps/web`: 55 unit tests passing; TypeScript typecheck passing; Next.js 15.5 production build passing.

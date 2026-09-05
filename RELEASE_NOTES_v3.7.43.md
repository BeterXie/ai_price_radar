# Release Notes v3.7.43

## 变更摘要

- **后台管理商品列表展示库存数量与状态**：
  - 在 `GET /api/v1/admin/offers` 接口中返回 `stock_count` 字段，并新增 `stock_status` 查询过滤参数。
  - 在管理后台单品头部标签栏（用户标记区域）增加直观的库存状态胶囊：
    - 在售且有确切数量：`<span className="status-pill status-success">库存 X 件</span>`；
    - 缺货商品：`<span className="status-pill status-danger">缺货 (0件)</span>`；
    - 不可用商品：`<span className="status-pill status-danger">不可用</span>`；
    - 状态未知：`<span className="status-pill">库存未知</span>`。
  - 价格信息下方格式化展示中文库存状态与件数（如 `有货 · 36件` / `缺货 · 0件`），并进行颜色高亮区分。
- **后台筛选工具栏新增库存状态下拉框**：
  - 支持一键筛选 `全部库存状态`、`仅看有货`、`仅看缺货`。

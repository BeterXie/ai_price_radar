# Task brief

## Authority and scope
- Controller / user instruction: “对全网站的 UI、文案、交互、排版进行一次优化修改”。
- Deliverable surface, count, canvas, editable-source requirement: 优化现有 Next.js 网站；覆盖首页、报价目录与商品详情、指南入口与长文、关注清单、来源申请、转换工具、信息/政策页，并让 Admin 继承统一设计令牌与可用性修正。交付以可编辑的 React/TypeScript/CSS 源码和可运行网站为准，不单独制作 Figma 文件，除非用户另行要求。
- Interaction policy: user approval；先确认简报和视觉方向，再批量实施。

## Image role preflight
- Image role status: approved（本任务未附图）
- Image role: pending / not applicable
- Image placement: not-placed
- Image role approval evidence: 用户未提供图像，也未要求新增图像。
- Image role source/rights: not applicable

## Reader and truth
- Reader action and viewing condition: 访客在桌面或手机上快速判断“买的是什么、价格是否可比、是否有货、数据多久前更新、下一步去哪里核对”；教程读者在购买前后完成核对；来源方提交公开页面；管理员处理数据工作流。
- Required facts, copy, and refusals: 本站聚合公开报价、不参与交易；价格、库存、交付方式和退款规则以来源页为准；保留快照时间、来源、数据覆盖与可比性口径。禁止夸大“最低价”、虚构实时性、代替商家承诺、隐藏风险或制造不存在的功能。
- Allowed sources and material boundary: 仓库代码与线上真实数据为事实来源；OpenRouter、Vercel AI Gateway、Cloudflare Radar 只作为界面问题的参考，不复制品牌表面；不使用生成图像。
- Unknowns that must remain visible: 商家质保、期限或交付方式不明时继续明确显示“未注明/未知”；不把推断写成事实。

## Asset decision
- Content-essential assets: 现有品牌图标、平台图标、真实报价、价格历史图；移除会损失身份或证据。
- Identity assets: `apps/web/app/icon.svg`、`@icons-pack/react-simple-icons` 平台图标。
- Supporting-atmosphere assets: 无；视觉丰富度来自排版、数据关系、状态、交互与现有证据。
- Source / rights / generation route: 本地项目资产与已安装图标库；无外部图片进入产品界面，无生成路线。

## Form questions
- Role of each page, state, or canvas: 首页负责定位与入口；目录负责筛选与比较；详情负责单品决策；指南负责解释与恢复；关注清单负责空/有内容状态；来源申请与工具负责输入、校验、反馈和完成；信息页负责信任说明。
- Viewer distance, dwell time, and access context: 首屏 3–10 秒完成定位；目录为 1–10 分钟高密度扫描；详情与指南为中长阅读；移动端以单手触达、横向筛选与分层展开为主。
- Capacity check with real copy: 使用真实中文商品长标题、99+ 报价、三层筛选、四项统计、长表单和 48 篇指南进行压力测试。
- Current-task visual mother object, relation, or event: “报价台账”——每条价格与来源、时间、库存和可比性绑定；荧光信号只标记可行动或状态变化。
- Title-removal test: 移除标题后，来源时间、可比范围、报价层级、风险说明和核对动作仍能明确指向 AI 商品报价决策。
- Single-canvas counterfactual, when relevant: 不适用。现有产品必须通过多个相关页面与状态完成任务。

## Felt brief
进入页面时先感到信息可信、更新有迹可循；使用中维持“快速扫描与必要展开”的节奏；离开时保留清楚的决策边界和核对动作。

## Autonomous fallback
- Least-assumptive permitted choice: 保留当前纸张底色、黑色文字和荧光绿状态信号；重构层级、令牌与组件，不更改业务口径或接口。
- Counterfactual result and unresolved risk: 若用户未选方向，不能进入全站高保真实施；现阶段只制作三套方向预览。

## Form challenge
- Authority: 用户明确要求修改“全网站”，因此交付形态必须是可运行的多页面产品界面。
- Reader action: 用户需要搜索、筛选、比较、展开、关注、核对、提交与恢复，单张视觉无法完成。
- Single-canvas test: 不成立；方向预览只是选择依据，最终成果是完整状态流。

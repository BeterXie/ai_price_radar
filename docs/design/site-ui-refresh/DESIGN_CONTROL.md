# Design control

Design schema: v3.1

## Gate 1 — Proposition
Gate 1 status: released
Image role status: approved
Image role: pending / not applicable
Image placement: not-placed
Image role approval evidence: 用户未提供图像。
Image role source/rights: not applicable
Brief status: approved
Direction status: approved
Direction preview shown: yes — 初稿 `signal-ledger.png`, `radar-workbench.png`, `editorial-atlas.png`, `signal-ledger-mobile.png`；修订稿 `signal-ledger-r2.png`, `signal-ledger-r2-mobile.png`
Proposed direction: signal-ledger-r2
Approved direction: signal-ledger-r2
Brief approval evidence: 2026-08-22 用户确认：“确认新版01，按此实施全站”。
Direction approval evidence: 2026-08-22 用户确认：“确认新版01，按此实施全站”。该确认对应已展示的 `signal-ledger-r2.png` 与 `signal-ledger-r2-mobile.png`。
Decision: Gate 1 released；按 `signal-ledger-r2` 进入生产代码级试点，试点渲染获批后再覆盖其余路由。
User approval: approved
Approval evidence: 2026-08-22 用户明确批准新版 01 并授权按此实施全站。
Source route: local product evidence → adjacent official product references → code-native preview
Source policy: 外部界面仅作 benchmark，不进入产品资产。
Contact sheet: `docs/design/site-ui-refresh/direction-preview.html`
Asset ledger: `docs/design/site-ui-refresh/ASSET_LEDGER.md`
Hero source: 真实产品数据与现有品牌图标；无图片 hero。
Generation exception: none

### Subject and audience
- Subject: 公开 AI 商品报价、库存、交付方式、来源与更新时间。
- Human stake: 用户可能因低价、过时库存、含糊交付或商品口径混淆而做错购买判断。
- Audience task: 在低认知负担下找到可比较报价，并知道哪些信息仍需去来源页核对。
- Unique soul: 报价不是孤立数字，而是带有来源、时间、库存、可比性和风险边界的“记录”。
- Required language: 简体中文为主，产品与平台固有英文名保留。
- Refusals: 装饰性技术微文案、无意义序号、无因渐变/玻璃卡、夸大低价、伪实时、把所有内容卡片化。

### Deliverable-form declaration and surface lock
- Form: production product UI；React/TypeScript/CSS 可编辑源码与交互式网站。
- Route families: 首页；目录/详情；指南入口/长文；关注清单；来源申请；本地工具；信息/政策；Admin 共享系统。
- Required states: default、information-dense、filter overlay/disclosure、empty/recovery、loading/submitting、success、error、decline/disabled。
- Canvas: responsive；重点验收 1440×900、1024×768、390×844。
- Reading mode: 扫描、比较、展开、长文阅读和表单完成。

### Reference family and decomposition

| Reference | First attention / path | Functional density | Transferable principle | Refuse copying |
| --- | --- | --- | --- | --- |
| [OpenRouter Models](https://openrouter.ai/models) | 搜索 → 模态标签 → 列表/表格 → 模型证据 | 分组侧栏、模式切换、描述与指标同层 | 将复杂筛选分层，给高频比较提供视图选择 | 紫色品牌、完整左栏结构 |
| [Vercel AI Gateway Models](https://vercel.com/ai-gateway/models) | 大标题与定义 → 搜索/类别 → 高密度表格 | 宏观静区与数据密区明确切换 | 先建立任务，再进入比较；表头和度量对齐 | Vercel 黑白品牌语法与表面网格 |
| [Cloudflare Radar](https://radar.cloudflare.com/) | 全局搜索/地区/时间 → 主趋势 → 分主题证据 | 固定方向、时间状态、分组数据卡 | 全局状态应持续可见；信息按问题域分组 | 橙色品牌与仪表板模板 |
| Current AI Price Radar | 大标题 → 搜索 → 最近更新 → 报价行 | 纸面、黑墨、荧光绿状态已形成识别 | 保留“台账 + 信号”关系，增强任务清晰度 | 继续堆叠 CSS 覆盖、所有页面同一密度 |

### Evidence selection

| Selected evidence | Source | Confidence | Task role | Why this, not a default |
| --- | --- | --- | --- | --- |
| 宏观静区与数据密区切换 | Vercel AI Gateway | high | 首页与目录节奏 | 对应“先理解，再比较”的真实任务 |
| 分层筛选与列表/表格视图 | OpenRouter | high | 报价目录 | 当前筛选和超长列表需要更可控的工作区 |
| 全局时间状态与证据分组 | Cloudflare Radar | high | 快照、新鲜度、状态反馈 | 数据更新时间是用户信任的关键事实 |
| 台账式横向结构与单一荧光信号 | 当前产品 | highest | 品牌延续 | 已有辨识度且与“监测/变化”有直接原因 |

### Technique rationale and density target

| Choice | Subject cause | Viewer effect | Surface job |
| --- | --- | --- | --- |
| 台账边界与对齐 | 报价必须与来源、时间和状态绑定 | 更快横向比较 | 目录、详情、历史与方法页 |
| 荧光绿仅标状态/主动作 | 数据变化和可行动项需要信号 | 一眼定位有货、更新、选择与成功 | 全站语义色系统 |
| 高对比标题 + 正文宽度约束 | 中文长标题与长文并存 | 快速定位且持续可读 | 首页、详情、指南 |
| 桌面工作区 / 移动端分层披露 | 筛选项多、报价列表长 | 降低首屏拥堵，保留完整能力 | 目录和工具 |
| 状态说明紧邻动作 | 用户输入与网络反馈存在风险 | 知道正在做什么、失败如何恢复 | 表单、关注、工具、Admin |

- Target density: 每个关键页面/状态至少四个相关设计行为；首屏一个主事件加不超过三个支持层。操作页面优先功能密度，品牌入口和空/完成状态提高审美完成度。
- Type ladder: Display 68–72/71；Page 44–48/52；Section 28–32/38；Body 16–18/27；Compact 14/20；Label 12/18；Data 18–22/26。移动端 Display 42–44，结构重组而非缩小桌面布局。
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 72。
- Palette cause: 温暖纸色来自“公开台账”；干净白色承载可操作面板；黑墨与加深的中性线保持证据可读；降低饱和度的荧光绿只代表更新、库存、选择、成功；矿物青只用于信息链接和覆盖度。拒绝蓝紫 AI 渐变和暗色霓虹技术场。
- Type cause: 沿用 Geist + 中文系统无衬线，靠层级、数字等宽和对齐建立识别。拒绝装饰衬线与满屏 mono 技术口吻。

### Three direction candidates
- `signal-ledger`（推荐）：延续现有纸张/黑墨/荧光绿，建立全站台账式结构、强状态栏和更清晰的决策层级。
- `radar-workbench`：深色工具侧栏 + 明亮数据画布，更强操作感和筛选效率，品牌气质偏专业控制台。
- `editorial-atlas`：编辑式大标题 + 温暖资料页 + 章节索引，教程与方法更有阅读魅力，目录操作密度较柔和。

Revision contract: preserve — 用户认可的 `signal-ledger` 台账骨架、事实口径、现有品牌图标、纸面与实时信号关系；remove — 绿色情绪化滥用、“最低价”式夸大口吻、9–10px 微字与重复说明；strengthen — 中性对比、信息色分工、直接中文、桌面标题比例和移动端可读性；locked — API/SEO URL/业务逻辑；reference level — 成熟数据目录与可信比较产品。
Interpretive copy status: approved — 用户通过“确认新版01，按此实施全站”批准方向预览中的新增文案，后续页面文案仍逐页遵守事实边界。

### Signal Ledger r2 review
- Render: `signal-ledger-r2.png`（桌面）与 `signal-ledger-r2-mobile.png`（手机）。
- Palette: 纸面 `#f4f1e8`、面板 `#fffef9`、墨色 `#171914`；信号绿 `#bae64c` 只标刷新/库存/选中/成功，矿物青 `#1f645c` 只标信息入口与覆盖度。
- Type: 桌面标题约 69.7px；手机标题 43px / 两行；方向内最小可见字号 11px。
- Responsive: 390×844 与桌面画布均无横向溢出；手机搜索框、报价面板和两列筛选均在视口内重组。
- Copy: 已移除 `signal-ledger` 中的“最低价”口吻；AI-flavor blacklist 扫描无命中。新增解释性文案仍待用户批准。
- Remaining risk: Gate 1 已释放；Gate 2 生产试点等待用户确认，确认前不扩展到其余路由族。

## Gate 2 — Master
Decision: released — 首页、报价目录与关键移动筛选态获批，按角色图扩展其余路由族
HTML master: local production Next.js routes at `/` and `/products`; mobile filter state at `/products?brand=OpenAI&in_stock=true&updated_within_hours=24&state=filter-open`
Approved render: `pilot-home-desktop.png`, `pilot-home-mobile.png`, `pilot-catalog-desktop.png`, `pilot-catalog-mobile-filter.png`
User approval: approved
Approval evidence: 2026-08-22 用户在收到“请回复：确认 Gate 2 试点，继续实施其余页面”的明确请求后回复：“确认”。
Visual review: `PILOT_REVIEW.md` — no unresolved P0/P1; 1440×900 desktop and 390px mobile states have zero horizontal overflow; mobile filter controls are at least 44px and use a 12px minimum label size.
Benchmark comparison: `PILOT_REVIEW.md` — `Signal Ledger` reaches the adjacent data-catalog benchmark through six type roles, persistent snapshot/scope state, a quiet-to-dense transition, grouped evidence rows, and explicit apply/reset/recovery paths without copying another product's brand surface.

## Gate 3 — Delivery
Decision: released — approved Signal Ledger master implemented across all route families and verified in a production build
Editable format: Next.js React/TypeScript/CSS source
Editable Figma file: not requested
Primary frame/node: not applicable
Figma node audit: not applicable
Figma comparison: not applicable
Interactive HTML: production Next.js application; local verified build at `http://127.0.0.1:4180`
Motion inventory: 150 ms hover/press feedback, native disclosure state, smooth in-page navigation; `prefers-reduced-motion` removes transitions and smooth scrolling
Full-site review: `FULL_SITE_REVIEW.md`

from __future__ import annotations

from typing import Any

INITIAL_SKILLS_DATA: list[dict[str, Any]] = [
    {
        "slug": "pelican-bicycle-benchmark",
        "kind": "benchmark",
        "title": "全网大模型“鹈鹕骑自行车”抗降智与空间推理横向评测",
        "subtitle": "2D SVG 动画零测试直接生成，一眼鉴别满血版与降智版",
        "summary": "通过让模型一次性输出包含物理连杆、SVG 坐标计算、CSS 关键帧动效的“鹈鹕骑自行车”HTML，全面检验模型的空间感知、机械连杆推演与防偷懒能力。内置 6 份真实大模型生成动效在线对比试玩！",
        "prompt_template": "创建一个HTML保存到本地，内容是SVG绘制一个 鹈鹕骑自行车 的2D动画，你不需要任何测试。",
        "author_name": "社区流行 Benchmark",
        "author_url": "",
        "repo_url": "",
        "stars_count": 5000,
        "install_command": "",
        "demo_url": "/demos/benchmarks/pelican-gpt6-astra-full.html",
        "demo_type": "pelican_arena",
        "tags": ["降智检测", "SVG动画", "空间推理", "防坑体检"],
        "target_models": ["GPT-6", "GPT-5.6", "Gemini 3.8", "Claude 3.5"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": True,
        "sort_order": 100,
        "content_markdown": """# 为什么“鹈鹕骑自行车”能测出大模型是否降智？

“让模型绘制一个 鹈鹕骑自行车 的 2D 动画，且不需要任何测试”已经成为当前全球 AI 社区最火热的模型降智体检 Prompt 之一。

## 为什么这个测试能击中模型软肋？

1. **复杂机械与物理运动学认知**：
   自行车包含车架几何结构、前后轮同轴与辐条、踏板曲柄连杆。满血模型知道踏板旋转时脚踝与膝盖需要做逆向动力学摆动，车轮需要匀速自转，且辐条具有旋转向心感。
2. **生物形态与机械物体的空间结合**：
   鹈鹕具有极其夸张的喉囊、大喙和翅膀羽毛，模型必须计算动物身体与车把、座垫、踏板三点接触的相对坐标，若空间感知差，鸟体会飘在车外或穿模。
3. **拒绝偷懒与长代码闭合能力**：
   降智版或小模型（如被官方悄悄降级为 mini 或粗量化版）经常用简单的几根直线凑数，甚至在生成几行后用 `/* 其余动效请自行添加 */` 偷懒；而满血版一次性输出数十层精细路径、光影与平滑关键帧。

---

## 满血版 vs 降智版 对照标准

| 维度 | 满血版表现（如 GPT-6 Astra 满血） | 降智版 / 偷懒表现 |
| :--- | :--- | :--- |
| **整体构图** | 丰富的情境（海滨、云朵、路标、微风），层次分明 | 寡淡单调，只有孤零零的几个色块 |
| **机械联动** | 曲柄带动踏板双脚交替踩踏，车轮自转，比例协调 | 仅车轮转动或身体死板平移，脚踩不到踏板上 |
| **生动细节** | 飘动的围巾、随呼吸眨眼、鸟喙色泽与反光细腻 | 鸟像简笔画，色块错位，缺少特征喉囊 |
| **代码量** | 10KB ~ 30KB 充沛的 SVG 路径与 CSS 动效 | 2KB ~ 4KB 简陋拼凑代码 |

---

## 快速体检指南

1. 点击右上方 **「一键复制测试 Prompt」**；
2. 粘贴到您的 ChatGPT、Claude、Codex 或 Cursor 中发送；
3. 将模型输出的 HTML 保存并在浏览器打开，对照本页上方的 6 大真实实测样本，即可一目了然！
""",
    },
    {
        "slug": "bajie-bicycle-benchmark",
        "kind": "benchmark",
        "title": "东方意象与拟人化机械评测：猪八戒骑自行车 2D 动画",
        "subtitle": "九齿钉耙、僧袍飘逸与自行车踩踏，测试东方文化认知与非现实物理融合",
        "summary": "让模型绘制西游记经典角色猪八戒骑自行车，考查模型在面对神话文化符号（黑僧帽、九齿钉耙、飘带）与现实机械运动（蹬车、转轮）时的自洽融合与创意发挥能力。",
        "prompt_template": "创建一个HTML保存到本地，内容是SVG绘制一个 猪八戒骑自行车 的2D动画，你不需要任何测试。",
        "author_name": "社区西游 Benchmark",
        "author_url": "",
        "repo_url": "",
        "stars_count": 3200,
        "install_command": "",
        "demo_url": "/demos/benchmarks/bajie-gpt6-astra.html",
        "demo_type": "iframe",
        "tags": ["降智检测", "文化意象", "SVG动画", "Codex"],
        "target_models": ["GPT-6", "Claude 3.5", "Codex"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": True,
        "sort_order": 95,
        "content_markdown": """# 猪八戒骑自行车：测试大模型的跨文化概念融合

在西游记的神话语境中融入现代交通工具，能极大考查大模型的**跨域概念拟合**能力：

- 能否准确还原猪八戒的标志性服饰（黑色僧帽、僧袍飘带、粉嫩憨厚的面容）？
- 背上的**九齿钉耙**是否能合理背负且不阻碍骑车动作？
- 田园麦浪与西行慢骑的情绪氛围是否能通过 SVG 配色与微动效传达？

在 GPT-6-Astra 的满血测试中，模型给出了极具意境的标语：*“去西天，也可以慢慢骑”*，展现了极强的审美与人文理解。
""",
    },
    {
        "slug": "taste-skill",
        "kind": "skill",
        "title": "taste-skill：Anti-Slop 前端审美与去模版化设计规范",
        "subtitle": "专治 AI 前端粗制滥造与烂俗审美，让生成的界面告别廉价模版感",
        "summary": "GitHub 突破 2.9 万 Stars 的神级前端 Skill！通过意图推断（Design Read）、审美三刻度盘（VARIANCE / MOTION / DENSITY）与严格预检机制，彻底根除紫色渐变、居中 Hero、死板三列卡片等 AI 通病。",
        "prompt_template": "",
        "author_name": "Leonxlnx",
        "author_url": "https://github.com/Leonxlnx",
        "repo_url": "https://github.com/Leonxlnx/taste-skill",
        "stars_count": 29000,
        "install_command": 'npx skills add https://github.com/Leonxlnx/taste-skill --skill "design-taste-frontend"',
        "demo_url": "",
        "demo_type": "none",
        "tags": ["UI 审美", "前端开发", "Tailwind", "Anti-Slop"],
        "target_models": ["Claude 3.5", "Cursor", "Codex", "GPT-4o"],
        "related_product_slug": "claude-pro",
        "is_pinned": True,
        "sort_order": 90,
        "content_markdown": """# taste-skill: 专治 AI 前端审美的良药

大多数 LLM 生成的前端界面之所以糟糕，是因为模型默认退回到了最烂俗的套路审美：
- 居中对齐的 Hero 标题配深色背景；
- 毫无意义的 AI 紫色/蓝粉渐变网格；
- 机械的三列等宽功能卡片；
- 到处乱加的悬浮发光与毛玻璃。

`taste-skill` 强制 AI 在动代码之前执行 **Design Read（需求读空气）**，并根据三个核心刻度盘调教输出：
- `DESIGN_VARIANCE`：打破机械对称，引入有机排版；
- `MOTION_INTENSITY`：从静态到电影级物理动效控制；
- `VISUAL_DENSITY`：从艺术留白到密集数据驾驶舱自适应。
""",
    },
    {
        "slug": "victor-design",
        "kind": "skill",
        "title": "Victor Design：以人为中心的视觉设计与 Figma 矢量交付工作流",
        "subtitle": "让 AI 像资深设计师一样产出海报、交互 UI 与无损 Figma 矢量框架",
        "summary": "曾获公开评比第一名的专业视觉设计 Skill！涵盖海报、社交图谱、多状态 UI 与 PPT。配合 DOM Migrate 插件可将生成的 HTML 页面 100% 转换为 Figma 可编辑矢量组件与 Auto Layout。在实测中，GPT-5.6 挂载该技能后直接实现艺术级跃升！",
        "prompt_template": "",
        "author_name": "victorzhang016-code",
        "author_url": "https://github.com/victorzhang016-code",
        "repo_url": "https://github.com/victorzhang016-code/victor-design",
        "stars_count": 1200,
        "install_command": "git clone https://github.com/victorzhang016-code/victor-design.git ~/.agents/skills/victor-design",
        "demo_url": "/demos/benchmarks/pelican-gpt56-vds.html",
        "demo_type": "iframe",
        "tags": ["视觉设计", "Figma", "UI/UX", "海报排版"],
        "target_models": ["GPT-5.6", "GPT-6", "Claude 3.5", "Cursor"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": True,
        "sort_order": 85,
        "content_markdown": """# Victor Design: 人文视觉与 Figma 级交付

在多项真实评测中，Victor Design 击败了众多一线设计 Skill，荣获公开票选第一名。

## 为什么它与众不同？
1. **形式先于风格**：先判定交付目标是单张海报、社交图卡、交互流程还是演示文稿；
2. **真实素材优先**：工作区事实与内容骨架优先，禁止随意敷衍；
3. **HTML 到 Figma 无损迁移**：通过其配套的 DOM Migrate 插件，将生成的受控 HTML 完美还原为 Figma 的 Auto Layout、网格系统、文本图层与组件约束！
""",
    },
    {
        "slug": "awesome-design-ui",
        "kind": "skill",
        "title": "awesome-design-ui：知名品牌工业级设计系统重构",
        "subtitle": "集纳 Linear、Apple、Stripe 等知名品牌规范，沉浸式升级现有组件",
        "summary": "VoltAgent 开源的视觉重构技能库。内置几十家顶级科技公司与知名站点的 DESIGN.md 规范文件，让 AI 严格按照指定品牌的色彩系统、字体梯度和卡片阴影重构网页或组件。",
        "prompt_template": "",
        "author_name": "VoltAgent",
        "author_url": "https://github.com/VoltAgent",
        "repo_url": "https://github.com/VoltAgent/awesome-design-ui",
        "stars_count": 3500,
        "install_command": 'npx skills add https://github.com/VoltAgent/awesome-design-ui --skill "awesome-design-ui"',
        "demo_url": "",
        "demo_type": "none",
        "tags": ["Design System", "品牌规范", "Linear 风格", "前端重构"],
        "target_models": ["Cursor", "Windsurf", "Claude 3.5"],
        "related_product_slug": "claude-pro",
        "is_pinned": False,
        "sort_order": 80,
        "content_markdown": """# awesome-design-ui: 顶级大厂设计系统开箱即用

当你想让现有的项目拥有 Linear 的高级深色科技感、Apple 的温润克制、或是 Stripe 的优雅现代感时，这个 Skill 是最快的捷径。

它收录了精细提取的品牌 `DESIGN.md`，在不破坏现有功能业务逻辑的前提下，有层次地升级页面的字体比例、阴影深度与响应式间距。
""",
    },
    {
        "slug": "agent-browser",
        "kind": "skill",
        "title": "agent-browser：Vercel 官方极速原生 Rust 浏览器自动化 CLI",
        "subtitle": "无需笨重 Puppeteer，AI 基于 CDP 与无障碍树毫秒级操控网页",
        "summary": "Vercel 实验室出品。基于原生 Rust 编译的超轻量级浏览器自动化命令行工具。AI 直接利用无障碍树（Accessibility Tree）快照与精简 @eN 元素引用实现精准点击、表单填写、自动截图与端到端测试。",
        "prompt_template": "",
        "author_name": "Vercel Labs",
        "author_url": "https://github.com/vercel-labs",
        "repo_url": "https://github.com/vercel-labs/agent-browser",
        "stars_count": 8600,
        "install_command": "npm i -g agent-browser && agent-browser install",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["浏览器自动化", "Vercel", "Rust", "E2E测试", "爬虫"],
        "target_models": ["Codex", "Cursor", "Claude Code", "Antigravity"],
        "related_product_slug": "openai-api-credit",
        "is_pinned": False,
        "sort_order": 75,
        "content_markdown": """# agent-browser: 为 AI Agent 而生的极速浏览器

传统的 Playwright 或 Puppeteer 在让大模型操作时存在痛点：DOM 树过于庞大消耗海量 Token、渲染等待慢、容易超时。

Vercel Labs 的 `agent-browser` 采用原生 Rust 编写：
- 提取紧凑的无障碍语义树（Accessibility Tree）；
- 用极短的 `@e1`、`@e2` 别名定位交互元素；
- 秒级启动，支持会话持久化与状态录像；
- 支持测试 Electron 桌面客户端（Slack, VS Code, Discord）。
""",
    },
    {
        "slug": "open-code-review",
        "kind": "skill",
        "title": "Open Code Review (OCR)：阿里开源的 Git 代码审查 Agent",
        "subtitle": "基于 Git Diff 行级精准审查，捕获安全隐患、性能瓶颈与代码 Bug",
        "summary": "阿里巴巴团队开源的专业代码审查工具。自动读取工作区改动、PR 或 Commit 提交，在理解业务上下文的前提下输出代码行级别的结构化审查意见与自动修复建议。",
        "prompt_template": "",
        "author_name": "Alibaba",
        "author_url": "https://github.com/alibaba",
        "repo_url": "https://github.com/alibaba/open-code-review",
        "stars_count": 2800,
        "install_command": "npm install -g @alibaba-group/open-code-review",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["Code Review", "代码质量", "阿里巴巴", "Git"],
        "target_models": ["Claude 3.5", "GPT-4o", "DeepSeek", "Cursor"],
        "related_product_slug": "claude-pro",
        "is_pinned": False,
        "sort_order": 70,
        "content_markdown": """# Open Code Review: 阿里企业级自动化 Review

通过 `@alibaba-group/open-code-review`，AI 在审查代码时能够做到：
- 精确到代码行号的具体改进提示；
- 区分业务背景（通过 `--background` 传入架构上下文）；
- 自动辨别内存泄漏、并发死锁与边界越界。
""",
    },
    {
        "slug": "storage-analyzer",
        "kind": "skill",
        "title": "storage-analyzer：macOS / Windows 磁盘占用智能诊断助手",
        "subtitle": "只读安全全盘扫描，三色灯智能分类，生成交互式 HTML 空间报告",
        "summary": "专为 AI Agent 设计的系统存储分析 Skill。严格遵守只读安全铁律，自动识别跨平台文件布局，揪出隐藏的庞大容器缓存，分级给出清理方案并生成排版精美的只读 HTML 交互报告。",
        "prompt_template": "",
        "author_name": "KKKKhazix",
        "author_url": "https://github.com/KKKKhazix",
        "repo_url": "https://github.com/KKKKhazix/khazix-skills",
        "stars_count": 900,
        "install_command": "git clone https://github.com/KKKKhazix/khazix-skills.git ~/.codex/skills/storage-analyzer",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["系统工具", "磁盘清理", "Python", "报告生成"],
        "target_models": ["Codex", "Claude Code", "Antigravity"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": False,
        "sort_order": 65,
        "content_markdown": """# storage-analyzer: 磁盘空间的智能体温计

电脑 C 盘或 Mac 存储满了？让 AI 来诊断时，最怕的是 AI 误删了重要工作文件或聊天记录。

`storage-analyzer` 确立了**只读诊断铁律**：
- 🟢 **可自动清理**：确定无害的开发依赖缓存（npm、pip、Xcode DerivedData）；
- 🟡 **需人工判断**：离线视频、项目源码 node_modules（提供一键跳转访达/资源管理器审查）；
- 🔴 **谨慎清理**：系统级镜像与已安装应用本体。
生成交互式 HTML 可折叠报告，直观且安全。
""",
    },
    {
        "slug": "grilling",
        "kind": "skill",
        "title": "grilling / grill-me：需求压力测试与架构连环逼问",
        "subtitle": "在动手前逼出隐藏假设与系统盲点，避免写出大返工的垃圾代码",
        "summary": "知名工程师 Matt Pocock 与 Jesse Vincent (obra) 打造的架构拷问技能。AI 扮演极度苛刻的技术委员会，以决策树前沿分轮次向用户提出尖锐的架构取舍问题，自动沉淀 ADR 决策记录。",
        "prompt_template": "",
        "author_name": "Matt Pocock / obra",
        "author_url": "https://github.com/mattpocock",
        "repo_url": "https://github.com/mattpocock/skills",
        "stars_count": 4200,
        "install_command": 'npx skills add https://github.com/mattpocock/skills --skill "grilling"',
        "demo_url": "",
        "demo_type": "none",
        "tags": ["架构设计", "需求分析", "ADR", "决策压力测试"],
        "target_models": ["Claude 3.5", "o1", "o3", "GPT-4o"],
        "related_product_slug": "claude-pro",
        "is_pinned": False,
        "sort_order": 60,
        "content_markdown": """# grilling: 动手前的无情拷问

写代码最忌讳的是“拿到模糊需求就开始敲键盘”。

`grilling` 技能通过决策前沿（Decision Frontier）算法，一轮一轮向你抛出结构化问题：
```
❓ Q1 - 是否需要支持历史版本回滚？
➡️ 推荐方案：先基于只读快照实现，暂不引入完整版本树。
```
逼迫开发者在写第一行代码前，想清所有边界情况与技术取舍。
""",
    },
    {
        "slug": "domain-modeling",
        "kind": "skill",
        "title": "domain-modeling：DDD 领域驱动建模与限界上下文沉淀",
        "subtitle": "统一业务语言，主动捕捉语义冲突，维护规范的 CONTEXT.md 与 ADR",
        "summary": "在系统设计过程中主动构建并磨砺领域模型。敏锐挑战模糊用词与代码语义冲突，自动创建与维护项目根目录下的 CONTEXT.md 术语表与 ADR 决策日志。",
        "prompt_template": "",
        "author_name": "Matt Pocock",
        "author_url": "https://github.com/mattpocock",
        "repo_url": "https://github.com/mattpocock/skills",
        "stars_count": 4200,
        "install_command": 'npx skills add https://github.com/mattpocock/skills --skill "domain-modeling"',
        "demo_url": "",
        "demo_type": "none",
        "tags": ["DDD", "领域驱动设计", "架构规范", "TypeScript"],
        "target_models": ["Claude 3.5", "Codex", "Cursor"],
        "related_product_slug": "claude-pro",
        "is_pinned": False,
        "sort_order": 55,
        "content_markdown": """# domain-modeling: 根治术语混乱与架构腐化

当团队或 AI 把 “User”、“Customer”、“Account” 混着叫时，系统架构就已经开始走向腐化。

`domain-modeling` 技能让 AI 在编码过程中主动扮演领域专家的角色，当发现前后语义冲突时主动叫停并对齐，同时将成熟的架构决策记录到 `docs/adr/` 中。
""",
    },
    {
        "slug": "agently-mail",
        "kind": "skill",
        "title": "agently-mail：腾讯 QQ 邮箱官方 Agent 邮件工作流",
        "subtitle": "官方 OAuth 安全授权，让 AI 自主处理邮件收发、检索与附件整理",
        "summary": "腾讯 QQ 邮箱团队推出的官方 Agent 技能。通过 OAuth 授权与 agently-cli 配合，让 AI 拥有合规读取、分类、总结最新邮件以及撰写和回复邮件的端到端能力。",
        "prompt_template": "",
        "author_name": "Tencent QQ Mail",
        "author_url": "https://agent.qq.com",
        "repo_url": "https://agent.qq.com",
        "stars_count": 1500,
        "install_command": "npm i -g @tencent-qqmail/agently-cli && npx skills add https://agent.qq.com --skill -g -y",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["腾讯", "QQ邮箱", "邮件自动化", "工作流"],
        "target_models": ["All Models", "Claude", "GPT-4o"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": False,
        "sort_order": 50,
        "content_markdown": """# agently-mail: 官方出品的邮件自动化助手

通过腾讯官方 `@tencent-qqmail/agently-cli`，AI 拥有了对 QQ 邮箱的安全管理能力：
- “帮我看看今天有没有重要的财务或签约邮件”
- “帮我整理最近收到的发票附件并归纳列表”
- “以商务礼貌的口吻起草一封合作回复邮件”
""",
    },
]

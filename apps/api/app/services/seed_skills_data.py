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
        "target_models": ["GPT-6 Astra", "GPT-5.6", "Gemini 3.8", "Claude 4.5 Sonnet"],
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
        "slug": "crab-riding-tricycle-pk",
        "kind": "pk",
        "title": "大模型极客对决：GLM-5.3-Flash vs Gemini 3.8 Flash 螃蟹骑三轮车实测 PK",
        "subtitle": "同等高难度 Prompt 零测试直出：2D 纯矢量切线动力学美学 vs 3D 空间轴测与 WebAudio 全家桶",
        "summary": "针对高难度提示词“生成完全自包含SVG动画：螃蟹骑带辅助轮三轮车沿花坛圆周骑行、8足严格绑定曲柄与车把、12秒无缝循环”，GLM-5.3-Flash 与 Gemini-3.8-Flash-Medium 分别交出了两份风格截然不同却又极具代表性的高分答卷。本页面提供双模型分屏实时对决、代码量与实现原理深度对比！",
        "prompt_template": """生成一个完全自包含的SVG动画，内容是一只螃蟹骑着带辅助轮的儿童三轮车，沿着圆形的花坛边缘做圆周骑行，同时螃蟹的8条腿里，有2条腿控制车把转向，剩下6条腿跟着3个车轮的曲柄同步运动。
要求：
1. 螃蟹的身体始终保持在三轮车座椅正上方，骑行轨迹和花坛边缘完全重合；
2. 所有车轮的旋转方向和螃蟹的圆周骑行方向完全匹配，辅助轮不出现侧翻错位；
3. 螃蟹的每条腿都严格绑定到对应运动部件，没有肢体穿进车身、车轮的情况；
4. 整体动画时长12秒，循环播放，所有元素用SVG路径绘制，不嵌入任何位图资源。""",
        "author_name": "AI Price Radar 实验室",
        "author_url": "https://ai.pricememo.cn",
        "repo_url": "",
        "stars_count": 6800,
        "install_command": "",
        "demo_url": "/demos/pk/crab-glm-5-3-flash.html",
        "demo_type": "crab_arena",
        "tags": ["模型PK", "GLM-5.3-Flash", "Gemini 3.8 Flash", "SVG动画", "逆运动学", "降智检测"],
        "target_models": ["GLM-5.3-Flash", "Gemini 3.8 Flash"],
        "related_product_slug": "gemini-advanced",
        "is_pinned": True,
        "sort_order": 99,
        "content_markdown": """# 螃蟹骑三轮车 12s 动画：大模型机械空间推理的“终极炼金石”

在继“鹈鹕骑自行车”之后，AI 社区与开发者设计了一道难度成倍跃升的几何运动学与空间推理提示词：**“螃蟹骑着带辅助轮的三轮车，沿着圆形花坛做 12 秒圆周骑行”**。

这道题目为何极度考验大模型的能力？

1. **非笛卡尔坐标系的圆周切线运动学**：
   三轮车不是在水平直线上前进，而是在 $R$ 半径的圆形花坛边缘做圆周公转。车头朝向必须随着切线角 $\\\\theta$ 实时转动，且前轮、左右后轮、左右辅助轮因处于不同回转半径，其线速度与滚动角速度存在复杂的阿克曼转向或差速约束。
2. **多足类生物与机械刚体的逆运动学（IK）铰接**：
   螃蟹具有多对步足与螯肢。提示词明确要求：2 条腿控制车把转向，剩下 6 条腿分别锁在 3 个车轮的曲柄踏板上。模型必须准确计算足尖目标点（Target），推导股节/胫节的膝关节坐标，确保无论车轮如何自转、车把如何偏航，关节自然外拱而不发生穿模刺穿。
3. **严格的时间齿比闭环（12.0 秒）**：
   所有车轮在 12 秒结束时，必须正好旋转整数圈（如 4 圈、6 圈、12 圈），以保证首尾关键帧 0 误差无缝循环。

---

## 两大模型的解题哲学对比

### 方案一：GLM-5.3-Flash —— 灵动优雅的纯矢量 2D 极简主义
* **代码规模**：542 行，仅 27.8 KB。
* **架构核心**：将三轮车与螃蟹抽象为侧视矢量 Rig，并沿花坛切线施加平移与旋转；通过 `scale(cos)` 实现前轮转向的伪透视压缩。
* **生物学直觉**：直接将 2 只大螯定义为前两条控把腿，6 条步足分为前、后、辅助轮曲柄。
* **视觉亮点**：内置红色飞扬披风、微醺腮红，并利用经典的 Park-Miller 伪随机数算法让花坛花草随微风生动摇曳。

### 方案二：Gemini 3.8 Flash (Medium) —— 极客硬核的 3D 物理与工程全家桶
* **代码规模**：1652 行，达 80.3 KB。
* **架构核心**：在 SVG 内手写了一整套 **3D 空间轴测投影引擎（X, Y, Z + 方位角/仰角变换）**，支持鼠标在画布上自由 360° 拖拽视角！
* **物理严谨性**：计算真正的阿克曼转向角 $\\\\arctan(\\\\text{wheelbase} / R)$，8 条步足刚性铰接曲柄，并额外赋予大螯举着墨镜向观众致意。
* **Web Audio 原生合成器**：没有任何外部音效文件，通过原生 Web Audio API 的 Oscillator 实时合成了 1480Hz/2220Hz/2960Hz 的双音自行车铃铛声与踏板机械咔哒声。
* **SVG 序列化导出**：提供一键生成独立自包含 `.svg` 文件的功能。

---

## 快速评测方法
1. 点击上方的 **「复制测试 Prompt」**；
2. 发送给您正在测试的任意大模型（如 Claude 4.5、GPT-5.6、DeepSeek 等）；
3. 检查模型能否做到肢体不穿模、车轮转速匹配以及首尾 12 秒完美循环！
""",
    },
    {
        "slug": "crab-tricycle-glm-5-3-flash",
        "kind": "pk",
        "title": "GLM-5.3-Flash 实测：螃蟹骑三轮车 12s 纯矢量自包含动画",
        "subtitle": "轻量优雅的 2D 骨骼逆向动力学，严格切线圆周运动与微风摇曳花坛",
        "summary": "由 GLM-5.3-Flash 生成的自包含 SVG 动画。仅用 542 行代码与 27.8 KB 体积，完美实现切线对齐圆周运动、阿克曼转向透视压缩、6足分踏3组曲柄连杆与大螯握把，辅以可爱的红披风飘动与确定性伪随机花木摇曳。",
        "prompt_template": """生成一个完全自包含的SVG动画，内容是一只螃蟹骑着带辅助轮的儿童三轮车，沿着圆形的花坛边缘做圆周骑行，同时螃蟹的8条腿里，有2条腿控制车把转向，剩下6条腿跟着3个车轮的曲柄同步运动。
要求：
1. 螃蟹的身体始终保持在三轮车座椅正上方，骑行轨迹和花坛边缘完全重合；
2. 所有车轮的旋转方向和螃蟹的圆周骑行方向完全匹配，辅助轮不出现侧翻错位；
3. 螃蟹的每条腿都严格绑定到对应运动部件，没有肢体穿进车身、车轮的情况；
4. 整体动画时长12秒，循环播放，所有元素用SVG路径绘制，不嵌入任何位图资源。""",
        "author_name": "智谱 AI / GLM-5.3-Flash",
        "author_url": "https://zhipuai.cn",
        "repo_url": "",
        "stars_count": 4200,
        "install_command": "",
        "demo_url": "/demos/pk/crab-glm-5-3-flash.html",
        "demo_type": "iframe",
        "tags": ["模型PK", "GLM-5.3-Flash", "SVG动画", "逆运动学"],
        "target_models": ["GLM-5.3-Flash", "GLM-4"],
        "related_product_slug": None,
        "is_pinned": False,
        "sort_order": 97,
        "content_markdown": """# GLM-5.3-Flash 实测分析：轻巧优雅的纯矢量运动学实现

GLM-5.3-Flash 在面对“螃蟹骑三轮车”的高难度空间物理要求时，采取了极高技术审美与实用主义结合的策略：

## 核心实现亮点

1. **齿比与 12 秒严格整数闭环**：
   - 花坛轨迹半径 $R=192$
   - 前轮半径 $r=48$（单圈正好自转 4 周）
   - 后轮半径 $r=32$（单圈正好自转 6 周）
   - 辅助轮半径 $r=24$（单圈正好自转 8 周）
   所有车轮在 12 秒周期结束时均恰好完成整数周自转，首尾状态毫厘不差，彻底规避了跳帧问题。
2. **轻量双骨骼 IK（Inverse Kinematics）**：
   编写了极简高效的平面反向动力学求解器，足端实时锁定曲柄销，膝关节自动向上拱起，杜绝肢体穿入车架。
3. **确定性伪随机数与微风环境动效**：
   内置 `s=(s*16807)%2147483647` 算法，在不增加运行时负担的前提下，生成了 64 丛随机花草，辅以 CSS Keyframes 呼吸摇曳。
4. **代码极其精练**：
   仅 542 行代码（27.8 KB），加载迅速、渲染零卡顿，是轻量化自包含 SVG 动画的典范。
""",
    },
    {
        "slug": "crab-tricycle-gemini-38-flash-medium",
        "kind": "pk",
        "title": "Gemini 3.8 Flash (Medium) 实测：螃蟹骑三轮车 3D 动力学与音效工程狂魔",
        "subtitle": "1652行真3D轴测投影、阿克曼转向角、Web Audio合成车铃音效与独立SVG导出",
        "summary": "由 Gemini 3.8 Flash (Medium) 制作的超高规格极客级交互应用。手写完整 3D 轴测投影引擎与视角自由拖拽旋转，根据转弯半径实时解算阿克曼转向角，内置 Web Audio 纯代码合成双音车铃与脚踏声，8足动力学铰接外加墨镜大螯，并提供独立 SVG 序列化导出。",
        "prompt_template": """生成一个完全自包含的SVG动画，内容是一只螃蟹骑着带辅助轮的儿童三轮车，沿着圆形的花坛边缘做圆周骑行，同时螃蟹的8条腿里，有2条腿控制车把转向，剩下6条腿跟着3个车轮的曲柄同步运动。
要求：
1. 螃蟹的身体始终保持在三轮车座椅正上方，骑行轨迹和花坛边缘完全重合；
2. 所有车轮的旋转方向和螃蟹的圆周骑行方向完全匹配，辅助轮不出现侧翻错位；
3. 螃蟹的每条腿都严格绑定到对应运动部件，没有肢体穿进车身、车轮的情况；
4. 整体动画时长12秒，循环播放，所有元素用SVG路径绘制，不嵌入任何位图资源。""",
        "author_name": "Google DeepMind / Gemini 3.8 Flash",
        "author_url": "https://deepmind.google",
        "repo_url": "",
        "stars_count": 5600,
        "install_command": "",
        "demo_url": "/demos/pk/crab-gemini-38-flash-medium.html",
        "demo_type": "iframe",
        "tags": ["模型PK", "Gemini 3.8 Flash", "3D投影", "WebAudio"],
        "target_models": ["Gemini 3.8 Flash", "Gemini 2.5"],
        "related_product_slug": "gemini-advanced",
        "is_pinned": False,
        "sort_order": 96,
        "content_markdown": """# Gemini 3.8 Flash (Medium) 实测分析：工程堆料与 3D 动力学的极致展现

Google 的 Gemini 3.8 Flash 在开启中等思考（Thinking Medium）后，展现出了惊人的代码吞吐与全功能工程建模能力：

## 核心实现亮点

1. **手写 3D 轴测投影系统**：
   建立完整的 X, Y, Z 三维世界坐标系，实时计算 Azimuth（方位角）与 Elevation（仰角）变换，并支持在画布上使用鼠标左键 360° 自由旋转视角。
2. **阿克曼几何转向学推演**：
   严格根据轴距（Wheelbase）和回转半径解算阿克曼转向角：`steerAngle = Math.atan2(CONFIG.wheelbase, CONFIG.trackRadius)`，前轮不仅自转，车把更随偏航角精准切入圆周内侧。
3. **Web Audio 纯代码物理音效合成**：
   没有任何外部音频资源，通过原生 `AudioContext` 创建 Oscillator 节点，合成了：
   - 1480Hz / 2220Hz / 2960Hz 三阶清脆双音童车铃声；
   - 三角波周期性脚踏机械咔哒声。
4. **生物学解剖与极客趣味**：
   将 8 条步行足全部精确绑定至转向车把与前后轮双曲柄，同时为螃蟹额外设计了佩戴墨镜向观众致意的一对大螯（Chelae）。
5. **内建独立 SVG 导出引擎**：
   一键将当前整个运行引擎序列化打包，支持直接下载可独立双击运行的 `.svg` 动效文件。
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
        "target_models": ["GPT-6 Astra", "Claude 4.5 Sonnet", "Codex++"],
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
        "slug": "jev-1-13-system-one-model",
        "kind": "article",
        "title": "Jev 1.13 是什么？这个不会聊天的 AI，可能正在改变大模型的使用方式",
        "subtitle": "专为软件调用设计的“系统一模型”：不要文本，只要判断，输入 $0.042/1M，输出 0 元",
        "summary": "TypeSafe AI 正式发布 Jev 1.13，开创“System One Model”新物种。它不生成长篇文本，专注于结构化选择、评分与概率判断。端到端响应 70~500ms，输入每百万 Token 仅 0.042 美元。实测 1 秒内将百万 Token 上下文压缩至 8.6 万，正在重塑大模型分工架构。",
        "prompt_template": "",
        "author_name": "AI Price Radar 深度观察",
        "author_url": "https://ai.pricememo.cn",
        "repo_url": "https://typesafe.ai/blog/introducing-system-one-models-and-jev",
        "stars_count": 3800,
        "install_command": "",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["Jev 1.13", "System 1", "推理降本", "Model Routing", "Agent 架构", "前沿模型"],
        "target_models": ["Jev 1.13", "Claude 3.7", "DeepSeek V4", "GPT-6 Astra", "All Models"],
        "related_product_slug": "claude-pro",
        "is_pinned": True,
        "sort_order": 98,
        "content_markdown": """# Jev 1.13 是什么？这个不会聊天的 AI，可能正在改变大模型的使用方式

最近几天，如果你关注 X 上的 AI 开发者圈，可能会频繁看到一个新名字：**Jev**。

它在 2026 年 9 月 15 日由 TypeSafe AI 正式发布。有意思的是，Jev 和我们熟悉的 ChatGPT、Claude、Gemini、DeepSeek 完全不是同一种思路。

它不会陪你聊天，不会帮你写文章，不会生成一大段分析。甚至可以说——**Jev 几乎不负责“说话”，它只负责“做判断”。**

---

## 一、发生了什么：机器原生智能与“系统一模型”

TypeSafe AI 将这种模型称为 **System One Model（系统一模型）**。官方将其定位成一种专门供软件调用的“机器原生智能”：输入一段状态或数据，再提出结构化问题，模型直接返回选择、评分、概率以及置信度，而不是生成一段自然语言。([TypeSafe AI 官方博客](https://typesafe.ai/blog/introducing-system-one-models-and-jev))

截至 2026 年 9 月 21 日，公开资料中可见的版本为 `Jev 1.13 / jev-1.13.0`，`jev-latest` 等别名目前也均指向这一版本。([Jev Changelog](https://jevaiguide.com/jev-changelog/))

### Jev 和 ChatGPT 最大的区别是什么？

传统大语言模型（LLM）的工作方式大致是：
```
输入 Prompt → 模型逐字推理 → 一个 Token 一个 Token 地生成文字 → 程序从文字里用正则解析答案
```

比如一个客服系统想知道：*这封邮件应该交给哪个部门？*
普通 LLM 可能回答：
> “根据用户描述，我认为这封邮件主要涉及退款问题，因此建议将其转交给账单或退款团队……”

但是下游程序真正需要的其实只有两个字：`Refund`。剩下的文字不仅浪费网络带宽与解析时间，本质上**全都是白花花的 Token 成本**。

Jev 则从一开始就把这个问题重构为底层结构：
- **Choice**：从提前定义好的选项列表（`Billing` / `Technical` / `Refund` / `Sales`）中直接做单选或多选；
- **Score**：按照预设规则或梯度进行精准评分；
- **Noul**：快速判断一个逻辑命题成立的置信概率。

也就是说，它更像一个**拥有 AI 判断能力的 `if / else` 分支网关**，而不是聊天机器人。

---

## 二、为什么值得关注：极速响应、极致低价与上下文压缩神话

### 1. 价格直降与毫秒级延迟
最直观的原因就是：**快，而且极其便宜**。
- **输入价格**：每 100 万输入 Token 仅需 **0.042 美元**；
- **输出价格**：因为它根本不生成传统意义上的长篇文本输出，官方将输出 Token 直接标为 **0 美元（免费）**；
- **响应速度**：官方公布的典型端到端延迟仅为 **70～500ms**。在特定 System One 工作流中，相比动辄 2~5 秒的通用前沿大模型存在数量级层面的速度优势。([TypeSafe 官方性能说明](https://typesafe.ai/blog/introducing-system-one-models-and-jev))

在生态集成上，Jev 上线后在 Vercel AI Gateway 的早期采用速度创下纪录：Vercel 披露其上线 24 小时后即覆盖了接近 13% 的付费团队，是该 Gateway 当时采用速度最快的一次模型发布。([Vercel 官方技术报告](https://vercel.com/blog/ai-gateway-jev-model-launch))

### 2. X 上的爆火案例：Claude Code 百万 Token 秒级裁剪
真正引爆开发者圈的，是社区迅速挖掘出的高价值落地场景。

例如开发者 Tamara Tran 制作了一个针对 Claude Code 的上下文压缩插件。传统做法通常是让另一个大型 LLM 阅读几十万字历史聊天记录重新做一次 Summary，又慢又贵。

而她换了全新思路：**让 Jev 逐条判断历史上的每一个 Tool Call（工具调用）——“这条信息在后续任务中到底还有没有价值？”**
- 有价值就保留；
- 无价值就直接剔除。

随后知名开发者 Alex Volkov 在 X 上公开实测：一个接近 **100 万 Token** 的超长 Claude 会话，被 Jev 在大约 **1 秒** 内精准裁切到了约 **8.6 万 Token**！([Jev Claude 实验报告](https://jevmodel.ai/models/jev-claude/))

这个案例生动印证了 Jev 的杀手级定位：**不要让它生成内容，让它专门判断内容。**

---

## 三、对普通用户与开发者的实际价值：分层漏斗与双引擎架构

Jev 会消灭或取代传统大语言模型吗？短期内恰恰相反。

**Jev 最有价值的姿态不是“取代”，而是与 GPT、Claude、Gemini、DeepSeek 组成“黄金搭档”。**

### 1. 前置意图路由（Model Routing）
```
用户请求
  ↓
Jev 极速判定任务类型与安全等级
  ↓
├── 简单文本/日常分类 → 交付 Mini / Flash 等超低价模型
├── 代码编写/工程重构 → 交付 Coding 专用模型
├── 复杂数理逻辑推理 → 交付 SOTA 强推理模型
└── 不确定 / 高危异常 → 升级人工审核
```

### 2. 后置质量护栏与二次重试
```
大模型生成候选答案
  ↓
Jev 校验输出是否命中规范要求
  ↓
├── 置信度足够高（≥95%） → 立即返回给用户
└── 置信度低（<95%）     → 触发重试或升级到顶配专家模型
```

### 3. 实战范本：Hassan 的邮件欺诈检测
开发者 Hassan 做过一次非常经典的公开实验：先由 Jev 对 100 封邮件做第一道前置筛查，仅将其判定置信度低于 95% 的 31 封邮件升级交给 Kimi K3 深度攻坚。

最终整个组合流程判断正确率高达 **96/100**，而全流程消耗的推理成本仅仅约 **0.07 美元**！([Made with Jev 评测](https://madewithjev.com/builds/fraud-detection-jev-kimi))

这种**“小而快的模型消化 70% 常规流量，强而贵的大模型专啃 30% 硬骨头”**的架构，直接重写了 AI 商业软件的成本模型。

---

## 四、我怎么看（AI 价格雷达观点）

过去两年，AI 行业的主流叙事始终困在“单点崇拜”里：
*“哪个模型更聪明？是 GPT、Claude、Gemini 还是 DeepSeek？”*

但随着真实业务流量爆发，所有工程师都在被昂贵的 API 账单和卡顿的 TTFT（首字延迟）上课。Jev 带来的深层启示在于：

> **真正的工业级 AI 应用，绝不应该只有一个“全能超级大脑”，而应该是一支精密配合的“特种舰队”。**

- Jev 负责第一道防线的判断、分类与路由；
- Claude / GPT / Gemini 负责攻坚高维度深度推理；
- 搜索模型负责检索实时情报；
- 视觉与多模态模型负责图像视听；
- 宿主程序负责将这些智能组件紧密粘合。

它真正挑战的不是某一家具体的大模型厂商，而是过去几年整个行业养成的懒惰惯性：**“遇到任何问题，都无脑调一个更大的 LLM”。**

对于关注 AI 成本架构与比价的开发者来说，Jev 1.13 是一个强烈的信号：**AI 软件工程的降本增效，正在从 Prompt 技巧层面，全面跃迁至模型编排架构层面。**
""",
    },
    {
        "slug": "multi-model-workflow-routing-2026",
        "kind": "article",
        "title": "别再让最贵的大模型干所有事情：2026 年 AI 工作流正在转向“多模型分工”",
        "subtitle": "从 Prompt Engineering 到 Model Routing：用“四层漏斗架构”砍掉 90% 的生产环境推理成本",
        "summary": "从盲目调用 SOTA 模型到建立多模型协作团队。结合 Hassan 邮件风控与 1018 篇论文分类实验，详解 Jev + DeepSeek / Kimi / Claude 混合流水线设计。手把手搭建“快速粗筛 → 主力生成 → 强推理攻坚 → 严格验证”的高性价比架构。",
        "prompt_template": "",
        "author_name": "AI Price Radar 实战指南",
        "author_url": "https://ai.pricememo.cn",
        "repo_url": "https://madewithjev.com/builds/fraud-detection-jev-kimi",
        "stars_count": 4500,
        "install_command": "",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["Model Routing", "成本优化", "Claude Code", "Agent 工作流", "省 Token", "架构实践"],
        "target_models": ["Jev 1.13", "DeepSeek V4", "Claude 3.7", "Kimi K3", "All Models"],
        "related_product_slug": "openai-api-credit",
        "is_pinned": True,
        "sort_order": 96,
        "content_markdown": """# 别再让最贵的大模型干所有事情：2026 年 AI 工作流正在转向“多模型分工”

很多开发者与企业当前使用 AI 的方式依然停留在粗放期：
找到市面上名气最大、参数最强的大模型，然后把业务链条里的所有事情全塞给它。

- 写代码？调顶配大模型。
- 分类一封客服邮件？调顶配大模型。
- 判断一段文本是否相关？继续调顶配大模型。
- 压缩几十万 Token 上下文？还是调顶配大模型。

这种做法在做实验室 Demo 时自然最省心。但随着 AI 产品真正接入成千上万的真实用户，一个残酷的现实浮出水面：**绝大多数生产任务，根本不需要顶配模型。**

---

## 一、发生了什么：单一模型依赖的成本墙与多模型协作浪潮

在 2026 年的 AI 开发者社区（特别是 X 与 Hacker News），关于多模型协同架构（Multi-Model Workflow & Routing）的讨论热度已全面超越了单纯的模型评测。

业界开始意识到：把所有工作全扔给顶配 SOTA 模型，不仅会导致 API 账单每月暴涨数百倍，更会引入严重的延迟瓶颈。伴随着类似 **Jev 1.13**（专注毫秒级结构化决策）、**DeepSeek V4 Flash**（极速高吞吐与大幅 KV 压缩）等专精模型的涌现，生产级 AI 架构正在全面转向“多模型分工”。

---

## 二、为什么值得关注：三个真实硬核实验的数据对照

### 案例 1：Hassan 的邮件风控分层流水线
开发者 Hassan 曾公布了一组对比测试：准备了 50 封正常业务邮件与 50 封欺诈诱捕邮件。
- **第一步（极速初筛）**：先让低成本决策模型 Jev 进行首轮研判。100 封邮件仅耗时约 1.42 秒；
- **第二步（置信度熔断与升级）**：设立置信度分流阈值——凡是判定置信度低于 95% 的个案，才无缝升级交给深度推理模型 Kimi K3 攻坚（最终仅 31 封触发升级）；
- **测试结果**：综合准确率高达 **96/100**，而全流程 100 次调用的总推理费用仅仅约 **0.07 美元**！([Made with Jev 实验记录](https://madewithjev.com/builds/fraud-detection-jev-kimi))

### 案例 2：1,018 篇学术论文分类流水线
在另一个处理 1,018 篇前沿 AI 论文的实验中，作者放弃了“用一个 LLM 从头读到尾并分类”的思路，而是将工作拆解：
- **第一棒（阅读与提炼）**：由 DeepSeek V4 Flash 通读论文并生成核心要点摘要（累计成本约 3.99 美元）；
- **第二棒（标签归类与路由）**：将“论文标题 + 摘要 + 24 个候选研究领域”送入 Jev，仅要求其做出纯粹的分类判断。
- **实测数据**：Jev 模块完成全部 1,018 篇分类的总成本仅为 **0.08 美元**，单篇中位端到端延迟低至 **256ms**。([Nutlope 实验分享](https://twiscan.com/en/x/nutlope))

### 案例 3：Claude Code 百万 Token 的精准剪枝
在深度工程编码场景下，长时间工作的 Coding Agent 会产生海量的终端日志、搜索中间态与报错堆栈。如果不加节制地塞入上下文，不仅每轮对话都在疯狂烧钱，更会导致注意力分散与指令漂移。
- 传统手段是调用大模型做全文递归总结，耗时且容易丢失关键细节；
- 新兴方案 `fast-jev-compaction` 则让轻量决策模型逐条研判每一个 Tool Call：“这条历史记录后续还有没有用？”没用就立刻剥离。
- 实测将一个接近 **100 万 Token** 的长任务会话在 1 秒内精简至 **8.6 万 Token**，大幅降低后续多轮推理的支出。([Jev Claude 实测数据](https://jevmodel.ai/models/jev-claude/))

---

## 三、对普通用户与开发者的实际价值：生产级“四层漏斗架构”

与其把时间耗费在写几十行花里胡哨的“提示词魔法”上，不如在系统架构层设计清晰的分工漏斗。推荐一套在生产环境中被广泛验证的四层结构：

| 层级 | 定位与核心职责 | 推荐模型类型 | 成本 / 延迟特征 |
| :--- | :--- | :--- | :--- |
| **第一层：快速门禁与初筛** | 用户意图识别、内容风控拦截、任务分流路由、上下文高频剪枝 | Jev 1.13、GPT-4o mini、Claude 3.5 Haiku | 毫秒级（70-300ms），成本近乎可忽略（$0.04/1M） |
| **第二层：主力执行单元** | 日常功能编写、文章润色、常规业务问答、摘要提取 | DeepSeek V4 Flash、Claude 3.7 Sonnet、GPT-4o | 秒级响应，平衡能力与经济性 |
| **第三层：专家攻坚核心** | 复杂算法推演、多文件深层架构重构、疑难 Bug 根因定位 | o3-mini (High)、GPT-6 Astra、Claude 3.7 (Extended Thinking) | 耗时较长（5-30s），单次调用成本高，仅承接约 10% 难关 |
| **第四层：自动化验证闭环** | 单元测试运行、Schema 格式对齐、安全漏洞扫雷、事实一致性比对 | 本地代码测试套件 + 规则引擎 + 判别模型 | 确定性强，保证流水线最终交付质量 |

### 生产流水线运作范式
```
用户请求
  ↓
[第一层] 快速初筛 → (命中敏感/非相关？直接拦截并返回)
  ↓
[第一层] 意图分流
  ├── 常规业务需求 → [第二层] 主力模型执行
  └── 复杂疑难任务 → [第三层] 强推理模型攻坚
  ↓
[第四层] 自动化测试与规则验证
  ├── 验证通过 → 格式化交付用户
  └── 验证失败 → 携带精细报错日志，回流至第二/三层单点修正
```

---

## 四、我怎么看（AI 价格雷达观点）

过去两年，我们讨论 AI 技巧时，最常听到的词汇是 **Prompt Engineering（提示词工程）**：
*怎样加上“你是一个资深专家”？怎样要求它分步骤思考？*

但当 AI 应用进入企业交付与真实账单结算时，核心驱动力已经快速转向：
**Context Engineering（上下文治理）+ Workflow Engineering（工作流工程）+ Model Routing（智能模型路由）。**

我们不会在一家公司里让年薪百万的首席科学家去负责前台收发快递和垃圾邮件清理。同样的逻辑在 AI 系统中完全成立：

> **从今天起，衡量一个 AI 工程师水准的标志，不再是他是否熟记所有的 Prompt 咒语；而是他能否在正确的时间点，将正确的子任务派发给性价比最合适的模型。**

以后在选择模型或评估 API 预算时，请把第一问从*“哪个模型最聪明”*改成：
**“我这个具体的业务步骤，真的有必要叫最贵的模型吗？”**
""",
    },
    {
        "slug": "glm-5-3-infra-agent-recursive-self-improvement",
        "kind": "article",
        "title": "GLM-5.3 开始帮自己造基础设施：AI 的“递归自我改进”真的开始了吗？",
        "subtitle": "超 10 万卡国产集群 2 周吞吐翻 3 倍背后：为什么说细粒度工程反馈远比单独模型能力更重要",
        "summary": "深度拆解 Z.ai 披露的 GLM-5.3-Flash 推理基础设施建设内幕。10 万卡集群、1M 上下文与复杂 Kernel 调优，Infra Agent 如何与人类工程师协作？理性辨析“递归自我改进（RSI）”真相，提炼对日常 Claude Code / Codex 开发者的反馈闭环指导。",
        "prompt_template": "",
        "author_name": "AI Price Radar 深度观察",
        "author_url": "https://ai.pricememo.cn",
        "repo_url": "https://z.ai/blog/glm-built-its-inference-infrastructure",
        "stars_count": 3100,
        "install_command": "",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["GLM-5.3", "Infra Agent", "递归自我改进", "反馈闭环", "AI 前沿", "系统工程"],
        "target_models": ["GLM-5.3", "Codex++", "Claude Code", "All Models"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": False,
        "sort_order": 94,
        "content_markdown": """# GLM-5.3 开始帮自己造基础设施：AI 的“递归自我改进”真的开始了吗？

“让 AI 帮写几行前端业务代码”在今天早已屡见不鲜。
但如果一个 AI 开始深度参与建设**运行下一代 AI 自己的万卡推理基础设施**呢？

2026 年 9 月 17 日，智谱技术团队（Z.ai）正式发布了一篇引发系统工程界热议的技术长文：
*《Toward Recursive Self-Improvement: How GLM Built Its Own Inference Infrastructure》*。

文中披露，在 GLM-5.3-Flash 的生产环境部署过程中，一个由 GLM-5.3 驱动的 **Infra Agent** 深度参与了整套推理底层系统的建设与性能榨取。([Z.ai 官方技术报告](https://z.ai/blog/glm-built-its-inference-infrastructure))

乍听之下，许多人可能会产生科幻式的联想：*“AI 已经开始自己造自己、实现奇点闭环了吗？”*
答案是：**目前还没有那么神化。但剥离掉宣传修辞后，它所展示的技术演进路径，比单纯的噱头重要得多。**

---

## 一、发生了什么：超 10 万卡集群与 2 周 3 倍的吞吐飞跃

根据 Z.ai 公布的信息，GLM-5.3-Flash 的生产推理集群由**超过 100,000 颗中国自主可控 AI 加速芯片**互联而成。

这绝非把现成开源框架复制粘贴过去那么简单。面对全新的模型拓扑结构、1M 超长上下文、原生多模态混合流量，团队必须跨越一系列严苛的硬核工程壁垒：
- 自定义算子 Kernel 缺失或效率低下；
- 显存带宽墙与芯片间跨卡通信瓶颈；
- 动态 Tensor Parallelism（张量并行）与 Pipeline 并行切分策略选择；
- 缓存精度量化（W8A8 量化、混合精度 KV Cache）下的数值稳定性。

原本这些属于典型高精尖系统架构师的调优范畴。而 Z.ai 披露，其中的代码审查、底层 Kernel 优化、性能 Profiling 和大规模切分实验，大量由 GLM-5.3 驱动的 Infra Agent 协同人类工程师并行推进。

### 落地成效
- **两周投产**：从底层硬件完成适配，到系统承接全量真实生产流量，耗时不到两周；
- **吞吐翻倍**：端到端推理吞吐量相比首版未调优状态提升了整整 **3 倍**；
- **核心优化落地**：覆盖了 ReplaySSM、Layer Split、Encode-Prefill-Decode 物理架构分离等前沿工程实践。([Z.ai 官方博客](https://z.ai/blog/glm-built-its-inference-infrastructure))

---

## 二、为什么值得关注：理性辨析“递归自我改进（RSI）”

所谓 **Recursive Self-Improvement（递归自我改进，简称 RSI）**，在经典计算机科学假设中通常指的是：
```
AI 写出更优的训练/系统代码 → 产出更强的下一代 AI → 下一代 AI 进一步优化底层系统 → 产生指数级迭代循环
```

如果这个闭环完全脱离人类干预自主加速旋转，那就是理论上的“技术奇点”。

但 Z.ai 在报告中非常实事求是地澄清：**当前状态绝不是无人看管的自主进化**。
- **人类掌控边界**：顶层性能目标、安全边界红线、验收测试集以及关键系统级变更的审核权，依然牢牢掌握在资深人类工程师手中；
- **真实定位**：更严谨的定义是 **“高自动化水平的 AI 辅助 AI 研发（AI-Assisted AI R&D）”**。

这件事情真正震撼业界的地方，不在于模型会不会写某个 CUDA 或专用加速器 Kernel，而在于：**AI 已经正式从“编写单体应用”迈进了“参与塑造自身算力基石”的深层正反馈阶段。**

---

## 三、对普通用户与开发者的实际价值：反馈（Feedback）远比聪明重要

Z.ai 在工程复盘中分享了一个极其关键但常被忽视的洞见：

> **“仅仅给 Agent 塞进更多代码库，并不能让它成为优秀的系统工程师。决定 Agent 产出上限的，是系统回传给它的反馈质量。”**

很多开发者在日常使用 Claude Code、Codex 或 Cursor 时，往往陷入这样的无效对话：
> 开发者：“帮我把这个复杂系统性能优化一下。”
> AI 改完代码。
> 开发者：“感觉还是慢，而且好像报错了，你再改改。”

这种模糊至极的负反馈对于模型毫无价值。模型根本无从得知：
- 是延迟崩了，还是吞吐崩了？
- 是第几层出现了通信阻塞，还是显存被 OOM 撑爆？
- 是数值溢出精度偏差，还是锁竞争导致死锁？

Z.ai 团队让 Infra Agent 发生质变的做法，是在外围搭建了一套**高精度的自动化工程反馈闭环**：
```
Agent 提交优化 Patch
  ↓
自动沙箱部署运行
  ↓
多维度高敏观测（精确到纳秒的 Profiling、数值精度矩阵比对、局部回归测试、A/B 基准打分）
  ↓
生成结构化错误诊断切片与调用栈追踪
  ↓
精准喂回给 Agent：“第 4 层注意力权重差异超 0.003，GEMM 耗时异常增加 12%”
  ↓
Agent 依据确定性事实做出精准二次收敛
```

### 给日常开发者的避坑指导
无论你是使用 AI 编写 Python 后端、优化 SQL 查询还是构建 Next.js 前端，请记住这个黄金铁律：

1. **别再让 AI 猜谜**：不要用空洞的“好像有问题”去要求重新生成；
2. **构建本地验证流水线**：为每次修改配置单测、基准脚本（Benchmark）或类型检查；
3. **精准投喂错误信息**：把编译器的确切 Traceback、测试失败日志或 Profiler 输出原封不动丢给 AI；
4. **让 AI 拥有自我纠错的闭环系统**：一个能自动运行 `test -> fix -> verify` 循环的普通模型，表现会彻底碾压一个没有测试反馈的顶配模型。

---

## 四、我怎么看（AI 价格雷达观点）

过去一年，整个行业陷入了疯狂的参数与榜单内卷：
*比谁的上下文更长，比谁在离线基准测试上又高了 0.5 分。*

但 GLM-5.3 这个案例向我们昭示了下半场竞争的核心分水岭：
> **单体模型的“裸智商”终将遭遇收益递减，而“模型 + 运行环境 + 自动化反馈循环”构建的工程闭环，才是工业级生产力的决定性护城河。**

一个没有工程反馈机制的 SOTA 模型，就像一个蒙着眼睛在黑夜里狂奔的顶尖短跑运动员；
而一个拥有严密测试套件、精细日志切片与自愈重试流水线驱动的系统，哪怕使用低成本模型，也能持续、稳定地产出坚如磐石的系统代码。

对于广大追求效费比的开发者与企业而言：**别再沉迷于等待下一个“完美模型”，抓紧为你的 Agent 打造健全的测试与反馈流水线，才是当下最确定、回报率最高的投资。**
""",
    },
    {
        "slug": "codex-context-management-experimental-mode",
        "kind": "article",
        "title": "Codex 隐藏实验性上下文管理开启指南：告别暴力压缩，省 Token 提表现",
        "subtitle": "配置 [features.context_management] experimental_mode = true，解锁笔记持久化与长会话防遗忘",
        "summary": "2026年9月社区核心爆料：在 ~/.codex/config.toml 中启用实验性上下文管理，用“跨窗口笔记+语义检索模式”取代旧版暴力 Compaction 压缩。大幅节省 Token 消耗，显著提升长任务连贯性与代码行级记忆力！",
        "prompt_template": "",
        "author_name": "songkeys / 蚁工厂",
        "author_url": "https://x.com/songkeys",
        "repo_url": "https://x.com/songkeys",
        "stars_count": 2700,
        "install_command": "[features.context_management]\nexperimental_mode = true",
        "demo_url": "",
        "demo_type": "none",
        "tags": ["Codex", "GPT-6 Astra", "配置技巧", "上下文优化", "省Token", "长会话"],
        "target_models": ["GPT-6 Astra", "GPT-5.6", "Codex++", "All Models"],
        "related_product_slug": "chatgpt-plus",
        "is_pinned": True,
        "sort_order": 92,
        "content_markdown": """# Codex 隐藏上下文管理秘籍：告别暴力压缩

2026 年 9 月初，海外知名 AI 架构师 @songkeys 在 X（Twitter）爆料了一项 OpenAI Codex 官方正在灰度测试的核心参数，国内技术博主“蚁工厂”等随后实测确认。这项配置预计将在未来几周内成为 GPT-6 Astra 的官方默认行为。

---

## 传统 Compaction 压缩 vs 实验性 Context Management

在日常长时间使用 Codex（尤其是大工程重构、多文件联调或深度排错）时，长上下文往往会遇到瓶颈：

### 1. 传统模式（默认 Compaction）
- **机制**：当上下文达到临界值时，强制进行单次大段文本压缩摘要（Compaction）。
- **痛点**：容易丢失早期重要的需求细节、代码精准行号和技术约束边界；后续对话一旦引用旧上下文容易出现“降智”或幻觉，且每次总结都会产生额外的 Token 开销。

### 2. 实验性模式（`experimental_mode = true`）
- **机制**：开启**跨窗口笔记（Notes）+ 历史上下文语义搜索（Searchable History）+ `new_context` 工具**。
- **优势**：
  - **按需索取**：模型在长任务中会自动沉淀重要事实到工作区笔记中，并在需要时像人类工程师一样主动检索历史，而非死板地背诵一段压缩总结；
  - **大幅省 Token**：减少无谓的大段重述，有效降低每次 Prompt 吞吐成本；
  - **多模型普适**：不仅适用于 **GPT-6 Astra**，配合 **GPT-5.6**、**Codex++** 等其他接入 Codex 的主力模型同样表现出色。

---

## 如何开启？

### 第一步：定位配置文件
- **macOS / Linux**：`~/.codex/config.toml`
- **Windows**：`C:\\Users\\<用户名>\\.codex\\config.toml`

### 第二步：添加配置项
使用文本编辑器打开 `config.toml`，在文件末尾追加以下配置（注意缩进与段落区分）：

```toml
[features.context_management]
experimental_mode = true
```

### 第三步：重启 Codex 使其生效
保存文件后，完全退出并重新启动 Codex 客户端或新开一个全新的任务会话即可无缝生效。

> **小贴士**：该特性适用于由 ChatGPT Plus / Pro 授权驱动的官方 Codex 运行环境。如遇偶发异常，只需将 `experimental_mode` 改为 `false` 或删除该小节即可无损恢复默认行为。
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
        "target_models": ["Claude 4.5 Sonnet", "Cursor", "Codex++", "GPT-6 Astra"],
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
        "target_models": ["GPT-6 Astra", "GPT-5.6", "Claude 4.5 Sonnet", "Cursor"],
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
        "target_models": ["Cursor", "Windsurf", "Claude 4.5 Sonnet", "GPT-6 Astra"],
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
        "target_models": ["Codex++", "Claude Code", "Cursor", "Antigravity"],
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
        "target_models": ["Claude 4.5 Sonnet", "GPT-6 Astra", "DeepSeek V3", "Cursor"],
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
        "target_models": ["Codex++", "Claude Code", "Antigravity"],
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
        "target_models": ["Claude 4.5 Sonnet", "o3", "o1", "GPT-6 Astra"],
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
        "target_models": ["Claude 4.5 Sonnet", "Codex++", "Cursor"],
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
        "target_models": ["All Models", "Claude 4.5", "GPT-6 Astra / GPT-5.6"],
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

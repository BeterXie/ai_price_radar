import type {
  GuideWalkthrough,
  GuideWalkthroughStep,
  WorkflowGuide,
  WorkflowVariant,
  WorkflowVariantId,
} from "@/lib/guides/types";
import { LAST_REVIEWED_AT, OFFICIAL_SOURCES, PROJECT_SOURCES } from "./sources";

const THIRD_PARTY_NOTICE =
  "Cockpit Tools、Sub2API、CC Switch 和 Codex++ 均为第三方项目，与 OpenAI 和 AI Price Radar 没有隶属关系。";

const CREDENTIAL_WARNING =
  "不要把完整 Cookie、Access Token、Refresh Token、API Key、恢复码或 auth.json 上传到 AI Price Radar、聊天机器人、公开仓库或陌生网站；不要上传或公开任何完整凭证。";

const LOCAL_CONVERTER_NOTE =
  "AI Price Radar 的 JSON 转换器只在浏览器本地处理文件；但下载并导入第三方工具后，凭证会由对应工具读取和保存。";

const TEAM_SEAT_WARNING =
  "工作区席位可被管理员限制或移除。不要在第三方管理的工作区、共享账号或未经授权的账号池中处理公司机密和个人敏感信息。";

const TERMS_RISK_NOTE =
  "账号池、共享、中转和第三方客户端可能受到平台条款、组织政策、地区、网络环境和风控限制。页面不得承诺稳定、永久或不会封号。";

const UI_VERSION_NOTE =
  "以你当前版本界面实际显示的 Base URL、客户端 Key、模型列表和字段名称为准，不要按本文示例端口或旧版字段硬编码。";

const CODEX_PLUS_PLUS_PROTOCOL_NOTE =
  "选择上游协议：上游原生支持 Responses API 时选择 Responses；上游只支持 Chat Completions 时选择 Chat Completions，由 Codex++ 的本地协议代理转换为 Responses。具体名称以当前 Codex++ 版本界面为准。";

function step(
  title: string,
  action: string,
  result: string,
  extra?: {
    items?: readonly string[];
    links?: readonly { label: string; url: string }[];
    trouble?: string;
  },
): GuideWalkthroughStep {
  return { title, action, result, ...extra };
}

function variant(
  id: WorkflowVariantId,
  title: string,
  description: string,
  walkthrough: GuideWalkthrough,
): WorkflowVariant {
  return { id, title, description, walkthrough };
}

export const workflowGuideEntries = [
  {
    slug: "openai-codex",
    title: "OpenAI 账号购买后如何用于 Codex",
    description:
      "先确认账号或席位已生效，再选择本地 Cockpit、服务器 Sub2API，或直接使用已交付的 Base URL 与 API Key，最后通过 CC Switch 或 Codex++ 接入 Codex。",
    flow: ["OpenAI 商品", "账号/API 服务层", "CC Switch 或 Codex++", "Codex"],
    audience: [
      "购买了 OpenAI 商品后需要真正接入 Codex 的用户",
      "需要在本地账号池、服务器账号池和直接 API 之间选择路线的用户",
      "需要同时理解 CC Switch 与 Codex++ 定位的用户",
    ],
    prerequisites: [
      "已确认账号、套餐、席位或 API 额度已经生效。",
      "已知道自己收到的是账号、JSON、Base URL 还是 API Key。",
      "已阅读 OpenAI 官方 Codex 文档，并接受第三方工具的凭证与条款风险。",
    ],
    overview: [
      {
        type: "paragraph",
        text: "Cockpit 和 Sub2API 位于上游：Cockpit 负责本地账号管理与本地 API，Sub2API 负责服务器账号池与 API 分发。CC Switch 和 Codex++ 位于用户客户端侧：CC Switch 负责供应商配置切换与本地路由，Codex++ 负责 Codex Desktop 的外部启动与中转注入。两者通常是二选一，不要求同时安装。",
      },
      {
        type: "callout",
        tone: "info",
        title: "这不是四个平行工具",
        text: "正确链路是：OpenAI 账号或凭证先进入 Cockpit（本地）或 Sub2API（服务器），形成 Base URL 与 API Key；再通过 CC Switch 或 Codex++ 把接口配置给 Codex CLI / Desktop。",
      },
      {
        type: "comparison",
        title: "推荐路线",
        columns: ["你的情况", "推荐路线"],
        rows: [
          ["单机、个人、多账号", "Cockpit"],
          ["服务器、多设备、多用户", "Sub2API"],
          ["已经收到 Base URL + Key", "API endpoint"],
          ["只使用官方账号且不需要账号池", "官方直接登录"],
          ["主要使用 Codex CLI", "优先 CC Switch"],
          ["主要使用 Codex Desktop 且需要中转注入", "优先 Codex++"],
        ],
      },
      {
        type: "steps",
        title: "接入前先确认四件事",
        items: [
          "账号套餐名称不等于必然拥有 Codex 权限，先到官方页面确认实际权限。",
          "API 额度商品和直接中转商品不需要先过 Cockpit；只有需要自己做账号池时才考虑 Sub2API。",
          "Team/K12/Business 席位可能被管理员移除，先确认组织策略和退出路径。",
          "不把 Cookie、Token 或 Key 上传给本站或聊天机器人。",
        ],
      },
      {
        type: "callout",
        tone: "danger",
        title: "凭证边界",
        text: CREDENTIAL_WARNING,
      },
    ],
    variants: [
      variant(
        "cc-switch",
        "个人本地路线：Cockpit 或直接 API → CC Switch → Codex",
        "适合个人电脑、多账号或已有 Base URL + Key 的用户。CC Switch 只保存客户端供应商配置，不代替上游账号池。",
        {
          title: "通过 CC Switch 接入 Codex",
          intro: "先确认商品生效，再选择 Cockpit 或直接 API 作为上游，最后用 CC Switch 配置供应商。",
          steps: [
            step(
              "确认商品已经生效",
              "在 OpenAI 官方页面核对账号、套餐、席位或 API 额度状态；不要只凭商品标题判断。",
              "你已确认哪个账号或哪份额度可以使用。",
              { trouble: "仍显示未生效时先联系原商家处理，不要继续配置第三方客户端。" },
            ),
            step(
              "选择上游并取得 Base URL 与 Key",
              "个人电脑和多账号选择 Cockpit 本地账号池；已收到 Base URL + Key 的用户直接使用。",
              "你有一组可用的 Base URL 与对应 Key，且知道协议和模型名。",
            ),
            step(
              "从官方 Release 安装 CC Switch",
              "只从 farion1231/cc-switch 的 GitHub Releases 页面下载，不要使用陌生网盘或同名收费站点。",
              "CC Switch 安装完成，版本来源可追溯。",
              {
                links: [{ label: "CC Switch 官方仓库", url: "https://github.com/farion1231/cc-switch" }],
              },
            ),
            step(
              "添加自定义供应商",
              "打开 Codex 面板，添加自定义供应商，填入上游 Base URL 与客户端 Key；协议按上游当前接口选择，Codex 通常使用 Responses，模型名优先读取 /v1/models 或上游模型列表。",
              "供应商配置保存成功，Key 只填在客户端本机。",
              { trouble: "不确定字段名称时，以当前 CC Switch 版本界面显示为准。" },
            ),
            step(
              "启用供应商并重启 Codex",
              "启用该供应商后重启 Codex CLI / Desktop，使配置和模型目录重新加载。",
              "Codex 使用新供应商启动，没有继续走旧配置。",
            ),
            step(
              "执行最小测试并可切回官方",
              "发送一个最小请求，确认上游日志或用量出现记录；同时确认如何切回 OpenAI Official。",
              "最小请求成功，且你知道随时切回官方线路。",
            ),
          ],
        },
      ),
      variant(
        "codex-plusplus",
        "Cockpit、Sub2API 或直接 API → Codex++ → Codex Desktop",
        "适合个人本地账号池、服务器账号池或直接 API 用户，需要 Codex Desktop 中转注入时使用。必须通过 Codex++ 启动入口启动 Codex，注入配置才会生效。",
        {
          title: "通过 Codex++ 接入 Codex Desktop",
          intro: "Codex++ 固定指 BigPizzaV3/CodexPlusPlus。先安装官方 Codex Desktop，再安装 Codex++，最后填写中转注入。",
          steps: [
            step(
              "确认商品已经生效",
              "在 OpenAI 官方页面核对账号、套餐、席位或 API 额度状态。",
              "你已确认上游可以正常使用。",
            ),
            step(
              "选择上游并取得 Base URL 与用户 Key",
              "个人电脑可以使用 Cockpit 本地 API 服务，服务器场景使用 Sub2API 的 HTTPS Base URL 与下游用户 Key；已有直接交付的 Base URL + Key 则直接使用。",
              "你有一组可用的 Base URL 与 Key，且知道协议和模型名。",
            ),
            step(
              "安装官方 Codex Desktop",
              "先从 OpenAI 官方渠道安装 Codex Desktop，再安装 Codex++ 对应系统版本。",
              "官方 Codex Desktop 与 Codex++ 都已安装。",
            ),
            step(
              "打开 Codex++ Manager 配置中转注入",
              "进入中转注入或供应商配置，填写 Base URL 与客户端 Key，然后选择上游协议并应用配置。",
              "配置已保存，但还没有启动 Codex。",
              {
                items: [CODEX_PLUS_PLUS_PROTOCOL_NOTE],
                trouble: "字段名称随版本变化时，以 Codex++ Manager 当前界面为准。",
              },
            ),
            step(
              "退出旧 Codex 并通过 Codex++ 启动",
              "退出已经运行的 Codex，必须从 Codex++ 启动入口重新启动，不能继续用普通桌面快捷方式。",
              "Codex 通过 Codex++ 启动，注入配置生效。",
            ),
            step(
              "执行最小请求并准备回滚",
              "发送最小请求确认上游日志出现记录；之后按版本说明清除 API 模式或中转注入，恢复官方线路。",
              "最小请求成功，且你知道如何恢复官方线路。",
            ),
          ],
        },
      ),
    ],
    verificationChecklist: [
      "账号、套餐、席位或 API 额度已在官方页面确认生效。",
      "Cockpit/Sub2API 位于上游，CC Switch/Codex++ 位于客户端侧，两者没有混用。",
      "Base URL 与 Key 来自对应上游，且 Key 没有被公开。",
      "CC Switch 与 Codex++ 只选择了其中一条路线，没有同时开启冲突配置。",
      "最小请求成功，并在上游日志或用量中看到记录。",
      "关闭第三方路线后可以恢复官方配置。",
    ],
    commonProblems: [
      {
        problem: "配置后请求返回 401",
        likelyCause: "Key 错误、Key 未启用或选错了用户 Key。",
        action: "回到上游管理端重新复制 Key，并检查上游日志中的认证结果。",
      },
      {
        problem: "请求返回 404",
        likelyCause: "Base URL 缺少 /v1 或协议路径不匹配。",
        action: "以当前上游页面显示的地址为准，不要使用旧文档中的固定端口。",
      },
      {
        problem: "提示模型不存在",
        likelyCause: "模型名来自旧教程或版本列表。",
        action: "读取 /v1/models 或上游当前模型列表，再填回客户端。",
      },
      {
        problem: "套餐显示生效但 Codex 提示无权限",
        likelyCause: "套餐名称不等于必然拥有 Codex 权限。",
        action: "查看 OpenAI 官方 Codex 权限说明，并以官方账号页面为准。",
      },
    ],
    riskNotes: [
      THIRD_PARTY_NOTICE,
      CREDENTIAL_WARNING,
      TERMS_RISK_NOTE,
      "CC Switch 与 Codex++ 通常是二选一；同时安装时需自行管理配置优先级和冲突。",
      TEAM_SEAT_WARNING,
    ],
    faq: [
      {
        question: "必须同时安装 CC Switch 和 Codex++ 吗？",
        answer: "不需要。CC Switch 与 Codex++ 通常是二选一：主要用 Codex CLI 优先 CC Switch，主要用 Codex Desktop 且需要中转注入优先 Codex++。",
      },
      {
        question: "账号显示 Plus 就一定能用 Codex 吗？",
        answer: "不一定。套餐名称不等于必然拥有 Codex 权限，必须看 OpenAI 官方账号页面和 Codex 权限说明。",
      },
      {
        question: "API 额度商品需要先导入 Cockpit 吗？",
        answer: "不需要。API 额度商品和直接中转商品可以直接走“Base URL + API Key → CC Switch 或 Codex++”路线。",
      },
      {
        question: "Team/K12 席位会被管理员撤销吗？",
        answer: "会。工作区管理员可以限制或移除席位，不要在第三方管理的工作区或未授权账号池中处理敏感信息。",
      },
    ],
    sources: [
      OFFICIAL_SOURCES.openaiCodexConfig,
      OFFICIAL_SOURCES.openaiCodexCli,
      PROJECT_SOURCES.cockpitTools,
      PROJECT_SOURCES.sub2api,
      PROJECT_SOURCES.ccSwitch,
      PROJECT_SOURCES.codexPlusPlus,
    ],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "cockpit-to-codex",
    title: "Cockpit 接入 CC Switch 或 Codex++ 使用 Codex",
    description:
      "在个人电脑上用 Cockpit Tools 管理 OpenAI 账号并启动本地 API 服务，再把 Base URL 与客户端 Key 配置给 CC Switch 或 Codex++，接入 Codex。",
    flow: ["OpenAI 账号或 JSON", "Cockpit 本地账号池", "CC Switch / Codex++", "Codex"],
    audience: [
      "个人电脑、单机用户",
      "有多个 OpenAI 账号需要本地管理的用户",
      "收到 JSON、OAuth 或 API Key 交付后需要导入 Cockpit 的用户",
    ],
    prerequisites: [
      "已安装 Cockpit Tools，且安装来源为项目官方 Release。",
      "已确认账号、套餐或席位可用。",
      "若收到 JSON，可先使用 /tools/json-to-cockpit 完成本地转换。",
      "本地端口未被占用，且用户知道真实 Base URL 和客户端 Key。",
    ],
    overview: [
      {
        type: "paragraph",
        text: "Cockpit Tools 是本地账号管理和本地 API 服务，属于上游；CC Switch 和 Codex++ 是客户端侧配置，属于下游。先完成账号导入和 API 服务启动，再配置 CC Switch 或 Codex++，不能把下游配置放在账号导入前。",
      },
      {
        type: "steps",
        title: "Cockpit 共同步骤",
        items: [
          "打开 Cockpit Tools。",
          "左侧选择 Codex。",
          "点击右上角 +。",
          "根据交付选择：OAuth 授权、Token / JSON、API Key 或导入。",
          "检查账号邮箱、套餐和额度。",
          "把目标账号加入 Cockpit API 服务账号池。",
          "启动本地 API 服务。",
          "创建或复制客户端 Key。",
          "复制 Base URL，以你当前 Cockpit API 服务页面显示的地址为准。",
          "先通过模型列表或最小请求确认服务可用。",
          "再进入 CC Switch 或 Codex++。",
        ],
      },
      {
        type: "callout",
        tone: "info",
        title: "添加 Codex 账号的四种方式",
        text: "OAuth 授权用于在浏览器中登录 OpenAI 账号并完成授权；Token / JSON 用于手动粘贴单账号 Token 或 JSON；API Key 用于直接交付可用的 Key；导入用于读取 Cockpit 支持的账号导出文件。商家交付 CPA、Sub2 或其他非 Cockpit JSON 时，先使用 /tools/json-to-cockpit 转换。",
      },
      {
        type: "callout",
        tone: "warning",
        title: "OAuth 回调只粘贴到 Cockpit",
        text: "不要在教程截图、日志或售后信息中展示完整 Token、回调 code、state 或 API Key。OAuth 回调地址只粘贴到 Cockpit 自己的输入框，不上传到本站或聊天机器人。",
      },
      {
        type: "callout",
        tone: "danger",
        title: "凭证边界",
        text: `${CREDENTIAL_WARNING}${LOCAL_CONVERTER_NOTE}`,
      },
    ],
    variants: [
      variant(
        "cc-switch",
        "方案 A：Cockpit → CC Switch → Codex",
        "CC Switch 负责供应商配置、切换和本地路由，消费 Cockpit 提供的 Base URL 与客户端 Key。",
        {
          title: "把 Cockpit 接口配置到 CC Switch",
          intro: `从 Cockpit 复制 Base URL 与客户端 Key 后，再按顺序配置 CC Switch。${UI_VERSION_NOTE}`,
          steps: [
            step(
              "先把非 Cockpit JSON 转换成 Cockpit 格式（如适用）",
              "如果商家交付的是 CPA、Sub2 或其他非 Cockpit JSON，先在浏览器本地打开站内转换工具，下载转换后的 Cockpit JSON；没有收到 JSON 时直接跳过。",
              "需要转换的文件已转换为 Cockpit JSON，且转换页只在本机处理文件。",
              {
                links: [{ label: "打开站内 JSON 转换工具", url: "/tools/json-to-cockpit" }],
                trouble: "转换只改变文件结构，不会修复过期令牌或缺失字段；转换失败时先查看跳过原因，再联系原商家。",
              },
            ),
            step(
              "从官方 Release 安装 CC Switch",
              "只从 farion1231/cc-switch 的 GitHub Releases 页面下载对应系统版本。",
              "CC Switch 安装完成。",
              {
                links: [{ label: "CC Switch Releases", url: "https://github.com/farion1231/cc-switch/releases" }],
              },
            ),
            step(
              "打开 Codex 面板",
              "在 CC Switch 中打开 Codex 面板，准备添加自定义供应商。",
              "你已进入 Codex 供应商管理界面。",
            ),
            step(
              "添加自定义供应商",
              "点击添加自定义供应商，填写供应商名称。",
              "新供应商卡片已创建。",
            ),
            step(
              "填入 Cockpit Base URL",
              "粘贴从 Cockpit API 服务页面复制的 Base URL。正文不硬编码端口，以你当前 Cockpit 页面显示的地址为准。",
              "Base URL 已填写，路径是否包含 /v1 以当前页面为准。",
            ),
            step(
              "填入 Cockpit 客户端 Key",
              "粘贴 Cockpit 生成的客户端 Key，不要把真实 Key 发到公开渠道。",
              "客户端 Key 已保存到本机配置。",
              { trouble: "Key 丢失时回到 Cockpit 重新创建或复制，不要在旧截图里找。" },
            ),
            step(
              "选择协议",
              "协议按 Cockpit 当前接口选择，Codex 通常使用 Responses。",
              "协议与上游当前接口一致。",
            ),
            step(
              "填写模型名",
              "模型名优先读取 /v1/models 或 Cockpit 当前模型列表，不要使用旧教程的固定值。",
              "模型名来自当前可用列表。",
            ),
            step(
              "启用供应商",
              "把该供应商设为启用状态。",
              "供应商已启用。",
            ),
            step(
              "重启 Codex CLI / Desktop",
              "重启 Codex CLI 或 Codex Desktop，使配置和模型目录重新加载。",
              "Codex 已加载新供应商配置。",
            ),
            step(
              "执行最小测试",
              "发送一个最小请求，确认 Cockpit 日志或用量出现记录。",
              "最小请求成功，且上游出现对应记录。",
            ),
            step(
              "知道如何切回 OpenAI Official",
              "确认 CC Switch 中切换回 OpenAI Official 的方法，并记录当前配置。",
              "关闭第三方路线后可恢复官方配置。",
              {
                items: [
                  "若当前 CC Switch 版本提供“保留官方登录”或“Codex App 增强”选项，只有需要同时保留官方插件/远程能力时才开启。",
                  "不要假设所有版本的开关名称和默认值相同。",
                ],
              },
            ),
          ],
        },
      ),
      variant(
        "codex-plusplus",
        "方案 B：Cockpit → Codex++ → Codex Desktop",
        "Codex++ 固定指 BigPizzaV3/CodexPlusPlus，通过中转注入把 Codex Desktop 请求指向 Cockpit 的 Base URL 与客户端 Key。",
        {
          title: "把 Cockpit 接口配置到 Codex++",
          intro: "必须从 Codex++ 启动入口启动 Codex，相关增强和中转配置才会生效。",
          steps: [
            step(
              "先把非 Cockpit JSON 转换成 Cockpit 格式（如适用）",
              "如果商家交付的是 CPA、Sub2 或其他非 Cockpit JSON，先在浏览器本地打开站内转换工具，下载转换后的 Cockpit JSON；没有收到 JSON 时直接跳过。",
              "需要转换的文件已转换为 Cockpit JSON，且转换页只在本机处理文件。",
              {
                links: [{ label: "打开站内 JSON 转换工具", url: "/tools/json-to-cockpit" }],
                trouble: "转换只改变文件结构，不会修复过期令牌或缺失字段；转换失败时先查看跳过原因，再联系原商家。",
              },
            ),
            step(
              "确认项目来源",
              "Codex++ 固定使用 BigPizzaV3/CodexPlusPlus，从官方仓库或官方 Release 获取。",
              "你已确认使用正确的项目，而不是同名 loader 项目。",
              {
                links: [{ label: "CodexPlusPlus 官方仓库", url: "https://github.com/BigPizzaV3/CodexPlusPlus" }],
              },
            ),
            step(
              "安装官方 Codex Desktop",
              "先从 OpenAI 官方渠道安装 Codex Desktop。",
              "官方 Codex Desktop 已安装。",
            ),
            step(
              "安装 Codex++ 对应系统版本",
              "按操作系统和架构选择 Codex++ 对应版本完成安装。",
              "Codex++ 安装完成，可打开 Codex++ Manager。",
            ),
            step(
              "打开 Codex++ Manager",
              "启动 Codex++ Manager，进入中转注入或供应商配置。",
              "你已进入配置界面。",
            ),
            step(
              "填写 Cockpit Base URL 与客户端 Key",
              "粘贴 Cockpit API 服务页面显示的 Base URL 与客户端 Key，字段名称以当前版本为准。",
              "配置已填写，没有使用固定端口或旧字段名。",
            ),
            step(
              "选择上游协议",
              "按 Cockpit 当前接口选择协议，然后应用配置。",
              "协议与上游接口一致，具体名称以当前 Codex++ 版本界面为准。",
              { items: [CODEX_PLUS_PLUS_PROTOCOL_NOTE] },
            ),
            step(
              "应用配置",
              "保存并应用中转注入配置。",
              "配置已生效并等待重启。",
            ),
            step(
              "退出已经运行的 Codex",
              "完全退出当前运行的 Codex，避免旧进程继续占用配置。",
              "没有正在运行的旧 Codex 进程。",
            ),
            step(
              "通过 Codex++ 启动 Codex",
              "必须使用 Codex++ 的启动入口重新启动 Codex，不要用普通桌面快捷方式。",
              "Codex 已通过 Codex++ 启动，注入配置生效。",
            ),
            step(
              "执行最小请求",
              "发送一个最小请求，确认 Cockpit 日志或用量出现记录。",
              "最小请求成功，且上游出现对应记录。",
            ),
            step(
              "准备回滚",
              "按版本说明清除 API 模式或中转注入，恢复官方线路。",
              "你知道如何恢复官方配置。",
            ),
          ],
        },
      ),
    ],
    verificationChecklist: [
      "Cockpit 账号状态正常。",
      "API 服务在运行。",
      "Base URL 可访问。",
      "Key 未被公开。",
      "/v1/models 或模型列表正常。",
      "Codex 请求出现在 Cockpit 日志或用量中。",
      "实际扣减的是目标账号或账号池额度。",
      "关闭第三方路线后可恢复官方配置。",
    ],
    commonProblems: [
      {
        problem: "API 服务没有启动",
        likelyCause: "账号池为空或服务状态未运行。",
        action: "回到 Cockpit API 服务页面确认账号已加入并启动服务。",
      },
      {
        problem: "填入 Base URL 后请求失败",
        likelyCause: "端口或 /v1 路径来自旧教程。",
        action: "以 Cockpit 当前 API 服务页面显示的地址为准，不要硬编码端口。",
      },
      {
        problem: "客户端 Key 无效",
        likelyCause: "复制了账号 Token 而不是客户端 Key。",
        action: "在 Cockpit 中创建或复制客户端 Key，只把 Key 给本机客户端。",
      },
      {
        problem: "模型列表为空",
        likelyCause: "账号池中没有可用账号或账号被限制。",
        action: "检查账号状态、套餐、额度和筛选条件。",
      },
    ],
    riskNotes: [
      THIRD_PARTY_NOTICE,
      CREDENTIAL_WARNING,
      LOCAL_CONVERTER_NOTE,
      TERMS_RISK_NOTE,
      "Cockpit 本地 API 服务只应在本机使用；不要把 Base URL 与客户端 Key 分享给陌生人。",
    ],
    faq: [
      {
        question: "Cockpit 和 CC Switch 是同一个工具吗？",
        answer: "不是。Cockpit 是本地账号池和 API 服务（上游），CC Switch 是客户端供应商切换（下游），两者职责不同。",
      },
      {
        question: "端口必须使用 12178 吗？",
        answer: "不一定。正文不硬编码永久端口，以你当前 Cockpit API 服务页面显示的地址为准。",
      },
      {
        question: "收到的 JSON 不是 Cockpit 格式怎么办？",
        answer: "先使用本站 /tools/json-to-cockpit 在浏览器本地完成转换，再导入 Cockpit；不要把原文件交给陌生人。",
      },
      {
        question: "本地 API 服务会公开我的账号吗？",
        answer: "Cockpit 是本地工具，但仍要保管好 Base URL 与客户端 Key；不要把本地地址和 Key 上传到公开渠道。",
      },
    ],
    sources: [
      OFFICIAL_SOURCES.openaiCodexConfig,
      PROJECT_SOURCES.cockpitTools,
      PROJECT_SOURCES.ccSwitch,
      PROJECT_SOURCES.codexPlusPlus,
    ],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "sub2api-to-codex",
    title: "Sub2API 接入 CC Switch 或 Codex++ 使用 Codex",
    description:
      "在服务器上部署 Sub2API 账号池并分发下游用户 Key，再把 HTTPS Base URL 与用户 Key 配置给 CC Switch 或 Codex++，接入 Codex。",
    flow: ["OpenAI 账号", "Sub2API 服务器账号池", "CC Switch / Codex++", "Codex"],
    audience: [
      "有服务器和运维能力的用户",
      "多设备、多用户或需要账号池调度的团队",
      "已经部署 Sub2API 并登录管理端的用户",
    ],
    prerequisites: [
      "已有服务器、域名和运维能力。",
      "理解 HTTPS、数据库、日志与密钥管理。",
      "已按 Sub2API 官方 README 部署并登录管理端。",
      "账号池中至少有一个健康可用的 OpenAI 账号。",
    ],
    overview: [
      {
        type: "callout",
        tone: "warning",
        title: "高级方案",
        text: "高级方案：需要服务器、HTTPS、数据库、日志和密钥管理能力。个人单机用户优先选择 Cockpit。",
      },
      {
        type: "paragraph",
        text: "Sub2API 是服务端账号池，不是桌面客户端，也不是普通单机用户的首选。部署时只依赖稳定概念：Linux/容器环境、数据库与缓存、HTTPS、管理员账号和数据备份。不要复制可能过时的完整部署命令，以项目官方 README 和部署文档为准。",
      },
      {
        type: "steps",
        title: "部署与账号池共同步骤",
        items: [
          "部署并登录 Sub2API 管理端。",
          "添加 OpenAI/Codex 账号。",
          "选择 OAuth 或项目当前支持的导入方式。",
          "核对账号状态、套餐、额度和失败原因。",
          "创建账号组或账号池。",
          "配置调度、并发和禁用规则。",
          "创建下游用户或 API Key。",
          "仅把用户 Key 提供给客户端，不要把管理员 Key 发给用户。",
          "复制 HTTPS Base URL。",
          "用最小请求检查 /v1/models 和 /v1/responses。",
          "再配置 CC Switch 或 Codex++。",
        ],
      },
      {
        type: "callout",
        tone: "danger",
        title: "管理员 Key 与用户 Key 分离",
        text: "管理员 Key 只能保留在服务器管理端；客户端只使用下游用户 Key。服务器应限制来源、并发和额度，且不要把示例管理员密钥或数据库密码写进任何页面。",
      },
    ],
    variants: [
      variant(
        "cc-switch",
        "方案 A：Sub2API → CC Switch → Codex",
        "CC Switch 只保存客户端配置，不代替服务器权限控制；Base URL 是远程 HTTPS 地址，API Key 是下游用户 Key。",
        {
          title: "把 Sub2API 接口配置到 CC Switch",
          intro: "步骤与 Cockpit 方案相近，但必须使用远程 HTTPS Base URL 和下游用户 Key。",
          steps: [
            step(
              "从官方 Release 安装 CC Switch",
              "只从 farion1231/cc-switch 的 GitHub Releases 页面下载对应系统版本。",
              "CC Switch 安装完成。",
              {
                links: [{ label: "CC Switch Releases", url: "https://github.com/farion1231/cc-switch/releases" }],
              },
            ),
            step(
              "打开 Codex 面板并添加自定义供应商",
              "在 CC Switch 中打开 Codex 面板，添加自定义供应商。",
              "新供应商卡片已创建。",
            ),
            step(
              "填入 Sub2API HTTPS Base URL",
              "粘贴 Sub2API 管理端提供的远程 HTTPS Base URL，不填写本地地址。",
              "Base URL 是远程 HTTPS 地址。",
            ),
            step(
              "填入下游用户 Key",
              "粘贴 Sub2API 下游用户 Key，不能使用管理员 Key。",
              "客户端只持有用户 Key。",
              { trouble: "拿到管理员 Key 时先撤销并重新签发，不要把管理员 Key 配到客户端。" },
            ),
            step(
              "选择协议并填写模型名",
              "协议按 Sub2API 当前接口选择，Codex 通常使用 Responses；模型名以 /v1/models 或管理端模型列表为准。",
              "协议和模型名与服务器当前接口一致。",
            ),
            step(
              "启用供应商并重启 Codex",
              "启用供应商后重启 Codex CLI / Desktop。",
              "Codex 已加载新供应商配置。",
            ),
            step(
              "执行最小请求",
              "发送最小请求，确认服务器调度日志显示请求落到预期账号池。",
              "最小请求成功，服务器日志出现对应记录。",
            ),
            step(
              "知道如何切回官方",
              "确认 CC Switch 中切换回 OpenAI Official 的方法。",
              "关闭第三方路线后可恢复官方配置。",
            ),
          ],
        },
      ),
      variant(
        "codex-plusplus",
        "方案 B：Sub2API → Codex++ → Codex Desktop",
        "Codex++ 固定指 BigPizzaV3/CodexPlusPlus；在中转注入中填写 Sub2API HTTPS Base URL 与下游用户 Key，并通过 Codex++ 启动。",
        {
          title: "把 Sub2API 接口配置到 Codex++",
          intro: "远程服务不可用时应先检查服务器、域名、TLS 和账号池，不要反复重装 Codex。",
          steps: [
            step(
              "确认项目来源",
              "从 BigPizzaV3/CodexPlusPlus 官方仓库或官方 Release 获取 Codex++。",
              "你已确认使用正确的项目。",
              {
                links: [{ label: "CodexPlusPlus 官方仓库", url: "https://github.com/BigPizzaV3/CodexPlusPlus" }],
              },
            ),
            step(
              "安装官方 Codex Desktop 与 Codex++",
              "先安装官方 Codex Desktop，再按系统版本安装 Codex++。",
              "两个程序都已安装。",
            ),
            step(
              "打开 Codex++ Manager 进入中转注入",
              "启动 Codex++ Manager，进入中转注入或供应商配置。",
              "你已进入配置界面。",
            ),
            step(
              "填写 Sub2API HTTPS Base URL",
              "粘贴远程 HTTPS Base URL，不填写本地地址或旧示例端口。",
              "Base URL 已填写。",
            ),
            step(
              "填写下游用户 Key",
              "粘贴下游用户 Key，不要使用管理员 Key。",
              "客户端只持有用户 Key。",
            ),
            step(
              "选择上游协议并应用配置",
              "按 Sub2API 当前接口选择协议并应用配置。",
              "配置已保存。",
              { items: [CODEX_PLUS_PLUS_PROTOCOL_NOTE] },
            ),
            step(
              "退出旧 Codex 并通过 Codex++ 启动",
              "退出已经运行的 Codex，从 Codex++ 启动入口重新启动 Codex Desktop。",
              "Codex 已通过 Codex++ 启动，注入配置生效。",
            ),
            step(
              "执行最小请求",
              "发送最小请求，确认请求到达服务器账号池。",
              "最小请求成功，服务器日志出现记录。",
            ),
            step(
              "远程故障时先查服务器",
              "服务不可用时依次检查服务器、域名、TLS 和账号池，不要反复重装 Codex。",
              "你按服务器链路排查，而不是重装客户端。",
            ),
            step(
              "清除中转注入恢复官方",
              "按版本说明清除中转注入，恢复官方线路。",
              "你已知道如何回滚。",
            ),
          ],
        },
      ),
    ],
    verificationChecklist: [
      "HTTPS 证书正常。",
      "管理端未暴露给普通用户。",
      "用户 Key 权限和额度符合预期。",
      "账号池至少有一个健康账号。",
      "调度日志显示请求落到预期账号。",
      "客户端看不到管理员密钥。",
      "请求失败不会把完整凭证写入公开日志。",
    ],
    commonProblems: [
      {
        problem: "客户端请求 401",
        likelyCause: "使用了管理员 Key，或用户 Key 已失效。",
        action: "改用下游用户 Key，必要时重新签发并撤销旧 Key。",
      },
      {
        problem: "HTTPS 证书告警",
        likelyCause: "证书过期、域名不匹配或使用自签名证书。",
        action: "先修复域名、TLS 和证书链，再继续配置客户端。",
      },
      {
        problem: "账号池没有健康账号",
        likelyCause: "账号被禁用、额度用完或调度规则排除了全部账号。",
        action: "在管理端查看账号状态、额度和失败原因。",
      },
      {
        problem: "请求没有到达服务器",
        likelyCause: "客户端走了旧配置、DNS 或网络问题。",
        action: "检查客户端供应商配置、域名解析和防火墙，不要重装 Codex。",
      },
    ],
    riskNotes: [
      THIRD_PARTY_NOTICE,
      CREDENTIAL_WARNING,
      TERMS_RISK_NOTE,
      "Sub2API 是服务端账号池，不是桌面客户端；普通单机用户优先选择 Cockpit。",
      "管理员 Key 和数据库凭据必须与用户 Key 分离，防止客户端看到服务器管理权限。",
      TEAM_SEAT_WARNING,
    ],
    faq: [
      {
        question: "Sub2API 能当作普通桌面客户端使用吗？",
        answer: "不能。Sub2API 是服务端账号池和 API 分发服务，需要服务器、HTTPS、数据库和运维能力。",
      },
      {
        question: "管理员 Key 和用户 Key 有什么区别？",
        answer: "管理员 Key 管理整个服务，只能保留在服务器管理端；用户 Key 只代表下游用户的权限和额度，客户端只应拿到用户 Key。",
      },
      {
        question: "可以复制旧版部署命令直接执行吗？",
        answer: "不要。部署命令可能过时，应以 Sub2API 官方 README 和部署文档为准，且不把示例管理员密钥或数据库密码写进页面。",
      },
      {
        question: "远程服务不可用为什么要先查服务器？",
        answer: "远程链路涉及服务器、域名、TLS、账号池和日志，反复重装 Codex 不会解决上游问题。",
      },
    ],
    sources: [
      OFFICIAL_SOURCES.openaiCodexConfig,
      PROJECT_SOURCES.sub2api,
      PROJECT_SOURCES.ccSwitch,
      PROJECT_SOURCES.codexPlusPlus,
    ],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "api-endpoint-to-codex",
    title: "把 Base URL 和 API Key 接入 CC Switch 或 Codex++",
    description:
      "已有 Base URL 与 API Key 时，不需要先导入 Cockpit 或部署 Sub2API，直接通过 CC Switch 或 Codex++ 把接口配置给 Codex。",
    flow: ["Base URL + API Key", "CC Switch / Codex++", "Codex"],
    audience: [
      "已有 OpenAI API 额度的开发者",
      "购买了直接交付中转地址和用户 Key 商品的用户",
      "不需要账号池、只需要把接口配置给 Codex 的用户",
    ],
    prerequisites: [
      "已收到 Base URL、API Key、协议、模型名、额度和并发信息。",
      "已确认 Key 只交给可信任的客户端。",
      "已安装 Codex CLI 或 Codex Desktop。",
    ],
    overview: [
      {
        type: "paragraph",
        text: "本路线不要求先导入 Cockpit，也不要求先部署 Sub2API。适用商品包括 openai-api-credit、chatgpt-access-service，以及明确交付中转地址和用户 Key 的商品。",
      },
      {
        type: "steps",
        title: "接入前先确认五项信息",
        items: [
          "Base URL：是否包含 /v1，以供应商交付为准。",
          "API Key：属于哪个下游用户，是否有有效期和额度。",
          "支持的协议：Responses 或 OpenAI-compatible。",
          "模型名：从 /v1/models 或供应商控制台读取。",
          "额度与并发：避免超限后误判为客户端问题。",
        ],
      },
      {
        type: "callout",
        tone: "warning",
        title: "不要把 Key 写进公开位置",
        text: "不把第三方 Key 写入公开仓库、前端代码或截图。供应商配置只保存在客户端本机。",
      },
      {
        type: "callout",
        tone: "info",
        title: "常见状态码排查",
        text: "出现 401 时先检查 Key；404 先检查路径和协议；模型不存在先查模型列表，不要反复重装客户端。",
      },
    ],
    variants: [
      variant(
        "cc-switch",
        "方案 A：Base URL + Key → CC Switch → Codex",
        "CC Switch 管理供应商配置和切换，适合主要使用 Codex CLI 或需要快速切换供应商的用户。",
        {
          title: "把 Base URL 与 Key 配置到 CC Switch",
          intro: "直接从官方 Release 安装 CC Switch，然后按顺序添加供应商。",
          steps: [
            step(
              "从官方 Release 安装 CC Switch",
              "只从 farion1231/cc-switch 的 GitHub Releases 页面下载。",
              "CC Switch 安装完成。",
              {
                links: [{ label: "CC Switch Releases", url: "https://github.com/farion1231/cc-switch/releases" }],
              },
            ),
            step(
              "打开 Codex 面板并添加自定义供应商",
              "在 CC Switch 中打开 Codex 面板，添加自定义供应商。",
              "新供应商卡片已创建。",
            ),
            step(
              "填入 Base URL",
              "粘贴供应商交付的 Base URL；是否包含 /v1 以供应商交付说明为准。",
              "Base URL 已填写。",
            ),
            step(
              "填入 API Key",
              "粘贴对应 Key，不要把 Key 发到公开渠道。",
              "Key 已保存到本机配置。",
            ),
            step(
              "选择协议",
              "选择 Responses 或 OpenAI-compatible，以供应商支持为准。",
              "协议与供应商一致。",
            ),
            step(
              "填写模型名",
              "模型名以 /v1/models 或供应商控制台为准。",
              "模型名来自当前可用列表。",
            ),
            step(
              "启用供应商并重启 Codex",
              "启用供应商后重启 Codex CLI / Desktop。",
              "Codex 已加载新供应商配置。",
            ),
            step(
              "执行最小请求",
              "发送一个最小请求，确认模型可用和额度扣减符合预期。",
              "最小请求成功。",
            ),
            step(
              "知道如何切回官方",
              "确认 CC Switch 中切换回 OpenAI Official 的方法。",
              "你知道如何恢复官方配置。",
            ),
          ],
        },
      ),
      variant(
        "codex-plusplus",
        "方案 B：Base URL + Key → Codex++ → Codex Desktop",
        "Codex++ 固定指 BigPizzaV3/CodexPlusPlus，适合 Codex Desktop 中转注入；必须通过 Codex++ 启动入口启动。",
        {
          title: "把 Base URL 与 Key 配置到 Codex++",
          intro: "先安装官方 Codex Desktop，再安装 Codex++，最后在中转注入中填写配置。",
          steps: [
            step(
              "从官方仓库获取 Codex++",
              "固定使用 BigPizzaV3/CodexPlusPlus，从官方仓库或官方 Release 获取。",
              "你已确认项目来源正确。",
              {
                links: [{ label: "CodexPlusPlus 官方仓库", url: "https://github.com/BigPizzaV3/CodexPlusPlus" }],
              },
            ),
            step(
              "安装官方 Codex Desktop 与 Codex++",
              "先安装官方 Codex Desktop，再按系统版本安装 Codex++。",
              "两个程序都已安装。",
            ),
            step(
              "打开 Codex++ Manager",
              "启动 Codex++ Manager，进入中转注入或供应商配置。",
              "你已进入配置界面。",
            ),
            step(
              "填写 Base URL 与 API Key",
              "粘贴供应商交付的 Base URL 与对应 Key。",
              "配置已填写。",
            ),
            step(
              "选择上游协议并应用配置",
              "按供应商支持的协议选择并应用配置。",
              "配置已保存。",
              { items: [CODEX_PLUS_PLUS_PROTOCOL_NOTE] },
            ),
            step(
              "退出旧 Codex 并通过 Codex++ 启动",
              "退出已经运行的 Codex，从 Codex++ 启动入口重新启动。",
              "Codex 已通过 Codex++ 启动，注入配置生效。",
            ),
            step(
              "执行最小请求",
              "发送最小请求，确认模型和额度正常。",
              "最小请求成功。",
            ),
            step(
              "清除 API 模式恢复官方",
              "按版本说明清除 API 模式或中转注入，恢复官方线路。",
              "你已知道如何回滚。",
            ),
          ],
        },
      ),
    ],
    verificationChecklist: [
      "最小请求成功，模型响应符合预期。",
      "模型列表可读取。",
      "额度或扣量记录与供应商说明一致。",
      "Key 未写入公开仓库、前端代码或截图。",
      "关闭第三方路线后可恢复官方配置。",
    ],
    commonProblems: [
      {
        problem: "401 Unauthorized",
        likelyCause: "API Key 错误、过期或不属于该端点。",
        action: "先检查 Key，回到供应商控制台重新复制或重新签发。",
      },
      {
        problem: "404 Not Found",
        likelyCause: "Base URL 路径或协议不匹配。",
        action: "检查路径是否包含 /v1，并核对 Responses / OpenAI-compatible 协议。",
      },
      {
        problem: "模型不存在",
        likelyCause: "模型名来自旧文档。",
        action: "读取 /v1/models 或供应商控制台，填写当前模型名。",
      },
      {
        problem: "触发额度或并发限制",
        likelyCause: "超出供应商设定的额度与并发。",
        action: "查看供应商控制台的额度、并发和错误码，不要误判为客户端问题。",
      },
    ],
    riskNotes: [
      THIRD_PARTY_NOTICE,
      CREDENTIAL_WARNING,
      TERMS_RISK_NOTE,
      "此商品直接交付 API 使用能力，不需要先把账号导入 Cockpit；只有需要自行做账号池时才考虑 Sub2API。",
    ],
    faq: [
      {
        question: "使用这个路线需要先安装 Cockpit 吗？",
        answer: "不需要。已经有 Base URL + API Key 时，直接通过 CC Switch 或 Codex++ 配置给 Codex 即可。",
      },
      {
        question: "Base URL 一定要带 /v1 吗？",
        answer: "以供应商交付说明为准。有的供应商自带 /v1，有的需要手动加上，不要按旧教程硬编码。",
      },
      {
        question: "API Key 可以写进前端代码吗？",
        answer: "不可以。Key 只应保存在可信任客户端或密钥管理环境中，不能进入公开仓库、前端代码或截图。",
      },
      {
        question: "第三方中转稳定吗？",
        answer: "不承诺稳定、永久或不会封号。中转服务可能受平台条款、组织政策、地区、网络环境和风控限制。",
      },
    ],
    sources: [
      OFFICIAL_SOURCES.openaiCodexConfig,
      PROJECT_SOURCES.ccSwitch,
      PROJECT_SOURCES.codexPlusPlus,
    ],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
] satisfies readonly WorkflowGuide[];

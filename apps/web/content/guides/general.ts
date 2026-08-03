import type { GeneralGuide } from "@/lib/guides/types";
import { LAST_REVIEWED_AT, OFFICIAL_SOURCES } from "./sources";

export const generalGuideEntries = [
  {
    slug: "buying-checklist",
    title: "AI 商品购买前检查清单",
    description: "在付款前确认产品、交付方式、账号归属、期限、价格口径、质保和售后证据。",
    blocks: [
      { type: "paragraph", text: "先判断买到的究竟是订阅、账号、团队席位、兑换码、API 额度、验证辅助、共享池还是第三方中转；名称相近不代表控制权和风险相同。" },
      {
        type: "checklist",
        title: "商品与价格",
        items: [
          "商品标题、产品档位和页面说明一致。",
          "总价对应的期限、额度、次数或倍率已经写明。",
          "共享、体验和中转没有被当作长期独享订阅比较。",
          "价格明显偏低时已查看交付限制和质保，而非只看金额。",
        ],
      },
      {
        type: "checklist",
        title: "交付与控制权",
        items: [
          "确认使用自己的账号还是商家提供的账号。",
          "确认邮箱、密码、恢复渠道和 MFA 的控制方。",
          "不向本站或陌生第三方提交密码、验证码、恢复码或身份证件。",
          "保存商品原页面、订单、期限和售后条件。",
        ],
      },
      { type: "callout", tone: "warning", title: "交易边界", text: "AI Price Radar 不参与交易、支付、交付或售后；最终条件以商品原页面和品牌官方规则为准。" },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.anthropicHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "account-control",
    title: "账号控制权判断指南",
    description: "分清登录凭据、注册邮箱、恢复渠道、密码修改权和 MFA 管理权，避免把暂时可登录误认为拥有账号。",
    blocks: [
      {
        type: "comparison",
        title: "控制权分层",
        columns: ["要素", "应确认的问题", "常见风险"],
        rows: [
          ["登录方式", "邮箱密码还是第三方登录", "拿到密码却无法使用正确入口"],
          ["注册邮箱", "是否同时交付邮箱控制权", "原注册者通过邮箱找回"],
          ["恢复渠道", "手机号、恢复邮箱由谁管理", "账号可被远程重置"],
          ["MFA", "是否允许并能够安全开启", "安全设置仍受他人控制"],
          ["组织席位", "管理员是谁、能否移除成员", "席位到期或被移除"],
        ],
      },
      {
        type: "steps",
        title: "安全核对顺序",
        items: [
          "在品牌官方页面确认登录方式与账号标识。",
          "对照商品原文确认邮箱、密码和恢复渠道的交付范围。",
          "仅在明确允许时修改密码或开启 MFA，不反复改动安全设置。",
          "控制权不完整时不绑定支付方式，也不写入个人或企业隐私。",
        ],
      },
      { type: "callout", tone: "danger", title: "可登录不等于可长期控制", text: "原注册者、邮箱持有人或工作区管理员仍可能找回账号或移除席位。" },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.googleAccount],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "subscription-verification",
    title: "订阅状态与权益确认指南",
    description: "购买或代充后，从品牌官方账户页核对账号、套餐、期限、账单和自动续费状态。",
    blocks: [
      {
        type: "steps",
        title: "确认订阅是否生效",
        items: [
          "打开品牌官方账户设置，确认当前登录账号与订单一致。",
          "查看套餐名称、付费状态、开始或到期时间。",
          "核对账单记录与自动续费状态，避免不知情的后续扣费。",
          "用一个普通、非敏感任务检查目标功能是否可用。",
          "保存显示账号标识、套餐和时间的截图，注意遮挡隐私信息。",
        ],
      },
      {
        type: "faq",
        items: [
          { question: "页面仍显示免费套餐怎么办？", answer: "先确认登录账号和约定到账时间，刷新官方账户页；仍未生效时保存截图并联系原商家。" },
          { question: "功能可用是否就代表套餐正确？", answer: "不一定。体验、团队席位或临时权限也可能开放部分功能，应以官方套餐页为准。" },
        ],
      },
      { type: "callout", tone: "info", title: "以官方状态为准", text: "商品页描述用于确认交易约定；实际账号套餐、账单和续费状态以品牌官方账户页显示为准。" },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.geminiHelp, OFFICIAL_SOURCES.xHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "troubleshooting",
    title: "登录、激活与套餐故障排查",
    description: "使用安全、可逆的步骤确认登录方式、账号、官方状态和错误证据，不绕过验证或风控。",
    blocks: [
      {
        type: "steps",
        title: "按顺序排查",
        items: [
          "确认使用商品说明约定的正确登录方式。",
          "确认当前账号与订单中的目标账号一致。",
          "查看品牌官方状态页、账户页和完整错误提示。",
          "不要反复修改密码、邮箱、MFA 或其他安全设置。",
          "保存错误截图、发生时间、账号标识和订单信息。",
          "在商品售后范围内联系原商家。",
          "涉及账号安全、恢复或可疑登录时，改用品牌官方恢复与支持渠道。",
        ],
      },
      {
        type: "faq",
        items: [
          { question: "遇到地区或验证提示怎么办？", answer: "按官方页面提示处理或联系官方支持；本站不提供绕过地区、身份、短信、支付验证或风控的方法。" },
          { question: "可以连续尝试多个密码吗？", answer: "不建议。反复尝试可能触发安全限制，应先确认登录方式并保存错误提示。" },
        ],
      },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.anthropicHelp, OFFICIAL_SOURCES.googleAccount],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "after-sales-evidence",
    title: "售后证据准备指南",
    description: "在不泄露密码、验证码、恢复码和完整密钥的前提下，准备能说明商品、账号状态、时间与错误的信息。",
    blocks: [
      {
        type: "checklist",
        title: "建议保存",
        items: [
          "商品原页面、标题、交付类型、期限、价格和售后条件。",
          "订单编号、支付时间、交付时间和沟通记录。",
          "品牌官方账户页中的账号标识、套餐、到期时间或用量。",
          "完整错误提示、发生时间、重现步骤和官方状态信息。",
          "卡密兑换结果、团队邀请状态或 API 的非敏感请求标识。",
        ],
      },
      {
        type: "callout",
        tone: "danger",
        title: "先遮挡敏感信息",
        text: "截图和日志中必须遮挡密码、验证码、恢复码、身份证件、支付信息、完整 API Key、Cookie 和会话令牌。",
      },
      {
        type: "steps",
        title: "描述问题",
        items: [
          "写明预期收到什么、实际收到什么。",
          "按时间顺序列出已经完成的安全操作。",
          "附上经过遮挡的证据，并说明希望按商品原页面执行哪项售后。",
        ],
      },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    slug: "security",
    title: "AI 账号安全与隐私指南",
    description: "按交付方式判断数据边界，保护账号凭据、API Key、聊天内容、文件和支付信息。",
    blocks: [
      {
        type: "checklist",
        title: "账号与凭据",
        items: [
          "只在品牌官方域名输入账号凭据、兑换码或恢复信息。",
          "不同服务使用不同密码，并在拥有完整控制权时开启 MFA。",
          "API Key 使用环境变量或密钥管理，不写入前端、聊天、截图或代码仓库。",
          "怀疑泄露时立即撤销或轮换凭据，并检查异常登录、用量和账单。",
        ],
      },
      {
        type: "comparison",
        title: "数据风险按交付形式变化",
        columns: ["交付形式", "主要风险", "数据原则"],
        rows: [
          ["成品或体验账号", "原注册者可找回", "不保存隐私、支付或长期资料"],
          ["团队席位", "管理员可管理或移除", "不写入公司机密或个人敏感资料"],
          ["共享池", "其他使用者可能看到会话", "只处理可公开、可丢弃内容"],
          ["第三方中转", "请求经第三方服务器", "不发送敏感、受监管或保密数据"],
        ],
      },
      { type: "callout", tone: "warning", title: "安全功能不是障碍", text: "不要按第三方要求关闭 MFA 或规避品牌验证与风控；遇到安全问题使用官方恢复渠道。" },
    ],
    officialSources: [OFFICIAL_SOURCES.openaiKeySafety, OFFICIAL_SOURCES.googleAccount, OFFICIAL_SOURCES.geminiHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
] as const satisfies readonly GeneralGuide[];

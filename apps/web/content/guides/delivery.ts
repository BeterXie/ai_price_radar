import type { DeliveryGuide } from "@/lib/guides/types";
import { LAST_REVIEWED_AT, OFFICIAL_SOURCES } from "./sources";

export const deliveryGuideEntries = [
  {
    deliveryType: "subscription_recharge",
    title: "订阅代充、直充与充值指南",
    shortLabel: "订阅充值",
    summary: "商家为指定账号开通一段时间的订阅；先确认使用自己的账号还是商家提供的账号，二者的控制权完全不同。",
    whatYouReceive: [
      "自有账号代充通常只产生套餐状态变化，不会收到新账号。",
      "商家账号充值会同时涉及账号凭据和订阅权益，必须分别确认归属。",
    ],
    beforeBuying: [
      "确认充值账号、套餐名称、期限、适用地区以及是否会自动续费。",
      "只提供完成订单所需的最少信息；不要向商家提供长期有效密码、验证码或恢复码。",
      "保存商品页中关于账号归属、到账时间和售后的原始说明。",
    ],
    usageSteps: [
      "在官方页面核对当前登录账号，避免为错误账号充值。",
      "按商品页约定等待处理；不要同时重复下单或反复改动安全设置。",
      "处理完成后从官方账户设置查看套餐和续费状态。",
    ],
    verifySuccess: [
      "账号标识与下单账号一致。",
      "官方账户页显示正确套餐、到期时间或账单记录。",
      "自动续费状态符合下单前约定。",
    ],
    commonProblems: [
      { problem: "套餐未生效", action: "刷新官方账户页并保存套餐页截图，等待约定到账时间后联系原商家。" },
      { problem: "重复扣费", action: "核对官方账单与商家订单，不要再次付款，分别联系对应收费方。" },
      { problem: "账号不匹配", action: "停止后续操作，保存当前账号标识与订单信息并联系原商家。" },
    ],
    riskNotes: [
      "具体充值规则、套餐权益和退款条件以品牌官方页面与商家商品原页面为准。",
      "任何要求长期保留密码或索取验证码、恢复码的流程都应停止。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "finished_account",
    title: "成品账号登录、控制权与安全指南",
    shortLabel: "成品账号",
    summary: "成品账号是已注册、可按约定方式登录的完整账号，但收到登录凭据不代表拥有长期账号控制权。",
    whatYouReceive: [
      "登录方式可能是邮箱密码，也可能依赖 Google、Apple、X 等第三方登录。",
      "邮箱控制权、密码修改权和 MFA 设置权需要在购买前分别确认。",
    ],
    beforeBuying: [
      "确认是否交付邮箱控制权、是否允许修改密码、是否允许开启 MFA。",
      "确认登录方式、质保期限、多人登录限制和账号被找回时的处理范围。",
      "阅读品牌官方条款；账号共享或转让可能不被允许。",
    ],
    usageSteps: [
      "只在品牌官方登录页面使用约定的登录方式。",
      "首次登录后先核对账号、套餐和安全设置，不要立即批量修改资料。",
      "仅在商品说明明确允许且已取得邮箱控制权时修改密码或开启 MFA。",
    ],
    verifySuccess: [
      "官方账户页显示的账号标识、套餐和期限符合订单。",
      "已明确谁控制注册邮箱、恢复渠道和 MFA。",
      "退出并重新登录一次仍能使用约定方式访问。",
    ],
    commonProblems: [
      { problem: "登录方式不匹配", action: "停止尝试其他密码，保存错误提示并向原商家确认是密码登录还是第三方登录。" },
      { problem: "不能修改密码或 MFA", action: "不要强行更改；核对商品原文中的控制权范围。" },
      { problem: "账号被找回", action: "保存登录失败、订单和交付记录，联系原商家；本站不提供账号接管方法。" },
    ],
    riskNotes: [
      "原注册者可能通过邮箱或恢复渠道找回账号；凭据交付不等于账号所有权。",
      "不要在第三方成品账号中存放个人隐私、公司机密、支付信息或长期聊天记录。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiTerms, OFFICIAL_SOURCES.openaiHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "semi_finished_account",
    title: "半成品账号首次登录与激活指南",
    shortLabel: "半成品账号",
    summary: "半成品账号通常还需要完成首次登录、常规绑定或品牌官方要求的验证，交付不代表验证必然成功。",
    whatYouReceive: [
      "可用于开始激活的账号信息，以及商家明确列出的剩余正常步骤。",
      "不应包含代为规避官方身份、短信、地区、支付验证或风控的承诺。",
    ],
    beforeBuying: [
      "确认还缺少哪些官方激活步骤、由谁完成，以及失败后的售后范围。",
      "不要向本站或陌生第三方提交身份证件、密码、验证码、恢复码等敏感凭据。",
      "确认是否交付邮箱控制权以及完成激活后能否维护安全设置。",
    ],
    usageSteps: [
      "在品牌官方页面使用商品约定的登录方式。",
      "只完成页面直接提示的常规激活、条款确认或资料核对。",
      "遇到额外验证或风险提示时停止操作，使用官方帮助渠道或联系原商家。",
    ],
    verifySuccess: [
      "能够通过约定登录方式正常进入官方账户。",
      "官方页面不再显示待完成的常规激活步骤。",
      "账号控制权、邮箱归属和隐私边界已经明确。",
    ],
    commonProblems: [
      { problem: "要求额外验证", action: "不要寻找规避方法；记录官方提示并核对商品售后范围。" },
      { problem: "需要恢复码或证件", action: "停止向第三方提交敏感材料，改用品牌官方支持渠道。" },
    ],
    riskNotes: [
      "本站不提供规避官方验证、地区限制或风控的方法。",
      "账号仍可能由原注册者控制；不要在控制权未确认前写入隐私或机密内容。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.openaiTerms],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "team_seat",
    title: "团队席位与工作区邀请指南",
    shortLabel: "团队席位",
    summary: "团队席位让用户加入其他组织的工作区；席位是访问权限，不等于账号或组织所有权。",
    whatYouReceive: [
      "来自组织或工作区的邀请，以及在席位有效期内可使用的团队功能。",
      "管理员可能拥有成员管理、权限分配和移除成员等管理能力。",
    ],
    beforeBuying: [
      "确认邀请来源、工作区名称、管理员身份、席位期限和被移出后的售后。",
      "确认使用现有个人账号加入还是领取独立账号。",
      "工作区权限可能随退出、到期或被管理员移除而消失。",
    ],
    usageSteps: [
      "从官方页面检查邀请的组织名称和接收账号。",
      "接受邀请后确认当前所在工作区，避免把内容写入错误组织。",
      "需要离开时使用官方工作区设置退出，无法自助退出则联系管理员。",
    ],
    verifySuccess: [
      "官方账户页显示正确的组织或工作区名称。",
      "目标团队功能可用，且个人账号登录方式没有改变。",
      "已知道管理员、席位期限和退出路径。",
    ],
    commonProblems: [
      { problem: "未收到邀请", action: "核对接收账号、垃圾邮件与官方通知中心，再联系原商家确认邀请状态。" },
      { problem: "被移出工作区", action: "保存工作区提示和订单信息；席位失效不等于个人账号丢失。" },
    ],
    riskNotes: [
      "组织管理员可能管理你的席位；不要在他人工作区存放公司机密或个人敏感资料。",
      "席位不等于账号控制权，离开工作区后访问和其中内容可能不可用。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.anthropicHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "card_code",
    title: "卡密与兑换码使用指南",
    shortLabel: "兑换码",
    summary: "卡密或兑换码用于在指定官方入口兑换权益，适用品牌、地区、套餐和期限必须与账号条件一致。",
    whatYouReceive: ["一段一次性或有限次数使用的兑换码，以及商品页声明的适用范围。"],
    beforeBuying: [
      "核对品牌、地区、套餐、有效期、账号资格和是否仅限新用户。",
      "兑换前确认官方页面中登录的是目标账号。",
      "只在品牌官方兑换页面输入兑换码，不向第三方页面或聊天窗口泄露。",
    ],
    usageSteps: [
      "保存订单、商品页和未展示完整码值的交付记录。",
      "打开商品说明指向的品牌官方兑换入口并核对域名。",
      "确认账号后仅提交一次，保存成功或失败结果。",
    ],
    verifySuccess: ["官方账户页显示相应权益、期限或兑换记录。", "保存兑换成功页和账号标识的截图。"],
    commonProblems: [
      { problem: "兑换码过期或已使用", action: "不要反复提交；保存完整错误提示、时间和订单，联系原商家。" },
      { problem: "地区或套餐不匹配", action: "停止兑换，不尝试规避地区限制，按商品页售后规则处理。" },
    ],
    riskNotes: ["兑换码通常一经使用不可恢复；不要公开完整码值。", "本站不提供改变地区或规避账号资格限制的方法。"],
    officialSources: [OFFICIAL_SOURCES.geminiHelp, OFFICIAL_SOURCES.xHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "api_credit",
    title: "API Key 与额度安全指南",
    shortLabel: "API 额度",
    summary: "API 额度用于程序调用，与 ChatGPT、Claude、Gemini 或 Grok 的网页会员不是同一项服务。",
    whatYouReceive: [
      "可能是官方项目额度、独立 API Key，或由卖方控制的访问权限；三者的账单与撤销权不同。",
      "第三方售卖的 Key 可能被多人共用、限制模型或随时撤销。",
    ],
    beforeBuying: [
      "确认是官方 API、项目成员权限还是第三方访问，并核对额度单位、模型、有效期和速率限制。",
      "确认谁能查看用量、设置预算、撤销 Key 和处理异常账单。",
      "不要购买来源不明或要求在公开页面展示完整 Key 的服务。",
    ],
    usageSteps: [
      "API Key 不得写入前端、公开代码或公开仓库。",
      "使用环境变量或专用密钥管理服务，并按应用和环境使用不同 Key。",
      "在官方控制台设置使用额度、预算阈值和账单提醒，持续查看用量。",
    ],
    verifySuccess: [
      "通过最小测试请求确认模型、额度和权限，避免先运行高成本任务。",
      "官方控制台中的用量与请求对应，预算与提醒已生效。",
      "已确认可以由自己或明确的管理员撤销并轮换 Key。",
    ],
    commonProblems: [
      { problem: "Key 泄露", action: "立即在官方控制台撤销泄露的 Key，创建新 Key，并检查异常用量和账单。" },
      { problem: "额度与宣传不一致", action: "保存控制台用量、错误响应和订单口径，停止高成本请求并联系原商家。" },
    ],
    riskNotes: [
      "Key 代表调用与费用权限；任何拿到 Key 的人都可能产生用量。",
      "不要把生产数据或敏感内容发送给来源不明的第三方 API 服务。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiKeySafety, OFFICIAL_SOURCES.openaiPlatform],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "verification_service",
    title: "注册与验证辅助服务风险说明",
    shortLabel: "验证服务",
    summary: "验证辅助通常只处理注册或验证环节，不等于提供长期账号控制权，也不代表品牌官方认可。",
    whatYouReceive: ["商品页约定的一次性辅助结果；本站不收集、展示或转交用户验证码。"],
    beforeBuying: [
      "确认服务是否合法、合规并符合品牌规则，以及失败后的售后范围。",
      "拒绝绕过官方验证、自动化规避风控或长期接管账号的承诺。",
      "不要提交密码、验证码、恢复码、身份证件或其他敏感凭据给本站。",
    ],
    usageSteps: [
      "优先使用品牌官方注册、验证和恢复渠道。",
      "如商品仅提供合规咨询，按官方页面提示由本人完成操作。",
      "遇到索取敏感凭据或规避安全机制的要求时立即停止。",
    ],
    verifySuccess: ["通过品牌官方页面确认账号状态。", "确认账号恢复渠道与控制权仍由本人掌握。"],
    commonProblems: [
      { problem: "验证未通过", action: "保留官方提示并使用官方支持；不要反复提交或尝试规避验证。" },
      { problem: "被索取验证码", action: "停止交易，不向本站或第三方披露验证码。" },
    ],
    riskNotes: [
      "本站不提供接码、规避验证或自动化绕过教程。",
      "验证服务不等于账号所有权；确认控制权并避免泄露隐私和敏感凭据。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.googleAccount],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "shared_pool",
    title: "共享账号与共享池风险指南",
    shortLabel: "共享账号",
    summary: "共享池由多人共用同一账号或资源池，隐私、稳定性和会话冲突风险显著高于独享订阅。",
    whatYouReceive: ["有限时间或次数的共享访问，不等于独享账号、订阅或账号控制权。"],
    beforeBuying: [
      "确认并发、期限、掉线、记录可见性、质保和禁止操作。",
      "共享池不应与长期独享订阅直接比价。",
      "确认不会用于个人隐私、企业机密、受监管数据或支付操作。",
    ],
    usageSteps: [
      "只处理非敏感、可替代的临时内容。",
      "不要保存支付信息，不要上传个人或企业敏感资料。",
      "不要修改密码、邮箱、MFA 或其他安全设置，使用后退出当前会话。",
    ],
    verifySuccess: ["可在约定期限内访问声明的功能。", "没有保存账号、付款或敏感信息，且会话已正常退出。"],
    commonProblems: [
      { problem: "会话冲突或掉线", action: "停止重复登录，记录发生时间并按商品页的并发与质保规则联系原商家。" },
      { problem: "看到他人内容", action: "不要查看、复制或传播，立即退出并报告原商家。" },
    ],
    riskNotes: [
      "多人可能看到同一账号中的历史记录、文件或会话；默认按不具备隐私保障处理。",
      "共享账号可能随时失效，且官方条款可能限制账号共享。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiTerms, OFFICIAL_SOURCES.anthropicTerms],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "relay_api",
    title: "第三方 API 中转服务说明",
    shortLabel: "API 中转",
    summary: "中转或反代不是品牌官方 API；请求会先到第三方服务器，再由第三方处理或转发。",
    whatYouReceive: [
      "第三方接口地址、访问凭据和按其规则计算的额度、倍率或并发。",
      "中转服务的额度、倍率和并发不等于官方账单或官方服务承诺。",
    ],
    beforeBuying: [
      "确认运营主体、隐私政策、日志保留、模型范围、额度单位、并发与失效规则。",
      "明确密钥、输入和输出可能由第三方服务器处理。",
      "不得用于敏感、受监管、保密或无法接受泄露的数据。",
    ],
    usageSteps: [
      "使用独立、低权限的中转凭据并设置客户端预算上限。",
      "先用非敏感测试数据验证接口、模型和计费口径。",
      "监控异常用量；不在前端或公开仓库保存中转密钥。",
    ],
    verifySuccess: ["响应模型、计费单位和扣量与商品说明一致。", "确认停止使用后可以撤销第三方凭据。"],
    commonProblems: [
      { problem: "模型或倍率不符", action: "保存非敏感请求的时间、响应标识和扣量记录，停止继续消耗并联系原商家。" },
      { problem: "怀疑数据泄露", action: "立即撤销凭据、停止发送数据，并按组织安全流程处理。" },
    ],
    riskNotes: [
      "第三方可能处理、记录或分析请求内容与输出，不能按官方 API 的数据边界推定。",
      "本站不提供绕过官方地区、额度、验证或风控限制的中转配置方法。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiKeySafety, OFFICIAL_SOURCES.anthropicDocs],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
  {
    deliveryType: "trial_account",
    title: "短期体验号、日抛号与小时号指南",
    shortLabel: "体验账号",
    summary: "体验号有效期短，可能按小时、天或很短周期提供，并可能随时失效。",
    whatYouReceive: ["临时账号或短期访问权，不适合长期工作，也不代表稳定的账号控制权。"],
    beforeBuying: [
      "确认起算时间、有效期、可用功能、登录次数和失效后的质保。",
      "体验号价格不能与长期独享账号或完整订阅直接比较。",
      "确认任务可以在账号失效后安全丢弃，不绑定任何重要资料。",
    ],
    usageSteps: [
      "仅用于非敏感、可随时停止的测试。",
      "不要保存聊天记录、机密、支付方式或个人身份信息。",
      "任务结束后导出允许保留的非敏感结果并退出。",
    ],
    verifySuccess: ["在商品声明的短期范围内可以使用目标功能。", "账号中没有留下隐私、机密或支付信息。"],
    commonProblems: [
      { problem: "提前失效", action: "保存登录提示、时间和订单说明，按原商品质保联系商家。" },
      { problem: "功能不完整", action: "核对购买的是体验号而非完整订阅，保存套餐页证据。" },
    ],
    riskNotes: [
      "账号可能随时失效或被原注册者收回，不能依赖其长期控制权。",
      "不要在体验账号存放隐私或机密内容，也不要用于持续业务。",
    ],
    officialSources: [OFFICIAL_SOURCES.openaiHelp, OFFICIAL_SOURCES.anthropicHelp],
    lastReviewedAt: LAST_REVIEWED_AT,
  },
] as const satisfies readonly DeliveryGuide[];

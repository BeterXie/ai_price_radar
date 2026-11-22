# 辅助商品目录

新增 7 个分类、17 个标准产品。沿用现有来源 Connector、审核、完整快照、同款分组和价格历史流程，不新增数据库表。

| 分类 | 标准产品 |
| --- | --- |
| 邮箱 | `email-gmail`、`email-outlook`、`email-education`、`email-icloud`、`email-account` |
| 接码 / 验证 | 新增 `verification-google`、`verification-claude`、`verification-cursor`、`verification-social`、`verification-paypal`、`verification-general`、`verification-kyc` |
| 虚拟卡 | `virtual-card` |
| 礼品卡 | `gift-card` |
| 社媒账号 | `social-media-account` |
| Apple ID | `apple-id-account` |
| VPS | `vps` |

原有 `chatgpt-access-service`、`muse-access-service`、`jev-access-service` 归入“接码 / 验证”，保持原 product ID、slug、历史报价和关注关系。
线上已有的 `x-account` 继续由 X 分类管理；新增社媒分类不迁走这些历史账号报价。

## 分类与展示

- 商品标题优先；描述中的联系方式、支持平台、支付方式、附赠邮箱等不用于新增辅助商品归类。
- “已接码”“未接码”和账号附带的接码链接保留为账号信息，不将账号变成验证服务。
- 虚拟卡、礼品卡、服务器租用分别使用 `virtual_card`、`gift_card`、`hosting_service`；邮箱与账号复用账号交付，接码复用 `verification_service`。
- 人工锁定、隐藏和审核规则继续生效，导入不会自动恢复被隐藏的报价。
- 前台、后台使用同一组分类。辅助分类不显示 AI 套餐专用的“成品账号 / 代充”快捷切换，仍可使用完整筛选表单。

金额为商家原始报价；不同礼品卡面额、虚拟卡额度、社媒平台、VPS 配置和计费周期不等价。本次不做面额或硬件规格归一化。现有原币种、CNY 主价格和低价校验规则继续适用，低于 1 元的报价仍可显示，但不会计入可信主最低价。

## 使已有来源生效

1. 按 `docs/QUICK_DEPLOY.md`、`docs/MULTI_BRAND_DEPLOY.md`、`docs/COLLECTOR_DEPLOY.md` 更新 API、五站 Web、Pipeline、Detector、Crawler 与 Oracle Worker，并保持两端 Release 一致。
2. API 启动和导入会幂等登记新产品；复用 `scripts/reclassify_account_offers.py --dry-run` 预览历史商品归类，应用仍走现有重分类入口。
3. 重新扫描已收录的 LDXP 店铺。过去未匹配的邮箱、卡片和社媒商品可能从未进入爬虫数据库，仅重分类无法补齐。
4. 发布一份完整多来源快照后，前台和机器人才能同时读取新增报价。没有来源报价的分类保留空状态，不生成示例价格。

Source Discovery 和 LDXP 默认关键词已包含这些分类；16688 原有分类轮询继续使用，未扩大扫描预算。

## 参考商品与稳定扫描

2026-11-22 从 PriceAI 的公开商品页核对原始商家链接，将 38 家 LDXP 店铺写入 `crawler/ldxp/seeds.txt`，并与 46 家 16688 商家一起写入 `config/discovery/general_seeds.txt`。生产任务实际读取的 `config/collection-keywords.json` 同时增加辅助商品词。

这些链接进入现有持久候选、审批和定时扫描流程；已存在的来源去重，人工隐藏或停用决定保持不变。商品、价格和库存读取原商家接口，保留原始链接和采集时间。PriceAI 用于发现与分类核对，不镜像其聚合数据库。VPS 查询当时无商品结果，保留空分类，不将广告报价当作库存。

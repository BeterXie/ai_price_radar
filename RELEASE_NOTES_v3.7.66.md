# Release Notes v3.7.66 - 收录邮件地址与「店铺已收录」通知修复

**Release Date:** 2026-09-13  
**Version:** 3.7.66  

---

## 变更概要 (Overview)

v3.7.65 支持了 16688 单品链接反查店铺，但收录完成邮件的地址与文案未同步适配，导致两类问题：

1. **链接地址错误**：当用户提交的是单品链接（`/goods/G...`）时，邮件里的「本站收录页面」直接套用了申请表中的 `source_key`，生成 `https://ai.pricememo.cn/shops/https://www.16688.com.cn/goods/G22076118` 这类无效地址。`source_key` 并不等于店铺 token，只有真正来自 `shops` 表的 token 才能用于公开链接。
2. **文案与实际不符**：申请单里的店铺若已被系统收录（例如提交的是已收录店铺的某个商品），邮件仍称「店铺已正式收录」，用户会重复提交收录申请。

---

## 主要更新点 (Key Updates)

1. **收录邮件地址解析 (`pipeline/publish_catalog.py`)**
   - 新增 `resolve_intake_shop()`，按「本次发布的店铺 token（单店铺来源时）→ `source_url` → `source_key` → 店铺 token → 商品 key 反查 → 来源 origin」的顺序解析真实店铺，只有确证命中 `shops` 表才生成「本站收录页面」链接，否则该行整行省略，杜绝拼接出无效 URL；
   - 店铺名称若为 URL（如 `www.16688.com.cn`）自动替换为店铺真实名称。

2. **「店铺已收录，新增商品无需重新申请」通知**
   - 当提交地址是该店铺已收录商品的页面时，改为发送规则说明邮件：告知用户该店铺已在收录列表中，系统会自动扫描同步新增商品，无需重复提交收录申请，并给出店铺收录页与本次提交地址；
   - 新事件类型 `shop_intake.goods_added`（独立 dedupe key，不影响历史 `shop_intake.onboarded` 记录）；
   - 首次收录的新店铺（即使通过单品链接提交）仍发送「店铺已正式收录」并附带正确收录页链接。

3. **补发工具与回归测试**
   - `pipeline/backfill_published_intake_emails.py` 支持 `--intake-id` 与 `--replace`，可针对单条收录申请重新生成并补发正确邮件；
   - 新增测试：新店铺单品链接仍发收录邮件、已收录店铺单品链接发规则说明邮件、新店铺收录页链接正确。

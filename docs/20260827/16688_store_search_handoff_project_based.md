# AI Price Radar — 16688 店铺检索与接入交接文档

- 项目：`BeterXie/ai_price_radar`
- 生产站点：`https://ai.pricememo.cn`
- 代码基线：`main`
- 基线提交：`6d591e8c2d6a78557ff85f5cd0be929c342fcb7a`
- 仓库内相关版本说明：`RELEASE_NOTES_v3.7.14.md`（16688 Source Integration）
- 文档日期：2026-08-27
- 文档目标：说明 16688 店铺发现、验证、采集、入库、发布的现状，明确当前“检索不到足够店铺”的真实缺口和下一步改造位置。

> 本文档基于当前仓库代码编写，不是通用爬虫方案。实现时优先复用现有 Unified Source Discovery、Detector、Connector、Atomic Publish 链路，不新增第二套并行发布体系。

---

## 1. 交接结论

当前项目对 **16688 的“店铺读取与发布”已经基本完成**，真正欠缺的是：

> **如何高召回地发现更多真实的 `https://www.16688.com.cn/shop/{code}` 候选 URL。**

当前仓库已经具备：

1. 16688 URL 识别；
2. 16688 店铺 alias → canonical shop number 解析；
3. 官方公开店铺详情 API 校验；
4. 官方公开商品列表 API 读取；
5. 平台隔离后的店铺 token；
6. 商品标准化；
7. AI 商品分类；
8. Source Candidate 去重与状态机；
9. Detector 验证；
10. 管理审核；
11. Atomic multi-source snapshot 发布；
12. FastAPI / Next.js 公开展示；
13. `source_platform=16688` 筛选。

所以后续工作不应再“重写 16688 爬虫”，而应把主要精力放在：

- 16688 搜索词覆盖；
- 16688 公共索引召回；
- 高质量种子；
- 候选证据记录；
- 发现效果统计；
- 必要时新增“第三方公开索引 → 官方 16688 shop URL”的候选适配器。

---

# 2. 当前架构中的 16688 位置

当前主数据流：

```text
Seed / Bing / GitHub / Common Crawl
              │
              ▼
Unified Source Discovery
crawler/ldxp/ldxp_crawler/source_discovery/
              │
              ▼
SourceCandidate
apps/api/app/services/source_discovery.py
              │
              ▼
Source Detector
detector/probe.py
              │
              ▼
管理员审核 / SourceIntake
              │
              ▼
16688 Connector
pipeline/connectors/platform_16688.py
              │
              ▼
common record shape
              │
              ▼
pipeline/common.py
分类 / Shop / RawProduct / Offer / History
              │
              ▼
Atomic Snapshot Publish
pipeline/publish_catalog.py
              │
              ▼
PostgreSQL
              │
       ┌──────┴──────┐
       ▼             ▼
FastAPI           Next.js
```

---

# 3. 16688 已实现能力清单

## 3.1 平台识别

文件：

```text
apps/api/app/services/source_platform.py
```

当前已定义：

```python
PLATFORM_16688_HOSTS = {"16688.com.cn", "www.16688.com.cn"}
PLATFORM_16688_PATH = re.compile(r"^/shop/([A-Za-z0-9._~-]+)$", re.IGNORECASE)
```

合法输入形态：

```text
https://www.16688.com.cn/shop/{shop_code}
https://16688.com.cn/shop/{shop_code}
```

识别后平台：

```text
16688
```

店铺 token：

```text
16688-{shop_no}
```

这样可以防止与 LDXP 或其他平台出现相同 token 时发生碰撞。

---

## 3.2 16688 Detector

文件：

```text
detector/probe.py
```

当检测到：

```text
16688.com.cn/shop/{code}
```

会进入：

```python
_probe_16688(...)
```

当前检测流程：

```text
候选 shop code
    │
    ▼
POST /shopApi/shop/detail
    │
    ├─ 验证 code == 1
    ├─ 读取 canonical shop_no
    └─ 读取 shop name
    │
    ▼
POST /shopApi/goods/list
{
  "shop_no": canonical_shop_no,
  "sort": "default"
}
    │
    ├─ 验证 code == 1
    └─ 验证 data.list
```

只有实际通过公开 API 契约的 URL 才能作为真实 16688 店铺继续流转。

这意味着：

> Discovery 阶段可以允许“多来源候选”，但绝不能把搜索结果本身当成已确认店铺。

真实确认仍以 Detector 为准。

---

# 4. 16688 Connector 当前实现

文件：

```text
pipeline/connectors/platform_16688.py
```

Connector 名：

```python
name = "16688"
```

注册位置：

```text
pipeline/connectors/__init__.py
```

注册内容：

```python
"16688": platform_16688.load_records
```

## 4.1 当前公开 API

店铺详情：

```text
POST https://www.16688.com.cn/shopApi/shop/detail
```

Payload：

```json
{
  "shop_no": "<requested_shop_no>"
}
```

商品列表：

```text
POST https://www.16688.com.cn/shopApi/goods/list
```

Payload：

```json
{
  "shop_no": "<canonical_shop_no>",
  "sort": "default"
}
```

---

## 4.2 Connector 输出字段

16688 商品会转换成项目统一 record。

关键字段：

```text
token
shop_name
shop_url
shop_status
source_platform
source_kind
product_key
variant_key
product_name
category_name
product_url
listed_price
currency
stock_count
product_status
auto_delivery
raw_json
```

16688 特有身份：

```text
shop token:
16688-{shop_no}

product key:
16688:{goods_no}

variant key:
{goods_no}
```

例如代码逻辑：

```python
def _shop_token(shop_no: str) -> str:
    return f"16688-{shop_no}"
```

商品 URL：

```text
https://www.16688.com.cn/goods/{goods_no}
```

店铺 URL：

```text
https://www.16688.com.cn/shop/{shop_no}
```

币种固定：

```text
CNY
```

---

# 5. 数据库层无需为 16688 重新设计

核心模型：

```text
apps/api/app/models.py
```

现有：

```text
Shop
Product
RawProduct
Offer
OfferHistory
```

其中 `Shop` 已经拥有：

```text
token
name
source_url
platform
source_score
status
consecutive_failures
is_visible
first_seen_at
last_seen_at
last_success_at
```

因此不建议建立独立：

```text
16688_shops
16688_products
```

继续使用统一模型即可。

正确身份模型：

```text
Shop.token = 16688-{shop_no}
Shop.platform = 16688
RawProduct.source_product_key = 16688:{goods_no}
```

---

# 6. 当前 AI 分类已经覆盖目标范围

分类入口位于：

```text
pipeline/common.py
```

现有标准商品已包括：

```text
chatgpt-account
chatgpt-plus
chatgpt-go
chatgpt-k12
chatgpt-pro
chatgpt-pro-5x
chatgpt-pro-20x
openai-api-credit
chatgpt-access-service
codex-access

claude-pro
claude-account
claude-api-access

gemini-advanced
gemini-account
gemini-api-access

grok-super
grok-account
grok-api-access
```

特别重要：

```text
chatgpt-access-service
```

本身就是：

> ChatGPT / Codex 周边服务：接码、验证、提链、邮箱等辅助服务。

所以 **Codex 接码不需要新建一套 16688 专用分类**。

除非后续业务明确需要把：

```text
Codex 接码
Codex 长效接码
Codex 短效接码
```

再拆成更细的标准产品，否则现阶段应先通过：

```text
chatgpt-access-service
tags
delivery_type
use_scenarios
raw title
```

表达。

---

# 7. 当前真正的缺口：Discovery 召回率

## 7.1 当前 Unified Source Discovery

目录：

```text
crawler/ldxp/ldxp_crawler/source_discovery/
```

已有：

```text
bing.py
commoncrawl.py
github.py
seed.py
normalize.py
runner.py
keywords.py
bridge.py
```

生产入口：

```text
scripts/refresh_remote.sh
```

执行：

```bash
bash scripts/refresh_remote.sh discover
```

其中 Unified Source Discovery 默认：

```text
seed,bing,github,commoncrawl
```

---

# 8. Bing 对 16688 的当前实现存在明确召回缺口

文件：

```text
crawler/ldxp/ldxp_crawler/source_discovery/keywords.py
```

当前：

```python
def bing_16688_queries(keywords: Sequence[str] = ()) -> list[str]:
    del keywords
    return [
        'site:16688.com.cn/shop "ChatGPT"',
        'site:16688.com.cn/shop "Claude"',
        'site:16688.com.cn/shop "Gemini"',
        'site:16688.com.cn/shop "Grok"',
        'site:16688.com.cn/shop "OpenAI"',
    ]
```

这里有两个关键问题。

## 问题 A：直接丢弃了传入 keywords

```python
del keywords
```

虽然：

```text
scripts/refresh_remote.sh
```

已经传入大量关键词，包括：

```text
gpt
chatgpt
chatgpt plus
chatgpt pro
openai api
codex
claude
gemini
grok
账号
成品号
代充
直充
卡密
兑换码
API
额度
...
```

但是这些关键词对 `bing_16688_queries()` 完全不起作用。

---

## 问题 B：16688 查询没有 Codex 和接码相关词

当前没有：

```text
Codex
接码
验证码
短信验证码
接马
验证
成品号
Plus
Pro
```

这与本项目当前最想发现的商品恰好错位。

---

# 9. P0：立即修改 16688 Bing 查询词

建议修改：

```text
crawler/ldxp/ldxp_crawler/source_discovery/keywords.py
```

第一版不要无限组合，保持固定、可测试、有预算上限。

建议：

```python
def bing_16688_queries(keywords: Sequence[str] = ()) -> list[str]:
    high_value_terms = [
        "ChatGPT",
        "Codex",
        "OpenAI",
        "Claude",
        "Gemini",
        "Grok",
        "ChatGPT Plus",
        "ChatGPT Pro",
        "Codex 接码",
        "接码",
        "验证码",
        "成品号",
    ]

    return [
        f'site:16688.com.cn/shop "{term}"'
        for term in high_value_terms
    ]
```

建议不要把所有 `all_keywords()` 做笛卡尔积。

原因：

- Bing RSS 有查询预算；
- 过多泛词会造成大量低价值结果；
- `API`、`账号` 单独查询噪声很大；
- Discovery 的核心是候选 URL，不是全文商品搜索。

---

# 10. 建议增加的 16688 搜索词

## 第一优先级

```text
ChatGPT
Codex
OpenAI
Claude
Gemini
Grok
```

## 第二优先级

```text
ChatGPT Plus
ChatGPT Pro
SuperGrok
Claude Pro
Gemini Advanced
OpenAI API
```

## 第三优先级：服务型商品

```text
Codex 接码
接码
验证码
短信验证码
成品号
代充
直充
```

不建议第一轮加入：

```text
API
账号
卡密
```

这种过宽单词作为单独查询。

---

# 11. Bing Adapter 不需要重写

文件：

```text
crawler/ldxp/ldxp_crawler/source_discovery/bing.py
```

当前已经会：

1. 调用 Bing RSS；
2. 多页搜索；
3. URL normalize；
4. 去重；
5. 生成 `DiscoveredCandidate`；
6. 自动设置 `platform_hint`；
7. 保存 `matched_query`。

所以本轮应优先只调整：

```text
keywords.py
tests
预算参数
```

不要因为召回低就重写整个 Bing Adapter。

---

# 12. Common Crawl 当前行为

文件：

```text
crawler/ldxp/ldxp_crawler/source_discovery/commoncrawl.py
```

已定义：

```python
CDX_PATTERNS = {
    "ldxp": ("pay.ldxp.cn/shop/*",),
    "16688": (
        "16688.com.cn/shop/*",
        "www.16688.com.cn/shop/*",
    ),
}
```

这条链路能找到历史被 Common Crawl 记录过的：

```text
/shop/{code}
```

但是必须明确：

> Common Crawl CDX 是 URL 索引，不是正文关键词搜索。

因此它只能回答：

```text
曾经有哪些 /shop/* URL
```

不能回答：

```text
这些店里谁卖 Codex
谁卖 ChatGPT
谁卖接码
```

后续 AI 商品相关性必须由 Detector / 商品 API / 分类器确认。

---

# 13. Common Crawl 的正确用途

正确：

```text
16688 /shop/* URL discovery
        ↓
Detector
        ↓
goods/list
        ↓
AI 分类
```

错误：

```text
Common Crawl 直接全文搜索“Codex 接码”
```

目前代码没有做 WARC 正文检索，也不应该伪装成已经支持。

---

# 14. Seed 是当前最高确定性的补充方式

统一 seed 文件：

```text
config/discovery/general_seeds.txt
```

生产调用：

```text
--seed-file /config/general_seeds.txt
```

当人工或外部公开索引发现一个 16688 店铺时，应只写官方 URL：

```text
https://www.16688.com.cn/shop/S755531
```

不要把第三方聚合页 URL 当成 Source。

第三方页面只作为：

```text
发现证据
```

最终进入 Detector 的必须是：

```text
16688 官方 shop URL
```

---

# 15. 第三方聚合站如何接入本项目

如果后续继续使用公开聚合站发现 16688 店铺，推荐做成：

```text
Public Aggregator Index
       │
       ▼
extract 16688 shop code
       │
       ▼
https://www.16688.com.cn/shop/{code}
       │
       ▼
SourceCandidate
       │
       ▼
Detector
       │
       ▼
16688 public API
```

绝对不要：

```text
第三方聚合站商品数据
       ↓
直接写 PostgreSQL
```

这样会绕过当前：

```text
Detector
SourceIntake
审核
Connector
Atomic Snapshot
```

破坏项目现有可信来源模型。

---

# 16. 可选 P1：新增 “Aggregator Reference Discovery Adapter”

只有在实际需要时再实现。

建议文件：

```text
crawler/ldxp/ldxp_crawler/source_discovery/aggregator_refs.py
```

职责只允许：

1. 读取明确 allowlist 的公开页面；
2. 提取明显的 16688 shop code；
3. 生成官方 URL；
4. 创建 `DiscoveredCandidate`；
5. 保存 `discovered_by`；
6. 保存 `matched_query`；
7. 不读取私人数据；
8. 不自动发布。

建议：

```text
platform_hint = 16688
```

生成：

```text
https://www.16688.com.cn/shop/{code}
```

然后交给 Detector。

---

# 17. 不要在当前阶段暴力枚举 shop code

现有项目安全边界已经明确：

- 不随机暴力枚举店铺 token；
- 不绕过 CAPTCHA；
- 不绕 WAF；
- 不通过代理轮换对抗限制；
- 只处理公开可访问商品。

所以禁止把：

```text
S000001
S000002
S000003
...
```

做全空间扫描。

Discovery 应继续使用：

```text
公共搜索索引
Common Crawl
种子
公开第三方引用
```

---

# 18. Goods 页面检索属于后续研究项

搜索引擎通常更容易索引商品页：

```text
/goods/{goods_no}
```

但当前项目的 16688 Detector 只对：

```text
/shop/{code}
```

有明确平台契约。

因此暂时不要直接把：

```text
site:16688.com.cn/goods "Codex"
```

结果塞进生产 Discovery。

只有先确认一个稳定、公开、可验证的：

```text
goods_no -> shop_no
```

映射方法后，才能实现：

```text
goods result
    ↓
resolve canonical shop
    ↓
SourceCandidate
```

该映射必须来自公开官方页面或公开官方 API，不能猜接口。

---

# 19. SourceCandidate 与状态机已经可复用

文件：

```text
apps/api/app/services/source_discovery.py
```

当前支持平台：

```text
unknown
ldxp
dujiao_next
merchant_json
woocommerce
16688
schema_org
other
```

可发布平台：

```text
dujiao_next
merchant_json
woocommerce
16688
schema_org
```

16688 自动批准配置：

```text
DISCOVERY_16688_AUTO_APPROVE
```

当前默认：

```text
false
```

这是正确默认值。

建议继续保留。

---

# 20. 16688 Candidate 去重与 canonicalization

Discovery 阶段：

```text
https://www.16688.com.cn/shop/HARVEY
```

可能只是 alias。

Detector 调用：

```text
/shopApi/shop/detail
```

后获得真实：

```text
shop_no
```

最终 canonical source 应使用：

```text
https://www.16688.com.cn/shop/{canonical_shop_no}
```

最终公开 token：

```text
16688-{canonical_shop_no}
```

因此后续实现必须继续以 Detector 的 canonical identity 为准，不要用搜索引擎返回的 alias 当最终主键。

---

# 21. 跨平台碰撞处理已经有测试

文件：

```text
pipeline/tests/test_connectors.py
```

已有测试验证：

即使 LDXP 已存在：

```text
S343514
```

16688 仍会保存为：

```text
16688-S343514
```

从而保持：

```text
LDXP Shop != 16688 Shop
```

注意：

测试里的：

```text
HARVEY -> S343514
```

是测试 fixture，不应作为生产真实店铺映射事实使用。

---

# 22. 生产 Discovery 当前调用方式

文件：

```text
scripts/refresh_remote.sh
```

当前：

```bash
run_crawler discover-sources \
  --db /data/ldxp_crawler.db \
  --seed-file /config/general_seeds.txt \
  --api-url "${DISCOVERY_API_URL:-http://api:8000}" \
  --sources "${DISCOVERY_SOURCES:-seed,bing,github,commoncrawl}" \
  --max-raw-urls "${DISCOVERY_MAX_RAW_URLS:-2000}" \
  --max-unique-candidates "${DISCOVERY_MAX_NEW_CANDIDATES:-1000}" \
  --request-interval "${DISCOVERY_REQUEST_INTERVAL_SECONDS:-2}" \
  --bing-pages "${DISCOVERY_BING_PAGES:-5}" \
  --bing-count "${DISCOVERY_BING_COUNT:-30}" \
  --cc-indexes "${DISCOVERY_COMMONCRAWL_INDEXES:-2}" \
  --cc-max-urls "${DISCOVERY_COMMONCRAWL_MAX_URLS:-500}" \
  --keywords "${KEYWORDS[@]}"
```

生产统一入口：

```bash
bash scripts/refresh_remote.sh discover
```

---

# 23. 本地开发冒烟方式

仓库已有 crawler-dev 只读挂载方式。

推荐：

```powershell
docker compose -f docker-compose.yml -f docker-compose.pricememo.yml `
  -f docker-compose.crawler-dev.yml run --no-build --rm crawler `
  discover-sources --sources seed --api-url http://api:8000 --worker-key dev-key
```

针对本次改动，建议先：

```text
seed
```

再：

```text
bing
```

最后：

```text
seed,bing,commoncrawl
```

不要一开始就用最大预算跑全源。

---

# 24. P0 开发任务

## P0-1 扩展 16688 Bing 查询

修改：

```text
crawler/ldxp/ldxp_crawler/source_discovery/keywords.py
```

必须覆盖：

```text
ChatGPT
Codex
Claude
Gemini
Grok
OpenAI
Codex 接码
接码
验证码
成品号
```

---

## P0-2 增加查询单元测试

文件优先：

```text
crawler/ldxp/tests/test_source_discovery.py
```

测试：

```text
bing_16688_queries()
```

至少断言：

```text
有 Codex
有 接码/验证码
有 ChatGPT
有 Claude
有 Gemini
有 Grok
所有查询仍限制 site:16688.com.cn/shop
无重复
```

---

## P0-3 增加 Discovery 指标观察

至少记录：

```text
raw URLs
unique candidates
16688 platform_hint candidates
Detector success
Detector no_match
Detector validation_failed
published
```

应能按：

```text
discovered_by
matched_query
```

比较每条 Bing query 的实际收益。

最终可以淘汰：

```text
零召回 / 高噪声 query
```

---

# 25. P1 开发任务

## P1-1 建立 16688 verified seed 集合

把已人工核验的官方 shop URL 放入：

```text
config/discovery/general_seeds.txt
```

原则：

```text
只存官方 16688 shop URL
```

不存：

```text
price aggregator URL
search result URL
截图 URL
聊天记录 URL
```

---

## P1-2 保存外部发现证据

若候选来自第三方公开索引：

建议记录：

```text
discovered_by
matched_query
public reference URL
first_seen_at
```

但公开站点最终展示来源仍应是：

```text
16688 official source_url
```

---

# 26. P2 研究任务

## P2-1 Goods → Shop 映射

目标：

```text
16688 /goods/{goods_no}
        ↓
canonical shop_no
```

先通过浏览器 Network / 官方前端公开请求确认。

如果有稳定公开契约，再增加：

```text
goods candidate resolver
```

不要猜 API。

---

## P2-2 第三方公开索引 Adapter

只有 P0/P1 召回仍明显不足时再做。

必须：

```text
allowlist
低频
只抓公开页
只生成候选
Detector 二次确认
不直接发布
```

---

# 27. 需要特别避免的错误实现

不要：

```text
❌ 为 16688 新建第二套数据库
❌ 直接把第三方聚合数据写入 Offer
❌ 用店名作为主键
❌ 用搜索结果 alias 作为永久 shop token
❌ 枚举 S000000～S999999
❌ 绕过验证码/WAF
❌ 把商品页直接当店铺页
❌ 关闭 Detector
❌ 开启 16688 自动批准作为默认值
❌ 绕过 Atomic Snapshot
```

应当：

```text
✅ Discovery 只负责找候选
✅ Detector 负责证明来源有效
✅ canonical shop_no 负责身份
✅ Connector 负责读取
✅ common.py 负责统一分类与入库
✅ Publisher 负责原子发布
```

---

# 28. 验收标准

## Discovery

- [ ] `bing_16688_queries()` 包含 Codex。
- [ ] 包含接码/验证码类查询。
- [ ] 所有 Bing 16688 query 仍限定在官方域名。
- [ ] 同 URL 不重复提交。
- [ ] 能保留 matched query 证据。
- [ ] Common Crawl 16688 `/shop/*` 仍正常工作。
- [ ] Seed 16688 URL 可进入候选池。

## Detector

- [ ] 非法 shop code 被拒绝。
- [ ] 非官方域名被拒绝。
- [ ] `shop/detail` 非成功返回被拒绝。
- [ ] `goods/list` 非法结构被拒绝。
- [ ] alias 能归一到 canonical shop number。

## Connector

- [ ] `source_platform=16688`。
- [ ] token 形如 `16688-{shop_no}`。
- [ ] product key 形如 `16688:{goods_no}`。
- [ ] CNY 正常保存。
- [ ] 库存状态正确映射。
- [ ] 商品原始信息进入 `raw_json`。

## Pipeline

- [ ] 同店重复导入幂等。
- [ ] 同商品重复导入幂等。
- [ ] 价格/库存变化才增加 history。
- [ ] 与 LDXP 相同 token 不碰撞。
- [ ] 失败来源不破坏上一完整 snapshot。

## Public Site

- [ ] `source_platform=16688` 可筛选。
- [ ] 店铺页能显示 16688 来源标签。
- [ ] 商品页可看到 16688 报价。
- [ ] 原始 16688 商品链接保留。

---

# 29. 建议优先级

```text
P0
├─ 扩 Bing 16688 查询词
├─ 增测试
└─ 加 Discovery 效果统计

P1
├─ 补 verified seeds
└─ 规范第三方公开证据 → 官方 shop URL

P2
├─ 研究 goods → shop 官方公开映射
└─ 必要时新增 aggregator reference adapter
```

---

# 30. 接收方第一步

接手后先看：

```text
RELEASE_NOTES_v3.7.14.md
docs/CONNECTORS.md
crawler/ldxp/ldxp_crawler/source_discovery/keywords.py
crawler/ldxp/ldxp_crawler/source_discovery/bing.py
crawler/ldxp/ldxp_crawler/source_discovery/commoncrawl.py
crawler/ldxp/ldxp_crawler/source_discovery/normalize.py
apps/api/app/services/source_discovery.py
detector/probe.py
pipeline/connectors/platform_16688.py
pipeline/tests/test_connectors.py
scripts/refresh_remote.sh
```

然后只做第一刀：

```text
扩展 bing_16688_queries()
+
补 test
+
本地只跑 Bing discovery
+
统计新增候选
```

确认有效后再扩大。

---

# 31. 一句话交接

> 16688 的 API 读取、标准化、验证、入库和发布已经完成；当前最需要解决的是 Discovery 召回率。第一优先级是扩展 `bing_16688_queries()` 到 Codex / 接码 / 验证码等高价值词，并通过现有 Detector 验证每个候选，绝不要另建一条绕过现有 Source Discovery 与 Atomic Publish 的数据通道。

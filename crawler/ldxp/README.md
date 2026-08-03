# 链动小铺 GPT / ChatGPT 店铺检索器 v2.0

本版本针对 v1 扫描阶段全部出现 HTTP 403 的问题重构。

核心变化：不再用 `requests` 伪造访客请求，而是启动真实 Chromium，先正常打开店铺页面并复用浏览器 Cookie、localStorage 和页面实际请求头，再在同一页面上下文中读取商品数据。

## 使用边界

- 只处理无需登录即可访问的公开店铺和公开商品信息。
- 不随机暴力枚举店铺 token。
- 不破解或自动绕过验证码、WAF、登录或访问控制。
- 出现验证页时，程序只等待用户在正常浏览器窗口中手动完成验证。
- “全部店铺”表示公共搜索索引、Common Crawl、可选 Wayback 和你的种子列表能够发现的集合，不代表平台内部真正全量。

---

## v2 主要优化

### 浏览器会话扫描

- 使用 Playwright Chromium。
- 持久化浏览器目录：`browser_profile/`。
- 保存会话快照：`browser_state.json`。
- 自动捕获页面真实调用的 `/shopApi/Shop/...` 请求模板。
- API 分页请求在浏览器页面上下文中执行，继承浏览器会话。
- 接口不可用时，尝试从页面中 `/item/` 商品链接提取基础数据。

### 风控与请求控制

- 使用全进程统一限速，不会因多线程把请求频率成倍放大。
- 默认连续 3 次出现阻断、验证或限流后熔断。
- 熔断后剩余候选保持原状态，不会全部写成失败。
- 首次验证默认等待 300 秒，可调整。

### 数据可靠性

- 临时 403、超时或网络错误不会删除上一次成功商品结果。
- 新增运行历史和商品快照表。
- 自动迁移 v1 SQLite 数据库。
- 候选店铺按来源评分排序：种子、当前搜索结果优先，Wayback 最低。
- 分页不再依赖“本页数量少于 pageSize”这一不可靠判断，而是综合空页、重复页和 total 字段停止。

### 导出安全

- 对以 `= + - @` 开头的第三方文本进行 Excel/CSV 公式注入防护。
- 只允许 `http` 和 `https` 地址成为 Excel 超链接。
- Excel 新增：
  - `运行摘要`
  - `匹配商品`
  - `命中店铺`
  - `全部候选`
  - `失败记录`
  - `运行历史`

---

## Windows 最简单使用方法

解压后双击：

## 日常开发与冒烟（不重建 Playwright 镜像）

完整构建一次 Crawler 镜像后，日常修改 `crawler/ldxp` 或 `shared_http` 源码时使用只读挂载运行，不需要重建镜像：

```powershell
docker compose -f docker-compose.yml -f docker-compose.pricememo.yml `
  -f docker-compose.crawler-dev.yml run --no-build --rm crawler --version

docker compose -f docker-compose.yml -f docker-compose.pricememo.yml `
  -f docker-compose.crawler-dev.yml run --no-build --rm crawler `
  discover-sources --sources seed --api-url http://api:8000 --worker-key dev-key
```

`docker-compose.crawler-dev.yml` 只读挂载 `crawler/ldxp` 到 `/app`、`shared_http` 到 `/shared_http`（通过 `PYTHONPATH` 优先生效），源码变更立即生效。只有 `requirements.txt`、Dockerfile、系统依赖变化或最终发布门禁时才执行完整构建。

```text
run_windows.bat
```

它会自动：

1. 创建 `.venv` 虚拟环境。
2. 安装 Python 依赖。
3. 安装 Playwright Chromium。
4. 发现候选店铺。
5. 打开 Chromium 扫描。
6. 导出 Excel 和 CSV。

首次安装 Chromium 需要下载浏览器组件。

### 首次遇到验证页

保持命令窗口和 Chromium 窗口打开，在 Chromium 中正常完成验证。程序检测到验证结束后会继续扫描，并把会话保存在：

```text
browser_profile/
browser_state.json
```

不要把验证 Cookie、浏览器目录或 `browser_state.json` 分享给其他人。

---

## 后续无头运行

只有在有头模式已经成功建立会话后，再双击：

```text
run_headless_windows.bat
```

会话过期或再次出现验证时，重新运行：

```text
bootstrap_windows.bat
```

它只打开 `seeds.txt` 中优先级最高的店铺，用来建立或刷新会话。

---

## 是否扫描 Wayback 历史店铺

默认不启用 Wayback，避免像 v1 一样让历史失效店铺占候选主体。

需要扩大历史覆盖范围时，双击：

```text
run_with_archives_windows.bat
```

历史候选来源评分低，会排在种子和当前搜索结果之后。

---

## 迁移 v1 数据

把旧版的：

```text
ldxp_crawler.db
```

复制到 v2 解压目录中，再运行 v2。程序会自动增加新字段和新表。

重要行为：如果旧数据库里有成功商品记录，后续临时扫描失败不会再删除这些记录。

v1 导出的 Excel/CSV 不能恢复成完整数据库；最好迁移 SQLite 文件。

---

## 手动安装

需要 Python 3.10 或更高版本。

```bash
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\activate
```

Linux/macOS：

```bash
source .venv/bin/activate
```

安装依赖和 Chromium：

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

---

## 常用命令

### 完整运行

```bash
python ldxp_gpt_crawler.py all \
  --keywords gpt chatgpt openai codex "gpt plus" "gpt team" \
  --seed-file seeds.txt \
  --sources seed,bing,commoncrawl \
  --request-interval 2.0 \
  --circuit-breaker 3
```

Windows CMD 把行尾 `\` 换成 `^`。

### 建立或刷新浏览器会话

```bash
python ldxp_gpt_crawler.py bootstrap --manual-challenge-seconds 600
```

### 无头扫描

```bash
python ldxp_gpt_crawler.py scan --headless
```

### 重新扫描之前成功过的店铺

```bash
python ldxp_gpt_crawler.py scan --rescan
```

### 重新尝试阻断或需要验证的店铺

建议先建立浏览器会话，然后：

```bash
python ldxp_gpt_crawler.py scan --retry-blocked
```

### 使用历史索引发现候选

```bash
python ldxp_gpt_crawler.py discover \
  --sources seed,bing,commoncrawl,wayback
```

### 发现 Dujiao-Next 候选

Dujiao-Next 使用独立候选表，不会进入 LDXP 浏览器扫描或自动发布链路。发现器只访问首页和公开商品列表 API，默认单线程、候选请求间隔 2 秒：

```text
python ldxp_gpt_crawler.py discover-dujiao --sources seed,bing --seed-file dujiao_seeds.txt --request-interval 2 --max-new-candidates 500 --max-processed-candidates 2000 --reverify-stale-hours 24
```

候选必须同时满足：

- `/api/v1/public/products` 返回合法公开数据；
- 公开商品数大于 0；
- 至少一个带 slug 的商品标题、分类或标签命中 AI 关键词；
- 不属于 `dujiao-next.com` 或其官方子域。

首页的 `Dujiao-Next` 和默认主题文字只作为辅助指纹；白标或自定义页脚不会阻止 API 契约完整、且包含 AI 商品的候选进入人工审核。首页和公开 API 均禁止自动重定向、按 64 KiB 分块读取，超过 5 MiB 会在下载过程中立即关闭响应。

`--max-new-candidates` 和 `--max-processed-candidates` 是单次运行额度，不读取历史候选总数。每次运行会先按 `--reverify-stale-hours` 复验过期候选；因此数据库累计超过 500 条后仍可发现新店和检查旧店。验证结果写入同一 SQLite 文件的 `dujiao_candidates` 表，只有本次验证符合门槛的 `review_status=pending_review` 记录会以 JSONL 输出供人工检查。

人工审核只记录决定，不创建公开 Shop、Offer 或 Snapshot：

```text
python ldxp_gpt_crawler.py review-dujiao --origin https://shop.example.com --decision approve --note "公开页面与商品已核对"
python ldxp_gpt_crawler.py review-dujiao --origin https://shop.example.com --decision reject --note "来源信息不足"
python ldxp_gpt_crawler.py review-dujiao --origin https://shop.example.com --decision disable --note "停止维护该来源"
```

审核状态限定为 `pending_review`、`approved`、`rejected`、`needs_re_review` 和 `disabled`。复验不会把 `rejected`、`disabled` 或 `needs_re_review` 自动提升为 `approved`；已批准来源若 API 契约失效、跨站重定向、过期复验时不可达、不再包含 AI 商品，或可识别的页面标题发生变化，会转为 `needs_re_review` 并记录原因。批准后仍需由操作员显式运行后续 dry-run 和发布流程，发现和审核命令本身不会创建公开 Shop、Offer 或 Snapshot。

Common Crawl 的公共 CDX 服务是 URL 索引，不是页面正文全文搜索。它可以补证已知域名的历史 URL，但不能通过增加一条 `Dujiao-Next` 文本指纹发现任意域名；全网正文检索需要单独的 URL Index/WARC 分析任务，因此未伪装成当前低频命令的一部分。

### 只扫描自己的 URL 列表

将链接逐行写入 `seeds.txt`：

```text
https://pay.ldxp.cn/shop/IRPBFS50
https://pay.ldxp.cn/shop/example
```

然后：

```bash
python ldxp_gpt_crawler.py all \
  --sources seed \
  --seed-file seeds.txt
```

### 重新导出

```bash
python ldxp_gpt_crawler.py export
```

---

## 扫描状态说明

| 状态 | 含义 | 默认是否自动重试 |
|---|---|---|
| `success` | 成功并命中关键词 | 否 |
| `partial_success` | 取得部分商品，但后续分页失败 | 否 |
| `no_match` | 成功扫描，但没有关键词命中 | 否 |
| `empty_shop` | 页面和接口均未取得商品 | 否 |
| `closed` | 检测到店铺暂停/关闭 | 否 |
| `network_error` | 网络或浏览器请求错误 | 延迟后重试 |
| `rate_limited` | HTTP 429 | 延迟后重试 |
| `parse_error` | 响应格式异常 | 延迟后重试 |
| `api_changed` | 接口 404 或结构疑似变化 | 延迟后重试 |
| `challenge_required` | 需要浏览器人工验证 | 需加 `--retry-blocked` |
| `blocked` | HTTP 403 等阻断 | 需加 `--retry-blocked` |

---

## 输出文件

```text
ldxp_crawler.db
output/
  ldxp_gpt_results_时间.xlsx
  ldxp_gpt_results_shops_时间.csv
  ldxp_gpt_results_products_时间.csv
```

`ldxp_crawler.db` 是断点续跑、运行历史和商品快照的主要数据文件，请定期备份。

---

## 自检

不访问目标网站的本地自检：

```bash
python self_test.py
```

它会验证：

- v1 数据库迁移。
- 成功结果写入。
- 临时失败不会删除成功商品。
- Excel 公式注入防护。
- 非 HTTP(S) 链接不会成为 Excel 超链接。
- 运行摘要导出。

---

## 建议参数

先保持低频：

```text
--request-interval 2.0
--circuit-breaker 3
```

不要通过提高并发、代理轮换或自动验证码处理来对抗网站访问控制。候选很多时，优先使用 `--limit` 分批运行：

```bash
python ldxp_gpt_crawler.py scan --limit 50
```

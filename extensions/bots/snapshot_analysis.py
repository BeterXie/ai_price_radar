"""Price and availability analysis calculated exclusively from a published snapshot."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import timezone
from decimal import Decimal
import re
from statistics import mean, median
from typing import Literal
import unicodedata

from app.services.catalog_vocabulary import DELIVERY_LABELS, PERIOD_LABELS
from app.services.snapshot_catalog import QuoteQuery, SnapshotCatalog, timestamp

AnalysisMetric = Literal["summary", "mean", "median", "minimum", "maximum", "range", "count", "stock", "shops", "freshness", "popularity", "catalog"]
PAGE_SIZE = 5
ACCESS_LABELS = {"exclusive": "独享", "shared": "共享", "unknown": "使用方式未注明"}
STOCK_LABELS = {"in_stock": "有货", "out_of_stock": "已售罄", "unknown": "库存未知"}


def unavailable_topic(text: str) -> str:
    """Never substitute a quote, stock change or click count for a completed sale."""
    if re.search(r"成交|实付|付款金额|支付金额|订单(?:价格|金额|记录|数据)|销量|卖出(?:了)?多少", text):
        return "transactions"
    if re.search(r"历史(?:价|报价|最低|最高|均价)|价格(?:走势|趋势)|(?:近|最近|过去)\s*(?:\d+|[一二三四五六七八九十两]+)\s*(?:天|周|个月)|昨天|上周|上个月|涨了|跌了|降了", text):
        return "history"
    return ""


def analysis_request(text: str) -> tuple[AnalysisMetric, str] | None:
    """Recognize common questions even when no model provider is enabled."""
    clean = unicodedata.normalize("NFKC", text).casefold()
    # Comparisons and numbered items already have a dedicated conversation flow.
    if re.search(r"比较|对比|第[一二三四五1-5](?:家|个|条)", clean):
        return None
    patterns = (
        ("popularity", r"热门(?:商品|套餐|产品)?|人气(?:商品|套餐|产品)?|点击(?:热度|排行|排名)|最受欢迎(?:的商品)?"),
        ("catalog", r"(?:有哪些|有什么)(?:商品|套餐|品牌|产品)|商品目录|品牌目录|商品种类"),
        ("mean", r"平均(?:报价|价格|价|数)?|均价"),
        ("median", r"(?:价格|报价)?中位数|中位价"),
        ("maximum", r"最高(?:报价|价格|价)?|最贵(?:的)?"),
        ("minimum", r"最低(?:报价|价格|价)?|最便宜(?:的)?"),
        ("range", r"价差|价格区间|价格范围|报价区间|差价"),
        ("stock", r"库存(?:情况|统计|分布|数量|多少|怎么样|如何)?|有货(?:的)?(?:有)?(?:多少|几)(?:家|条|个)?|缺货率|有货率"),
        ("shops", r"(?:有)?(?:多少|几)家(?:店铺|店|商家)?|(?:有)?哪些(?:店铺|商家|店)(?:有卖|在卖)?|店铺(?:统计|分布|数量)|商家(?:统计|分布|数量)"),
        ("count", r"(?:有)?(?:多少|几)(?:条报价|款商品|个商品|个报价)|报价数量|商品数量|报价(?:一共)?有多少"),
        ("freshness", r"(?:什么时候|何时|多久)(?:更新|采集)|(?:数据|快照|报价)(?:更新时间|新鲜度)|最新采集时间"),
        ("summary", r"分析(?:一下)?|价格分布|报价分布|贵不贵|价格合理(?:吗)?|价格情况|价格如何"),
    )
    matches = [(metric, pattern) for metric, pattern in patterns if re.search(pattern, clean)]
    if not matches:
        return None
    metric = matches[0][0] if len(matches) == 1 else "summary"
    for _, pattern in matches:
        clean = re.sub(pattern, " ", clean)
    clean = re.sub(r"我想(?:看|知道|了解)|想(?:看看|了解)|帮我(?:看看|看|了解)?|给我|告诉我|请问|请|能不能|能否|可以|看看|看一下|查看|一下|是多少|有多少|多少|怎么样|如何|现在|目前|最近|这款商品|这个商品|该商品|这款|这个|它|那么|以及|还有|分别|各自|和", " ", clean)
    clean = re.sub(r"^有(?=\s)", "", clean)
    clean = re.sub(r"本网站|本站|站内|全站|网站|这里", " ", clean)
    clean = re.sub(r"[，,。.!！?？、:：;；()（）的呢吧吗]", " ", clean)
    return metric, " ".join(clean.split())


@dataclass
class AnalysisReply:
    text: str
    page: int = 0
    shown_ids: tuple[int, ...] = ()
    shown_products: tuple[str, ...] = ()


def _money(price: Decimal, currency: str) -> str:
    return f"{'¥' if currency == 'CNY' else currency + ' '}{price:.2f}"


def _shop(offer: dict) -> str:
    return offer["shop_token"] or offer["shop_name"]


def _group_key(row: tuple[dict, dict]) -> tuple:
    product, offer = row
    return (product["slug"], offer["currency"], offer["delivery_type"], offer["service_period"], offer["account_access"])


def _population(catalog: SnapshotCatalog, query: QuoteQuery, *, all_currencies: bool = False) -> list[tuple[dict, dict]]:
    # Keep each shop's quote; search() chooses the cheapest representative across shops.
    rows = catalog.matching_rows(replace(query, related=True, currency=query.currency or ("" if all_currencies else "CNY")))
    unique = {}
    for row in sorted(rows, key=lambda item: (timestamp(item[1]["observed_at"]), item[1]["id"]), reverse=True):
        offer = row[1]
        key = (*_group_key(row), _shop(offer), offer.get("item_fingerprint") or str(offer["id"]), offer["warranty"])
        unique.setdefault(key, row)
    return list(unique.values())


def _price_rows(rows: list[tuple[dict, dict]], query: QuoteQuery) -> list[tuple[dict, dict]]:
    return [(product, offer) for product, offer in rows if (
        offer["is_trusted_price"] and offer["is_comparable"]
        and offer["currency"] == (query.currency or "CNY")
        and offer["stock_status"] == (query.stock or "in_stock")
        and offer.get("price") is not None and Decimal(str(offer["price"])) > 0
    )]


def render_analysis(catalog: SnapshotCatalog, query: QuoteQuery, metric: AnalysisMetric, page: int = 0) -> AnalysisReply:
    all_currencies = metric in {"popularity", "catalog", "count", "stock", "shops", "freshness"}
    population = _population(catalog, query, all_currencies=all_currencies)
    eligible = _price_rows(population, query)
    product = catalog.products.get(query.product)
    title = product["display_name"] if product else query.brand or "本站商品"
    titles = {"summary": "商品分析", "mean": "平均报价", "median": "报价中位数", "minimum": "最低报价", "maximum": "最高报价", "range": "报价区间", "count": "报价数量", "stock": "库存分析", "shops": "店铺分布", "freshness": "数据更新时间", "popularity": "热门商品", "catalog": "商品目录"}
    lines = [f"📊【{title} · {titles[metric]}】", f"快照 #{catalog.id} · {catalog.published_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"]
    footer = "可继续问：平均价、最高价、热门商品、库存；也可只看月付、下一页、查看报价。"
    catalog_products = {slug: item for slug, item in catalog.products.items() if (
        (not query.product or slug == query.product) and (not query.brand or item["brand"] == query.brand)
    )} if metric == "catalog" and not any((query.terms, query.delivery, query.access, query.period, query.warranty, query.stock, query.currency, query.min_price is not None, query.max_price is not None)) else {}
    if not population and not catalog_products:
        return AnalysisReply("\n".join([*lines, "当前快照没有符合筛选条件的报价，无法统计。", "可更换商品或放宽筛选条件。"]))

    shops = {_shop(offer) for _, offer in population}
    currency_scope = query.currency or ("全部币种" if all_currencies else "CNY")
    lines.append(f"匹配 {len(population)} 条店铺报价 / {len(shops)} 家店 · {currency_scope}；同店同款重复记录取最新一条。")
    if metric in {"summary", "stock", "count"}:
        stocks = Counter(offer["stock_status"] for _, offer in population)
        lines.append(f"有货 {stocks['in_stock']} 条 · 已售罄 {stocks['out_of_stock']} 条 · 库存未知 {stocks['unknown']} 条。")
        if metric == "summary" and eligible:
            covered = sum(offer["warranty"] not in {"none", "unknown"} for _, offer in eligible)
            lines.append(f"价格样本中 {covered}/{len(eligible)} 条注明质保；质保不等于会员使用期限。")
    if metric == "stock":
        unknown_count = sum(offer.get("stock_count") is None for _, offer in population if offer["stock_status"] == "in_stock")
        lines.append(f"有货报价中 {unknown_count} 条未注明库存件数；库存变化不能证明销量或成交。")
        return AnalysisReply("\n".join([*lines, footer]))
    if metric == "freshness":
        observed = [timestamp(offer["observed_at"]) for _, offer in population]
        lines.extend([f"最新观测：{max(observed).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", f"最早观测：{min(observed).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "发布时间与商品观测时间不同；已按快照有效期剔除过期报价。"])
        return AnalysisReply("\n".join([*lines, footer]))

    sections: list[list[str]] = []
    representatives: list[int | None] = []
    product_positions: list[str] = []
    if metric == "popularity":
        if any("click_count" not in offer for _, offer in population):
            return AnalysisReply("\n".join([*lines, "这份快照未提供完整的站内点击数据，无法可靠排列热门商品。不能用报价数量或库存猜测热度。", footer]))
        by_product = defaultdict(list)
        for row in population:
            by_product[row[0]["slug"]].append(row)
        ranked = sorted(by_product.items(), key=lambda item: (-sum(offer["click_count"] for _, offer in item[1]), item[0]))
        ranked = [(slug, rows) for slug, rows in ranked if sum(offer["click_count"] for _, offer in rows) > 0]
        if not ranked:
            return AnalysisReply("\n".join([*lines, "这些商品尚无有效点击记录，暂时没有可排序的热门榜。", footer]))
        lines.append("按当前公开报价的站内累计点击次数排序；这不是销量，也不是最近几天的点击榜。")
        for slug, rows in ranked:
            clicks = sum(offer["click_count"] for _, offer in rows)
            in_stock = sum(offer["stock_status"] == "in_stock" for _, offer in rows)
            sections.append([f"{catalog.products[slug]['display_name']}：{clicks} 次累计点击，{len(rows)} 条报价（有货 {in_stock} 条）。"])
            representatives.append(None)
            product_positions.append(slug)
    elif metric == "catalog":
        by_product = defaultdict(list)
        for slug in catalog_products:
            by_product[slug] = []
        for row in population:
            by_product[row[0]["slug"]].append(row)
        for slug, rows in sorted(by_product.items()):
            item = catalog.products[slug]
            in_stock = sum(offer["stock_status"] == "in_stock" for _, offer in rows)
            sections.append([f"{item['display_name']} · {item['brand']}：{len(rows)} 条报价，有货 {in_stock} 条。"])
            representatives.append(None)
            product_positions.append(slug)
        lines.append("目录展示当前筛选范围内的套餐；零报价表示暂未收录可展示报价。可继续指定套餐查询或比较。")
    elif metric == "shops":
        by_shop = defaultdict(list)
        for row in population:
            by_shop[_shop(row[1])].append(row)
        for _, rows in sorted(by_shop.items(), key=lambda item: (-len(item[1]), item[0])):
            in_stock = sum(offer["stock_status"] == "in_stock" for _, offer in rows)
            sections.append([f"{rows[0][1]['shop_name']}：{len(rows)} 条报价，有货 {in_stock} 条。"])
            representatives.append(None)
    elif metric == "count":
        counts = Counter(item[0]["slug"] for item in population)
        lines.append(f"覆盖 {len(counts)} 个套餐；其中 {len(eligible)} 条通过价格校验并符合价格统计的库存条件。")
        for slug, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            sections.append([f"{catalog.products[slug]['display_name']}：{count} 条报价。"])
            representatives.append(None)
            product_positions.append(slug)
    else:
        lines.append(f"价格统计取 {len(eligible)} 条通过校验的可比{STOCK_LABELS.get(query.stock or 'in_stock', '指定库存')}报价，不按销量加权。")
        if not eligible:
            return AnalysisReply("\n".join([*lines, "没有符合条件的有效价格样本，不使用缺价或未通过校验的报价计算均价。", footer]))
        groups = defaultdict(list)
        for row in eligible:
            groups[_group_key(row)].append(row)
        ordered = sorted(groups.items())
        if metric in {"minimum", "maximum"}:
            extreme = min if metric == "minimum" else max
            ordered.sort(key=lambda item: extreme(Decimal(str(offer["price"])) for _, offer in item[1]), reverse=metric == "maximum")
        lines.append("按套餐、币种、交付方式、使用期限和共享/独享分别统计。")
        for (_, currency, delivery, period, access), rows in ordered:
            prices = [Decimal(str(offer["price"])) for _, offer in rows]
            low, high, avg, middle = min(prices), max(prices), mean(prices), median(prices)
            label = " · ".join([rows[0][0]["display_name"], DELIVERY_LABELS.get(delivery, delivery), PERIOD_LABELS.get(period, period), ACCESS_LABELS.get(access, "使用方式未注明")])
            section = [label, f"{len(rows)} 条价格样本 / {len({_shop(offer) for _, offer in rows})} 家店"]
            representative = None
            if metric in {"minimum", "maximum"}:
                selected = (min if metric == "minimum" else max)(rows, key=lambda row: Decimal(str(row[1]["price"])))
                offer = selected[1]
                section.append(f"{titles[metric]} {_money(Decimal(str(offer['price'])), currency)} @ {offer['shop_name']}")
                section.append(offer["original_name"][:100])
                if offer.get("source_url"):
                    section.append(offer["source_url"])
                representative = offer["id"]
            else:
                if metric in {"summary", "mean", "median"}:
                    section.append(f"平均报价 {_money(avg, currency)} · 中位数 {_money(middle, currency)}")
                if metric in {"summary", "range"}:
                    section.append(f"最低 {_money(low, currency)} · 最高 {_money(high, currency)} · 价差 {_money(high - low, currency)}")
            if len(rows) == 1:
                section.append("仅 1 条样本，不能据此判断市场水平。")
            sections.append(section)
            representatives.append(representative)
        if any(key[3] == "unknown" or key[4] == "unknown" for key in groups):
            lines.append("期限或使用方式未注明的分组仅反映报价分布，不能视为完全同款。")
        lines.append("报价不代表实际成交价；价差也不能单独证明商家可靠或商品更划算。")

    total_pages = max(1, (len(sections) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    lines.append(f"第 {page + 1}/{total_pages} 页 · 共 {len(sections)} 组")
    shown = []
    for position, (section, identifier) in enumerate(zip(sections[start:start + PAGE_SIZE], representatives[start:start + PAGE_SIZE]), 1):
        if identifier is not None:
            shown.append(identifier)
            section[0] = f"{len(shown)}. {section[0]}"
        elif product_positions:
            section[0] = f"{position}. {section[0]}"
        lines.extend(["", *section])
    if product_positions:
        lines.append("可说“第一个”查看该套餐，也可继续追问它的均价、库存或筛选条件。")
    lines.extend(["", footer])
    return AnalysisReply("\n".join(lines), page, tuple(shown), tuple(product_positions[start:start + PAGE_SIZE]))

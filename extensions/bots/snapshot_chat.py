"""Deterministic conversational search over the published quote snapshot."""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from difflib import get_close_matches

from app.services.catalog_vocabulary import (
    BRAND_GROUPS, DELIVERY_LABELS, PERIOD_LABELS, PRODUCT_ALIASES, WARRANTY_LABELS, normalize_search,
)
from app.services.snapshot_catalog import QuoteQuery, SnapshotCatalog, SnapshotUnavailable, snapshot_store, timestamp
from .price_assistant import AIUnavailable, CLARIFICATIONS, EXPLANATIONS, price_assistant
from .snapshot_analysis import analysis_request, render_analysis, unavailable_topic

PAGE_SIZE = 5
SESSION_TTL = 30 * 60
MAX_SESSIONS = 1000
SITE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://ai.pricememo.cn").rstrip("/")
AMOUNT = r"(?<![\d.])(\d+(?:\.\d{1,2})?)(?![\d.])"
MONEY_UNIT = r"\s*(?:元|块|美元|美金|usd|人民币|rmb|cny)?\s*"
PRICE_RANGE = r"(?:预算\s*)?" + AMOUNT + MONEY_UNIT + r"(?:到|至|[-~～])\s*" + AMOUNT + MONEY_UNIT
PRICE_BOUNDS = (
    (r"(?:不超过|最多|预算|上限|<=|≤)\s*" + AMOUNT + MONEY_UNIT + r"(?:以内|以下|封顶)?", "max_price", 0),
    (AMOUNT + MONEY_UNIT + r"(?:以内|以下|封顶)", "max_price", 0),
    (r"(?:低于|不到|小于|<)\s*" + AMOUNT + MONEY_UNIT, "max_price", -1),
    (r"(?:不少于|至少|下限|>=|≥)\s*" + AMOUNT + MONEY_UNIT, "min_price", 0),
    (AMOUNT + MONEY_UNIT + r"(?:以上|起)", "min_price", 0),
    (r"(?:高于|超过|大于|>)\s*" + AMOUNT + MONEY_UNIT, "min_price", 1),
)


@dataclass
class SearchSession:
    query: QuoteQuery
    snapshot_id: str
    page: int = 0
    shown_ids: tuple[int, ...] = ()
    touched: float = 0
    analysis_metric: str = ""
    shown_products: tuple[str, ...] = ()


class QueryError(ValueError):
    pass


def _alias_match(text: str, alias: str) -> re.Match | None:
    pattern = r"\s*".join(re.escape(char) for char in alias)
    if alias.isascii() and len(alias) <= 3:
        pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
    return re.search(pattern, text)


def parse_query(text: str, catalog: SnapshotCatalog, previous: QuoteQuery | None = None) -> QuoteQuery:
    rest = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    refining = bool(re.match(r"^(?:只看|只要|仅看|仅要|筛选|再看|换成|改成)", rest))
    rest = re.sub(r"^(?:请\s*|麻烦\s*)?(?:(?:帮我|给我)\s*)?(?:查询|搜索|比价|价格|找一下|查一下|找个|找|查|搜|看看|看一下|我想买|我要买|买|换成|改成|改查)\s*", "", rest)
    # Budget numbers must not become tier names (e.g. Pro + 100元以内 vs Pro 100).
    subject = rest
    for pattern in (PRICE_RANGE, *(pattern for pattern, _, _ in PRICE_BOUNDS)):
        subject = re.sub(pattern, " ", subject)
    aliases = {alias: {slug} for alias, slug in PRODUCT_ALIASES.items()}
    aliases.update(catalog.aliases)
    brand_alias = next((a for a in sorted(catalog.brands, key=len, reverse=True) if _alias_match(subject, a)), "")
    brand = catalog.brands.get(brand_alias, "")
    # A brand on its own is an overview, even if it is also a historical product alias.
    match = None if normalize_search(subject) in catalog.brands else next((
        alias for alias in sorted(aliases, key=len, reverse=True)
        if alias not in catalog.brands and _alias_match(subject, alias)
        and (not brand or _alias_match(alias, brand_alias) or any(catalog.products.get(slug, {}).get("brand") == brand for slug in aliases[alias]))
    ), None)
    product = ""
    if match:
        candidates = aliases[match]
        if len(candidates) > 1 and brand:
            candidates = {slug for slug in candidates if catalog.products.get(slug, {}).get("brand") == brand}
        if len(candidates) != 1:
            raise QueryError("这个名称对应多个商品，请补充品牌或完整套餐名称。")
        product = next(iter(candidates))
        span = _alias_match(rest, match)
        rest = rest[:span.start()] + " " + rest[span.end():]
    if brand_alias:
        span = _alias_match(rest, brand_alias)
        if span:
            rest = rest[:span.start()] + " " + rest[span.end():]
    if product:
        # A service named after a brand may belong to a separate service category.
        brand = catalog.products.get(product, {}).get("brand", "")
    # Explicit subjects start a new search; filter-only messages refine the previous one.
    query = QuoteQuery(product=product, brand=brand) if product or brand else replace(previous) if previous else QuoteQuery()
    changed = bool(product or brand)

    if re.search(r"不限价格|取消预算|不限预算", rest):
        query.min_price = query.max_price = None
        rest = re.sub(r"不限价格|取消预算|不限预算", "", rest)
        changed = True
    if re.search(r"美元|美金|usd|\$", rest):
        query.currency = "USD"
        rest = re.sub(r"美元|美金|usd|\$", "元", rest)
        changed = True
    elif re.search(r"人民币|rmb|cny|[¥￥]", rest):
        query.currency = "CNY"
        rest = re.sub(r"人民币|rmb|cny|[¥￥]", "元", rest)
        changed = True
    interval = re.search(PRICE_RANGE, rest)
    if interval:
        query.min_price, query.max_price = map(Decimal, interval.groups())
        rest = rest.replace(interval.group(), "", 1)
        changed = True
    else:
        for pattern, field, adjustment in PRICE_BOUNDS:
            bound = re.search(pattern, rest)
            if bound:
                setattr(query, field, Decimal(bound[1]) + Decimal(adjustment) / 100)
                rest = rest.replace(bound.group(), "", 1)
                changed = True
    if query.min_price is not None or query.max_price is not None:
        query.currency = query.currency or "CNY"
    if query.min_price is not None and query.max_price is not None and query.min_price > query.max_price:
        raise QueryError("价格下限高于上限，请重新给出预算范围，例如“50到100元”。")

    for field, pattern in (("access", r"不限共享|不限独享|取消独享|不限使用方式"), ("period", r"不限周期|取消周期"), ("delivery", r"不限交付|取消交付"), ("warranty", r"不限质保|取消质保"), ("stock", r"不限库存|包括缺货")):
        if re.search(pattern, rest):
            setattr(query, field, "")
            rest = re.sub(pattern, "", rest)
            query.related = query.related or field == "stock"
            changed = True
    options = (
        ("access", {"exclusive": r"不要共享|排除共享|非共享|不共享|独享|独立账号", "shared": r"共享|拼车|号池"}),
        ("warranty", {"none": r"无质保|不要质保", "subscription_term": r"全程质保|全保|订阅期质保", "first_login": r"首登质保", "seven_days": r"7天质保|七天质保", "three_days": r"3天质保|三天质保", "one_day": r"24小时质保|1天质保|一天质保", "one_hour": r"1小时质保|一小时质保", "covered": r"有质保|带质保|要质保"}),
        ("period", {"one_year": r"年付|年卡|一年|12个月|365天", "six_months": r"半年|6个月|六个月", "three_months": r"季付|季卡|3个月|三个月", "one_month": r"月付|月卡|包月|一个月|1个月|30天", "one_week": r"周付|周卡|一周|7天", "one_day": r"日付|日卡|一天|1天|日抛"}),
        ("delivery", {"relay_api": r"中转站|中转|反代|relay", "semi_finished_account": r"半成品|首登号", "finished_account": r"成品账号|成品号|成品", "subscription_recharge": r"直充|代充", "team_seat": r"团队席位|车位", "card_code": r"卡密|兑换码|cdk", "session_token": r"session|会话令牌", "verification_service": r"接码服务|验证服务|接码", "api_credit": r"api额度", "account": r"账号|账户"}),
        ("stock", {"out_of_stock": r"已售罄|缺货|无货", "in_stock": r"有货|现货"}),
    )
    for field, values in options:
        for value, pattern in values.items():
            if re.search(pattern, rest):
                setattr(query, field, value)
                rest = re.sub(pattern, "", rest)
                changed = True
                break
    if re.search(r"所有报价|全部报价|相关报价", rest):
        query.related = True
        rest = re.sub(r"所有报价|全部报价|相关报价", "", rest)
        changed = True
    if re.search(r"不要|排除|不看|不买|不是|取消|不限|(?:^|\s)[不非](?:\s|$)", rest):
        raise QueryError("暂不支持这个排除条件，请改成明确条件，例如“只看月付”或“清除筛选”。")
    rest = re.sub(r"只看|只要|仅看|仅要|筛选|再看|按价格排序|从低到高|最便宜|最低价|便宜的|报价|多少钱|价格|有没有|有吗|推荐|给我|帮我|想要|我想|要个|买个", "", rest)
    rest = re.sub(r"(?<!\S)元(?!\S)", "", rest)
    rest = re.sub(r"[，,。.!！?？、:：;；()（）的呢吧吗]", " ", rest).strip()
    terms = tuple(normalize_search(term) for term in rest.split() if term)
    if terms:
        # A new free-text search must not accidentally inherit an unrelated earlier subject.
        if previous and not changed and not refining:
            query = QuoteQuery()
        query.terms = tuple(dict.fromkeys((*query.terms, *terms))) if previous and refining and not product and not brand else terms
    if not (query.product or query.brand or query.terms or changed or previous):
        raise QueryError("请告诉我商品或筛选条件，例如“Claude Pro 月付，100元以内”。")
    return query


def _price(offer: dict) -> str:
    if offer.get("price") is None:
        return "价格未注明"
    currency = offer.get("currency", "CNY")
    return f"{'¥' if currency == 'CNY' else currency + ' '}{Decimal(str(offer['price'])):.2f}"


def _stock(offer: dict) -> str:
    if offer["stock_status"] == "out_of_stock":
        return "已售罄"
    if offer["stock_status"] != "in_stock":
        return "库存状态未注明"
    count = offer.get("stock_count")
    return f"库存 {count} 件" if count is not None else "有货，库存数未注明"


def _terms(offer: dict) -> str:
    parts = [DELIVERY_LABELS.get(offer["delivery_type"], "形态待确认"), PERIOD_LABELS.get(offer["service_period"], "期限未注明"), WARRANTY_LABELS.get(offer["warranty"], "质保未注明")]
    if offer.get("account_access") == "exclusive":
        parts.append("独享")
    elif offer.get("account_access") == "shared":
        parts.append("共享")
    return " / ".join(parts)


def _conditions(query: QuoteQuery) -> str:
    parts = [*query.terms]
    for value, labels in ((query.access, {"exclusive": "独享", "shared": "共享"}), (query.delivery, {**DELIVERY_LABELS, "account": "账号（成品 / 半成品）"}), (query.period, PERIOD_LABELS), (query.warranty, {**WARRANTY_LABELS, "covered": "有质保"}), (query.stock, {"in_stock": "有货", "out_of_stock": "已售罄"})):
        if value:
            parts.append(labels.get(value, value))
    currency = query.currency or "CNY"
    if query.currency and query.min_price is None and query.max_price is None:
        parts.append(currency)
    if query.related:
        parts.append("全部公开报价")
    if query.min_price is not None:
        parts.append(f"≥{query.min_price} {currency}")
    if query.max_price is not None:
        parts.append(f"≤{query.max_price} {currency}")
    return "，".join(parts)


def render_results(catalog: SnapshotCatalog, session: SearchSession) -> str:
    query = session.query
    rows = catalog.search(query)
    product = catalog.products.get(query.product)
    session.shown_ids = ()
    if query.product and product is None:
        return "未找到该商品的公开分类，请更换商品名称。"
    # Related-only categories remain discoverable, but never advertised as a comparable minimum.
    if not rows and product and product["comparable_offer_count"] == 0 and not query.includes_related:
        rows = catalog.search(replace(query, related=True))
    is_related = query.includes_related or any(not row[1].get("is_trusted_price") for row in rows)
    title = product["display_name"] if product else query.brand or "商品搜索"
    lines = [f"📦【{title}】"]
    conditions = _conditions(query)
    if conditions:
        lines.append(conditions)
    if not rows:
        session.shown_ids = ()
        lines.append("当前快照中未找到符合条件的报价。" if conditions else "暂无通过价格校验的可比现货报价。")
        if not product and query.terms:
            suggestions = get_close_matches("".join(query.terms), catalog.aliases, n=3, cutoff=0.7)
            if suggestions:
                lines.append("可以试试：" + "、".join(suggestions))
        return "\n".join(lines)
    session.page = max(0, min(session.page, (len(rows) - 1) // PAGE_SIZE))
    page_rows = rows[session.page * PAGE_SIZE:(session.page + 1) * PAGE_SIZE]
    session.shown_ids = tuple(row[1]["id"] for row in page_rows)
    if is_related:
        lines.append("相关商品报价（不纳入可比最低价）")
    else:
        lines.append(f"最低在售: {_price(rows[0][1])}")
    lines.append(f"共 {len(rows)} 组，同款合并 · 第 {session.page + 1}/{(len(rows) + PAGE_SIZE - 1) // PAGE_SIZE} 页")
    for index, (item, offer) in enumerate(page_rows, 1):
        lines.append(f"{index}. {_price(offer)} @ {offer['shop_name']}（{_stock(offer)}）")
        lines.append(f"   {item['display_name']} · {offer['original_name']}")
        lines.append(f"   {_terms(offer)}")
    if product:
        lines.append(f"{SITE_URL}/products/{product['slug']}" + ("?comparable=false" if is_related else ""))
    lines.append("可继续说：只看月付、100元以内、下一页、第二家、清除筛选。")
    return "\n".join(lines)


def render_overview(catalog: SnapshotCatalog, brand: str = "") -> str:
    title = BRAND_GROUPS.get(brand, {}).get("title", f"{brand} 商品报价") if brand else "PriceMemo AI 服务大盘行情"
    lines = [f"📊【{title}】"]
    for product in catalog.products.values():
        if brand and product["brand"] != brand:
            continue
        rows = catalog.search(QuoteQuery(product=product["slug"]))
        if rows:
            offer = rows[0][1]
            label = f"最低: {_price(offer)}" if brand else f"最低 {_price(offer)}"
            lines.append(f"{product['display_name']}: {label} · {offer['shop_name']}（{_stock(offer)}）")
        else:
            lines.append(f"{product['display_name']}: 暂无通过价格校验的可比现货报价")
    if brand in BRAND_GROUPS:
        lines.append(BRAND_GROUPS[brand]["hint"])
    return "\n".join(lines)


def render_comparison(rows: list[tuple[dict, dict]]) -> str:
    lines = ["商品比较（当前公开报价）"]
    for index, (product, offer) in enumerate(rows, 1):
        lines.extend([
            f"{index}. {product['display_name']} · {offer['shop_name']}",
            f"   {_price(offer)} · {_stock(offer)}", f"   {_terms(offer)}",
            f"   {offer['original_name']}",
            f"   {offer.get('source_url') or SITE_URL + '/products/' + product['slug']}",
        ])
    comparable = len(rows) >= 2 and all(
        offer.get("is_trusted_price") and offer.get("is_comparable") and offer.get("price") is not None
        and offer["stock_status"] == "in_stock" and offer["service_period"] != "unknown" for _, offer in rows
    ) and len({(p["slug"], o["currency"], o["service_period"]) for p, o in rows}) == 1
    if comparable:
        cheapest = min(range(len(rows)), key=lambda i: Decimal(str(rows[i][1]["price"])))
        price = Decimal(str(rows[cheapest][1]["price"]))
        differences = [Decimal(str(o["price"])) - price for _, o in rows]
        if any(differences):
            lines.append(f"相同套餐、币种和使用期限下，第 {cheapest + 1} 项报价最低。")
        else:
            lines.append("这几项报价相同，可以继续比较交付方式和质保。")
    elif len(rows) >= 2:
        lines.append("套餐、币种或期限不同/未注明，或包含缺货、库存未知及非可比报价，不能直接按金额判断哪项更划算。")
    for delivery, topic in (("semi_finished_account", "semi_finished"), ("subscription_recharge", "recharge"), ("trial_account", "trial"), ("session_token", "token")):
        if any(o["delivery_type"] == delivery for _, o in rows):
            lines.append(EXPLANATIONS[topic])
    lines.append("价格与库存以店铺下单页为准；商品条款不代表平台保证商家信誉。")
    return "\n".join(lines)


class SnapshotChat:
    def __init__(self):
        self.sessions: OrderedDict[tuple, SearchSession] = OrderedDict()
        self.lock = threading.Lock()

    def _remember(self, key, session: SearchSession) -> None:
        if key:
            self.sessions[key] = session
            self.sessions.move_to_end(key)
            while len(self.sessions) > MAX_SESSIONS:
                self.sessions.popitem(last=False)

    def reply(self, text: str, *, sender_id: str = "", channel: str = "qq", account_id: str = "", conversation_id: str = "c2c", use_ai: bool = False) -> str:
        try:
            catalog = snapshot_store.load()
        except SnapshotUnavailable as exc:
            return str(exc)
        if datetime.now(timezone.utc) - catalog.published_at > catalog.max_age:
            return "当前报价快照已过期，请等待价格同步后再查询。"
        key = (channel, account_id, conversation_id, sender_id) if sender_id else None
        if len(text) > 500:
            return "搜索内容太长，请用 500 字以内的商品名称和筛选条件查询。"
        raw_text = text
        text = normalize_search(text)
        topic = unavailable_topic(raw_text)
        if topic:
            return EXPLANATIONS[topic]
        analysis = analysis_request(raw_text)
        plan = None
        fallback_note = ""
        controls = {"重新搜索", "重置搜索", "结束查询", "行情", "大盘", "概况", "市场", "价格", "汇总", "下一页", "上一页", "清除筛选", "取消筛选", "再便宜点", "更便宜的", "查看报价", "报价列表"}
        detail_pattern = r"(?:看看|查看|看)?第?([1-5一二三四五])(?:家|个|条)(?:详情|怎么样|多少钱|呢)?"
        if use_ai and text not in controls and not re.fullmatch(detail_pattern, text) and text not in catalog.aliases and text not in catalog.brands:
            with self.lock:
                original = self.sessions.get(key) if key else None
                if original and time.monotonic() - original.touched >= SESSION_TTL:
                    original = None
                context = replace(original, query=replace(original.query)) if original else None
            # Release the global session lock before model I/O; quote lookup uses only the snapshot.
            try:
                plan = price_assistant.plan(raw_text, catalog, context, key)
                if plan:
                    catalog = snapshot_store.load()
                    if datetime.now(timezone.utc) - catalog.published_at > catalog.max_age:
                        return "当前报价快照已过期，请等待价格同步后再查询。"
                    plan.validate_for(catalog, context.query if context else None)
            except SnapshotUnavailable as exc:
                return str(exc)
            except (AIUnavailable, ValueError):
                fallback_note = "AI 暂时不可用，以下根据已识别的条件查询快照；可直接指定商品、预算，或询问均价、热门和库存。\n"
                plan = None
        with self.lock:
            now = time.monotonic()
            for expired in [k for k, v in self.sessions.items() if now - v.touched >= SESSION_TTL]:
                del self.sessions[expired]
            previous = self.sessions.get(key) if key else None
            if plan and previous is not original:
                return "本次搜索条件刚刚更新，请根据最新列表重新发送这句话。"
            if plan:
                if plan.action == "clarify":
                    return CLARIFICATIONS[plan.clarification]
                if plan.action == "explain":
                    if previous:
                        previous.touched = now
                    return "\n".join(EXPLANATIONS[topic] for topic in dict.fromkeys(plan.topics))
                text = {"detail": f"第{plan.positions[0]}家" if plan.positions else "", "next_page": "下一页", "previous_page": "上一页", "clear_filters": "清除筛选", "reset": "重新搜索"}.get(plan.action, text)
            if text in ("重新搜索", "重置搜索", "结束查询"):
                self.sessions.pop(key, None)
                return "已清除本次搜索，请输入新的商品或条件。"
            if text in ("行情", "大盘", "概况", "市场", "价格", "汇总"):
                self.sessions.pop(key, None)
                return render_overview(catalog)
            detail = re.fullmatch(detail_pattern, text)
            control = text in ("下一页", "上一页", "清除筛选", "取消筛选", "再便宜点", "更便宜的", "查看报价", "报价列表") or detail is not None or bool(plan and plan.positions)
            if control and previous is None:
                return "请先搜索商品，再继续筛选或查看报价。"
            changed_snapshot = previous is not None and previous.snapshot_id != catalog.id
            session = SearchSession(replace(previous.query), catalog.id, previous.page, previous.shown_ids, now, previous.analysis_metric, previous.shown_products) if previous else SearchSession(QuoteQuery(), catalog.id, touched=now)
            if changed_snapshot:
                session.page, session.shown_ids, session.shown_products = 0, (), ()
            if plan and plan.action == "compare" and not (changed_snapshot and plan.positions):
                if plan.positions:
                    if any(position > len(session.shown_ids) for position in plan.positions):
                        return "当前页没有这个序号，请按列表中的序号选择。"
                    rows = [catalog.by_id[session.shown_ids[position - 1]] for position in plan.positions]
                    if any(datetime.now(timezone.utc) - timestamp(o["observed_at"]) > catalog.max_age for _, o in rows):
                        return "这条报价已不可用，请重新搜索。"
                else:
                    queries = [spec.query(catalog, previous.query if previous else None) for spec in plan.searches]
                    candidates = [catalog.search(query) for query in queries]
                    if any(not rows for rows in candidates):
                        missing = [catalog.products.get(q.product, {}).get("display_name") or q.brand or "所选方案" for q, rows in zip(queries, candidates) if not rows]
                        return "以下方案没有符合条件的报价，暂时无法比较：" + "、".join(missing) + "。可放宽条件后再试。"
                    rows = [choices[0] for choices in candidates]
                    session.query = queries[0]
                    session.page = 0
                session.shown_ids = tuple(o["id"] for _, o in rows)
                session.analysis_metric = ""
                session.shown_products = ()
                self._remember(key, session)
                reply = render_comparison(rows)
                for topic in dict.fromkeys(plan.topics):
                    if EXPLANATIONS[topic] not in reply:
                        reply += "\n" + EXPLANATIONS[topic]
                return reply
            if detail and not changed_snapshot:
                number = int(detail[1]) if detail[1].isdigit() else "一二三四五".index(detail[1]) + 1
                if session.shown_products:
                    if number > len(session.shown_products):
                        return "当前页没有这个商品序号，请按列表中的序号选择。"
                    slug = session.shown_products[number - 1]
                    session.query = replace(session.query, product=slug, brand=catalog.products[slug]["brand"])
                    session.analysis_metric, session.shown_products, session.page = "", (), 0
                    reply = render_results(catalog, session)
                    self._remember(key, session)
                    return reply
                if number > len(session.shown_ids):
                    return "当前统计页没有报价序号，可先发送“查看报价”。" if session.analysis_metric else "当前页没有这个序号，请按列表中的序号选择。"
                row = catalog.by_id.get(session.shown_ids[number - 1])
                if row is None or datetime.now(timezone.utc) - timestamp(row[1]["observed_at"]) > catalog.max_age:
                    return "这条报价已不可用，请重新搜索。"
                product, offer = row
                previous.touched = now
                explanations = [EXPLANATIONS[topic] for topic in dict.fromkeys(plan.topics)] if plan else []
                return "\n".join([f"{product['display_name']} · {offer['shop_name']}", offer["original_name"], f"{_price(offer)} · {_stock(offer)}", _terms(offer), offer.get("source_url") or f"{SITE_URL}/products/{product['slug']}", *explanations])
            if not changed_snapshot and text in ("下一页", "上一页"):
                session.page += 1 if text == "下一页" else -1
            elif text in ("查看报价", "报价列表"):
                session.analysis_metric = ""
                session.page = 0
            elif text in ("清除筛选", "取消筛选"):
                session.query = QuoteQuery(product=session.query.product, brand=session.query.brand)
                session.page = 0
            elif text in ("再便宜点", "更便宜的"):
                current = catalog.search(session.query)
                if not current:
                    return "当前没有符合条件的报价，请先放宽筛选条件。"
                # Compare only within one currency; the default recommendations are CNY.
                currencies = {row[1]["currency"] for row in current}
                if len(currencies) != 1 or current[0][1].get("price") is None:
                    return "请先指定币种和预算，避免比较不同币种的报价。"
                previous.touched = now
                return "当前优先展示可比现货中的低价；可以清除筛选，或更换周期和交付方式。"
            elif not control:
                try:
                    if plan and plan.action in {"search", "analyze"}:
                        session.query = plan.searches[0].query(catalog, previous.query if previous else None, allow_catalog=plan.action == "analyze")
                        if plan.action == "analyze":
                            session.analysis_metric = plan.metric
                        elif not plan.searches[0].inherit:
                            session.analysis_metric = ""
                    else:
                        context_query = previous.query if previous and not re.search(r"本网站|本站|全站|站内", raw_text) else None
                        if analysis and not analysis[1] and context_query is None and analysis[0] in {"popularity", "catalog", "count", "stock", "shops", "freshness"}:
                            session.query = QuoteQuery()
                        else:
                            session.query = parse_query(analysis[1] if analysis else raw_text, catalog, context_query)
                        if analysis:
                            session.analysis_metric = analysis[0]
                        elif (text in catalog.aliases or text in catalog.brands or previous is None
                              or (session.query.product, session.query.brand) != (previous.query.product, previous.query.brand)):
                            session.analysis_metric = ""
                except QueryError as exc:
                    return str(exc)
                session.page = 0
            if session.analysis_metric:
                result = render_analysis(catalog, session.query, session.analysis_metric, session.page)
                session.page, session.shown_ids, session.shown_products = result.page, result.shown_ids, result.shown_products
                reply = result.text
                if conditions := _conditions(session.query):
                    reply = reply.replace("\n", f"\n筛选：{conditions}\n", 1)
            elif session.query.brand and not session.query.product and not _conditions(session.query) and not session.query.delivery:
                session.shown_products = ()
                session.shown_ids = ()
                reply = render_overview(catalog, session.query.brand)
            else:
                session.shown_products = ()
                reply = render_results(catalog, session)
            if changed_snapshot and control:
                reply = "报价已更新，已刷新列表，请按新列表选择。\n" + reply
            self._remember(key, session)
            if plan:
                reply += "".join("\n" + EXPLANATIONS[topic] for topic in dict.fromkeys(plan.topics))
            return fallback_note + reply


snapshot_chat = SnapshotChat()

from __future__ import annotations

import logging
import os
import re
from datetime import timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, contains_eager

from app.database import SessionLocal
from app.models import CatalogSnapshot, Offer, OfferHistory, Product, UserBotBinding
from app.schemas import OfferGroupPublic, OfferPublic
from app.services.bot_binding import complete_qq_binding
from app.services.catalog import (
    OfferFilters,
    _base_public_offer_query,
    _is_trusted_offer,
    _median_prices,
    get_current_snapshot,
    get_catalog_group_page,
    get_product_detail,
    get_product_recommendations,
    list_product_cards,
)

logger = logging.getLogger(__name__)

SITE_BASE_URL = os.getenv("NEXT_PUBLIC_SITE_URL", "https://ai.pricememo.cn").rstrip("/")

DELIVERY_LABELS: dict[str, str] = {
    "subscription_recharge": "官方直充 / 代充",
    "finished_account": "成品账号",
    "semi_finished_account": "半成品 / 首登号",
    "team_seat": "团队席位",
    "card_code": "卡密 / 兑换码",
    "trial_account": "日抛 / 体验号",
    "shared_pool": "共享号池",
    "relay_api": "中转 / 反代",
    "api_credit": "API 额度",
    "verification_service": "验证 / 接码服务",
    "unknown": "形态待确认",
}

PERIOD_LABELS: dict[str, str] = {
    "one_day": "1 天 / 日抛",
    "one_week": "1 周",
    "one_month": "1 个月",
    "three_months": "3 个月",
    "six_months": "6 个月",
    "one_year": "1 年",
    "unknown": "期限未注明",
}

WARRANTY_LABELS: dict[str, str] = {
    "none": "无质保",
    "first_login": "仅首登质保",
    "one_hour": "1 小时质保",
    "one_day": "24 小时质保",
    "three_days": "3 天质保",
    "seven_days": "7 天质保",
    "subscription_term": "订阅期全保",
    "unknown": "质保未注明",
}

def _normalize_query_alias(value: str) -> str:
    return "".join(value.split()).casefold()


BRAND_GROUPS: dict[str, dict[str, Any]] = {
    "Claude": {
        "title": "Claude 全系列最低报价一览",
        "aliases": ["claude", "anthropic", "克劳德"],
        "hint": "发送具体型号（如「claude pro」、「claude 20x」、「claude team」）可查看最低价与店铺详情。",
    },
    "OpenAI": {
        "title": "OpenAI / ChatGPT 全系列最低报价一览",
        "aliases": ["openai", "chatgpt", "gpt"],
        "hint": "发送具体型号（如「chatgpt plus」、「chatgpt 5x」、「chatgpt 20x」、「chatgpt go」、「chatgpt接码」）可查看最低价与店铺详情。",
    },
    "Gemini": {
        "title": "Gemini 全系列最低报价一览",
        "aliases": ["gemini", "google", "双子座", "谷歌ai"],
        "hint": "发送具体型号（如「gemini advanced」、「gemini账号」）可查看最低价与店铺详情。",
    },
    "Grok": {
        "title": "Grok 全系列最低报价一览",
        "aliases": ["grok", "xai", "x.ai"],
        "hint": "发送具体型号（如「supergrok」、「grok api」）可查看最低价与店铺详情。",
    },
    "X": {
        "title": "X (Twitter) Premium 全系列最低报价一览",
        "aliases": ["x", "twitter", "推特", "x会员"],
        "hint": "发送具体型号（如「premium」、「premium+」）可查看最低价与店铺详情。",
    },
    "Cursor": {
        "title": "Cursor 全系列最低报价一览",
        "aliases": ["cursor", "cursor会员"],
        "hint": "发送具体型号（如「cursor pro」、「cursor账号」）可查看最低价与店铺详情。",
    },
}

BRAND_ALIASES: dict[str, str] = {}
for brand_key, cfg in BRAND_GROUPS.items():
    for alias in cfg["aliases"]:
        BRAND_ALIASES[_normalize_query_alias(alias)] = brand_key

# Aliases mapped to canonical product slugs for single-product deep dive
PRODUCT_ALIASES: dict[str, str] = {
    # ChatGPT / OpenAI models
    "plus": "chatgpt-plus",
    "chatgpt plus": "chatgpt-plus",
    "gpt plus": "chatgpt-plus",
    "gpt4": "chatgpt-plus",
    "gpt-4": "chatgpt-plus",
    "gpt-4o": "chatgpt-plus",
    "4o": "chatgpt-plus",
    "chatgpt-plus": "chatgpt-plus",
    "gpt 5x": "chatgpt-pro-5x",
    "chatgpt 5x": "chatgpt-pro-5x",
    "chatgpt pro 5x": "chatgpt-pro-5x",
    "chatgpt-pro-5x": "chatgpt-pro-5x",
    "gpt 20x": "chatgpt-pro-20x",
    "chatgpt 20x": "chatgpt-pro-20x",
    "chatgpt pro 20x": "chatgpt-pro-20x",
    "chatgpt-pro-20x": "chatgpt-pro-20x",
    "chatgpt pro": "chatgpt-pro-20x",
    "gpt pro": "chatgpt-pro-20x",
    "chatgpt-pro": "chatgpt-pro-20x",
    "go": "chatgpt-go",
    "chatgpt go": "chatgpt-go",
    "gpt go": "chatgpt-go",
    "codex go": "chatgpt-go",
    "chatgpt-go": "chatgpt-go",
    "team": "chatgpt-k12",
    "gpt team": "chatgpt-k12",
    "chatgpt team": "chatgpt-k12",
    "k12": "chatgpt-k12",
    "团队": "chatgpt-k12",
    "车位": "chatgpt-k12",
    "chatgpt-k12": "chatgpt-k12",
    "gpt 账号": "chatgpt-account",
    "chatgpt 账号": "chatgpt-account",
    "chatgpt free": "chatgpt-account",
    "free": "chatgpt-account",
    "chatgpt-account": "chatgpt-account",
    "chatgpt 接码": "chatgpt-access-service",
    "chatgpt 手机接码": "chatgpt-access-service",
    "openai 接码": "chatgpt-access-service",
    "手机接码": "chatgpt-access-service",
    "chatgpt-access-service": "chatgpt-access-service",
    "openai api": "openai-api-credit",
    "openai-api-credit": "openai-api-credit",
    # Claude models
    "pro": "claude-pro",
    "claude pro": "claude-pro",
    "claude-pro": "claude-pro",
    "sonnet": "claude-pro",
    "5x": "claude-pro",
    "claude 5x": "claude-pro",
    "20x": "claude-pro-20x",
    "claude 20x": "claude-pro-20x",
    "claude pro 20x": "claude-pro-20x",
    "claude-pro-20x": "claude-pro-20x",
    "claude team": "claude-team",
    "claude-team": "claude-team",
    "claude 车位": "claude-team",
    "claude 团队": "claude-team",
    "claude 账号": "claude-account",
    "claude-account": "claude-account",
    "claude api": "claude-api-access",
    "claude-api-access": "claude-api-access",
    # Gemini models
    "gemini advanced": "gemini-advanced",
    "gemini pro": "gemini-advanced",
    "gemini-advanced": "gemini-advanced",
    "advanced": "gemini-advanced",
    "gemini 账号": "gemini-account",
    "gemini-account": "gemini-account",
    "gemini api": "gemini-api-access",
    "gemini-api-access": "gemini-api-access",
    # Grok models
    "grok super": "grok-super",
    "grok-super": "grok-super",
    "supergrok": "grok-super",
    "grok 账号": "grok-account",
    "grok-account": "grok-account",
    "grok api": "grok-api-access",
    "grok-api-access": "grok-api-access",
    # X Premium models
    "premium basic": "x-premium-basic",
    "x premium basic": "x-premium-basic",
    "x-premium-basic": "x-premium-basic",
    "premium": "x-premium",
    "x premium": "x-premium",
    "x-premium": "x-premium",
    "premium+": "x-premium-plus",
    "premium plus": "x-premium-plus",
    "x premium+": "x-premium-plus",
    "x premium plus": "x-premium-plus",
    "x-premium-plus": "x-premium-plus",
    # Others
    "deepseek": "deepseek-r1",
    "codex": "chatgpt-plus",
    "codex plus": "chatgpt-plus",
    "api": "openai-api-credit",
    # Cursor models
    "cursor": "cursor-pro",
    "cursor pro": "cursor-pro",
    "cursor-pro": "cursor-pro",
    "cursor business": "cursor-business",
    "cursor-business": "cursor-business",
    "cursor 账号": "cursor-account",
    "cursor-account": "cursor-account",
}
PRODUCT_ALIASES = {_normalize_query_alias(alias): slug for alias, slug in PRODUCT_ALIASES.items()}


def _get_current_snapshot(db: Session) -> CatalogSnapshot | None:
    return get_current_snapshot(db)


def _stock_label(offer: OfferPublic) -> str:
    if offer.stock_status == "out_of_stock":
        return "已售罄"
    if offer.stock_status != "in_stock":
        return "库存状态未注明"
    return f"库存 {offer.stock_count} 件" if offer.stock_count is not None else "有货，库存数未注明"


def _offer_terms(offer: OfferPublic) -> str:
    delivery = DELIVERY_LABELS.get(offer.delivery_type, offer.delivery_type)
    period = PERIOD_LABELS.get(offer.service_period, offer.service_period)
    warranty = WARRANTY_LABELS.get(offer.warranty, offer.warranty)
    return f"{delivery} / {period} / {warranty}"


def _group_quote_lines(groups: list[OfferGroupPublic]) -> list[str]:
    lines = []
    for idx, group in enumerate(groups, 1):
        offer = group.representative
        price = group.lowest_price if group.lowest_price is not None else offer.price
        currency = group.price_currency if group.lowest_price is not None else offer.currency
        price_label = "价格未注明" if price is None else f"{'¥' if currency == 'CNY' else currency + ' '}{price:.2f}"
        lines.append(f"{idx}. {group.product_name}: {price_label} | {_stock_label(offer)}")
        lines.append(f"   {offer.original_name}")
        lines.append(f"   {_offer_terms(offer)} | {group.shop_count} 家店铺")
    return lines


def query_brand_lowest_prices(db: Session, brand_name: str) -> str:
    """Find lowest price for all products under a brand/family."""
    brand_cfg = BRAND_GROUPS.get(brand_name)
    if not brand_cfg:
        return f"⚠️ 未知品牌分类「{brand_name}」。"

    snapshot = _get_current_snapshot(db)
    if not snapshot:
        return "⚠️ 暂无已发布的比价大盘数据，请稍后再试。"

    title = brand_cfg["title"]
    slugs = tuple(db.scalars(select(Product.slug).where(
        Product.platform == brand_name,
        Product.is_visible.is_(True),
    )))
    cards = list_product_cards(db, platform=brand_name, product_slugs=slugs, snapshot_id=snapshot.id)
    hint = brand_cfg.get("hint", "")

    lines = [
        f"🏷️【{title}】",
        "------------------------------------",
    ]

    digit_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, card in enumerate(cards):
        emoji = digit_emojis[idx] if idx < len(digit_emojis) else f"{idx+1}."
        best_rows = get_product_recommendations(db, card.slug, snapshot=snapshot, limit=1)
        lines.append(f"{emoji} {card.display_name}")
        if best_rows:
            best_offer = best_rows[0]
            lines.append(f"   💰 最低: ¥{best_offer.price:.2f} | {_stock_label(best_offer)}")
            lines.append(f"   🏪 店铺: {best_offer.shop_name} ({_offer_terms(best_offer)})")
        else:
            if card.offer_count and not card.comparable_offer_count:
                lines.append("   💰 仅有相关商品报价，不纳入可比最低价")
            elif card.offer_count:
                lines.append("   💰 暂无通过价格校验的可比现货报价")
            else:
                lines.append("   💰 暂无公开报价 (监控中)")
        lines.append(f"   🔗 {SITE_BASE_URL}/products/{card.slug}")
        lines.append("")

    if not cards:
        lines.append("当前没有可展示的公开商品分类。")
    if lines and lines[-1] == "":
        lines.pop()

    lines.append("------------------------------------")
    if hint:
        lines.append(f"💡 {hint}")
    lines.append(f"🌐 官网比价大盘: {SITE_BASE_URL}")

    return "\n".join(lines)


def query_lowest_price(db: Session, raw_query: str) -> str:
    """Find trusted comparable prices using the public catalog rules."""
    clean = raw_query.strip().casefold()

    # Route brand-level queries to brand aggregator
    alias_key = _normalize_query_alias(clean)
    matched_brand = BRAND_ALIASES.get(alias_key)
    if matched_brand:
        return query_brand_lowest_prices(db, matched_brand)
    if alias_key in ("中转", "中转站", "反代", "relay"):
        return query_relay_offers(db)

    target_slug = PRODUCT_ALIASES.get(alias_key)

    snapshot = _get_current_snapshot(db)
    if not snapshot:
        return "⚠️ 暂无已发布的比价大盘数据，请稍后再试。"

    matched_product: Product | None = None
    if target_slug:
        matched_product = db.scalar(select(Product).where(Product.slug == target_slug, Product.is_visible.is_(True)))
    else:
        # Search by display_name or slug
        matched_product = db.scalar(
            select(Product)
            .where(
                Product.is_visible == True,
                or_(
                    Product.slug.ilike(f"%{clean}%"),
                    Product.display_name.ilike(f"%{clean}%"),
                ),
            )
            .order_by(Product.id.asc())
            .limit(1)
        )

    if not matched_product:
        return (
            f"🔍 未找到与「{raw_query}」直接匹配的商品分类。\n"
            f"💡 常用指令示例:\n"
            f"  • claude — Claude 全系列最低价一览\n"
            f"  • openai — OpenAI 全系列最低价一览\n"
            f"  • claude 20x / chatgpt 20x — 查询对应品牌 20x 最低价\n"
            f"  • plus — 查询 ChatGPT Plus 最低价\n"
            f"  • pro — 查询 Claude Pro (5x) 最低价\n"
            f"  • 行情 — 查看全网大盘报价表\n"
            f"🌐 官网搜索: {SITE_BASE_URL}/products"
        )

    offers = get_product_recommendations(db, matched_product.slug, snapshot=snapshot)

    if not offers:
        detail = get_product_detail(db, matched_product.slug, snapshot_id=snapshot.id)
        if detail and detail.offer_group_count == 0:
            related = get_product_detail(db, matched_product.slug, filters=OfferFilters(), snapshot_id=snapshot.id)
            if related and related.offer_group_count:
                lines = [
                    f"📦【{matched_product.display_name}】仅有相关商品报价，暂无可直接比价的报价。",
                    "相关商品报价（不纳入可比最低价）：",
                    *_group_quote_lines(related.offer_groups[:5]),
                    f"🔗 商品详情: {SITE_BASE_URL}/products/{matched_product.slug}?comparable=false",
                ]
                return "\n".join(lines)
        msg = f"📦【{matched_product.display_name}】当前暂无通过价格校验的可比现货报价。\n"
        # Do not claim a subscription was created here: this path has no user
        # identity, so point the user at the place that can actually subscribe.
        msg += (
            f"🔔 想在有货或降价时收到通知？请到官网关注该商品：\n"
            f"   {SITE_BASE_URL}/products/{matched_product.slug}\n"
            f"🔗 官网实时监控: {SITE_BASE_URL}/products/{matched_product.slug}"
        )
        return msg

    best_offer = offers[0]
    delivery_label = DELIVERY_LABELS.get(best_offer.delivery_type, best_offer.delivery_type or "普通现货")
    warranty_label = WARRANTY_LABELS.get(best_offer.warranty, best_offer.warranty or "未注明")

    lines = [
        f"🎯【{matched_product.display_name}】全网比价推荐",
        f"平台所属: {matched_product.platform}",
        "------------------------------------",
        f"🥇 最低在售: ¥{best_offer.price:.2f}",
        f"🏪 店铺商家: {best_offer.shop_name}",
        f"📦 {_stock_label(best_offer)}",
        f"商品原文: {best_offer.original_name}",
        f"🏷️ 交付形式: {delivery_label}",
        f"服务期限: {PERIOD_LABELS.get(best_offer.service_period, best_offer.service_period)}",
        f"🛡️ 质保服务: {warranty_label}",
    ]

    if len(offers) > 1:
        lines.append("可比现货排行（同款合并）：")
        for idx, offer in enumerate(offers, 1):
            lines.append(f"{idx}. ¥{offer.price:.2f} @ {offer.shop_name} ({_stock_label(offer)})")
            lines.append(f"   {_offer_terms(offer)}")

    lines.append("------------------------------------")
    lines.append(f"🔗 商品比价详情: {SITE_BASE_URL}/products/{matched_product.slug}")
    if best_offer.source_url:
        lines.append(f"🛒 直达最低价店铺: {best_offer.source_url}")
    lines.append("💡 发送「降价」可查看今日全网降价精选")

    return "\n".join(lines)


def query_relay_offers(db: Session) -> str:
    snapshot = _get_current_snapshot(db)
    if not snapshot:
        return "⚠️ 暂无已发布的比价大盘数据，请稍后再试。"
    groups, total, *_ = get_catalog_group_page(
        db, offset=0, limit=5, filters=OfferFilters(delivery_type="relay_api"), snapshot=snapshot,
    )
    return "\n".join([
        f"中转 / 反代商品报价（跨品牌，共 {total} 组）",
        "相关商品报价，不纳入会员最低价比较。",
        *(_group_quote_lines(groups) if groups else ["当前没有公开的中转 / 反代商品报价。"]),
        f"商品报价: {SITE_BASE_URL}/products?brand=%E4%B8%AD%E8%BD%AC%E7%AB%99",
        f"中转站目录: {SITE_BASE_URL}/relays",
    ])


def query_market_overview(db: Session) -> str:
    """Render a market summary board for major AI subscriptions."""
    snapshot = _get_current_snapshot(db)
    if not snapshot:
        return "⚠️ 暂无已发布的行情快照数据。"
    published_at = snapshot.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    major_targets = [
        ("ChatGPT Plus", "chatgpt-plus"),
        ("Claude Pro (5x)", "claude-pro"),
        ("Claude Pro 20x", "claude-pro-20x"),
        ("Gemini Advanced", "gemini-advanced"),
        ("SuperGrok", "grok-super"),
    ]

    lines = [
        "📊【PriceMemo AI 服务大盘行情】",
        f"数据快照: #{snapshot.id} ({published_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})",
        "------------------------------------",
    ]

    for label, slug in major_targets:
        product = db.scalar(select(Product).where(Product.slug == slug, Product.is_visible.is_(True)))
        if not product:
            continue

        best_rows = get_product_recommendations(db, product.slug, snapshot=snapshot, limit=1)

        if best_rows:
            best_offer = best_rows[0]
            lines.append(f"▪️ {label}: 最低 ¥{best_offer.price:.2f} ({_stock_label(best_offer)})")
        else:
            lines.append(f"▪️ {label}: 暂无通过价格校验的可比现货报价")

    cards = list_product_cards(db, snapshot_id=snapshot.id)
    total_offers = sum(card.offer_count for card in cards)
    in_stock_offers = sum(card.in_stock_count for card in cards)

    lines.append("------------------------------------")
    lines.append(f"📡 当前公开报价: {total_offers} 条 | 有货报价: {in_stock_offers} 条")
    lines.append(f"🌐 完整比价看板: {SITE_BASE_URL}")
    lines.append("💡 发送 claude 或 openai 可查看品牌全系列价格一览")

    return "\n".join(lines)


def query_recent_drops(db: Session) -> str:
    """Find recently dropped price offers."""
    snapshot = _get_current_snapshot(db)
    if not snapshot:
        return "⚠️ 暂无已发布数据。"

    # Query offers with history where previous price was higher
    drops_found: list[dict[str, Any]] = []

    # Check top public comparable offers
    stmt = (
        _base_public_offer_query(db, include_details=True, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .options(contains_eager(Offer.product))
        .where(
            Product.is_visible.is_(True),
            Offer.is_comparable.is_(True),
            Offer.stock_status == "in_stock",
            Offer.currency == "CNY",
            Offer.price.is_not(None),
            Offer.price > 0,
        )
        .order_by(Offer.updated_at.desc())
        .limit(60)
    )
    offers = list(db.scalars(stmt).unique())
    medians = _median_prices(offers, comparable_only=True)

    for offer in offers:
        if not _is_trusted_offer(offer, medians):
            continue
        product = offer.product
        shop = offer.shop
        if not product or not shop:
            continue

        history_rows = list(
            db.scalars(
                select(OfferHistory)
                .where(OfferHistory.offer_id == offer.id)
                .order_by(OfferHistory.id.desc())
                .limit(2)
            )
        )
        if len(history_rows) >= 2:
            prev = history_rows[1]
            curr = history_rows[0]
            if prev.price and curr.price and curr.price < prev.price:
                diff = prev.price - curr.price
                pct = round(float(diff / prev.price * 100), 1)
                drops_found.append({
                    "product": product.display_name,
                    "shop": shop.name,
                    "old_price": prev.price,
                    "new_price": curr.price,
                    "diff": diff,
                    "pct": pct,
                    "stock": offer.stock_count,
                    "slug": product.slug,
                })
                if len(drops_found) >= 5:
                    break

    if not drops_found:
        return (
            "📉【今日降价精选】\n"
            "------------------------------------\n"
            "当前最新快照暂无剧烈降价波动，大盘价格整体平稳。\n"
            "💡 机器人将在发现降价的第一时间自动私聊推送！\n"
            f"🌐 查看实时行情: {SITE_BASE_URL}"
        )

    lines = [
        f"📉【今日降价精选】（共 {len(drops_found)} 条）",
        "------------------------------------",
    ]
    for d in drops_found:
        lines.append(
            f"🔻 {d['product']} ({d['shop']})\n"
            f"   ¥{d['old_price']:.2f} ➔ ¥{d['new_price']:.2f} (降¥{d['diff']:.2f}, -{d['pct']}%) 库存:{d['stock']}"
        )
    lines.append("------------------------------------")
    lines.append(f"🔗 官网实时追踪: {SITE_BASE_URL}")

    return "\n".join(lines)


def query_user_status(db: Session, sender_id: str, channel: str = "qq") -> str:
    """Show current bot notification preferences for this user."""
    if not sender_id:
        return "⚠️ 未能识别您的账号标识，请在个人中心扫码绑定。"

    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == channel,
            UserBotBinding.target_id == sender_id,
        )
    )

    if not binding:
        return (
            "👤【账号通知状态】\n"
            "您当前尚未绑定 PriceMemo 比价账号。\n"
            "------------------------------------\n"
            f"📱 快速绑定方法:\n"
            f"1. 电脑访问: {SITE_BASE_URL}/account\n"
            f"2. 点击「QQ 扫码绑定机器人」，手机扫码后即刻开通！\n"
            f"（或在网页获取 6 位绑定码后，在此私聊回复: /bind 验证码）"
        )

    status_icon = "🟢 开启中" if binding.is_active else "🔴 已暂停"
    drop_icon = "🟢 开启" if binding.notify_price_drop else "⚪ 已关闭"
    hike_icon = "🟢 开启" if binding.notify_price_hike else "⚪ 已关闭"

    lines = [
        "👤【您的 PriceMemo 通知设置】",
        "------------------------------------",
        f"🔔 推送总状态: {status_icon}",
        f"📉 降价通知: {drop_icon}",
        f"📈 涨价通知: {hike_icon}",
        "------------------------------------",
        "💡 快捷切换指令 (直接回复):",
        "  • 暂停推送 / 恢复推送",
        "  • 开启降价 / 关闭降价",
        "  • 开启涨价 / 关闭涨价",
        f"🌐 网页管理中心: {SITE_BASE_URL}/account",
    ]
    return "\n".join(lines)


def toggle_user_preference(db: Session, sender_id: str, action: str, channel: str = "qq") -> str:
    """Update user notification preferences via chat commands."""
    if not sender_id:
        return "⚠️ 无法获取您的账号标识。"

    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == channel,
            UserBotBinding.target_id == sender_id,
        )
    )

    if not binding:
        return (
            f"您尚未绑定账号，无法修改设置。\n"
            f"请先在 {SITE_BASE_URL}/account 扫码绑定 QQ 机器人。"
        )

    if action in ("暂停推送", "关闭推送", "/pause"):
        binding.is_active = False
        db.commit()
        return "🔴 已为您暂停全部消息推送。发送「恢复推送」可随时重新开启。"

    if action in ("恢复推送", "开启推送", "/resume"):
        binding.is_active = True
        db.commit()
        return "🟢 已为您恢复消息推送，降价变动将第一时间私聊通知您。"

    if action in ("开启降价", "开降价"):
        binding.notify_price_drop = True
        db.commit()
        return "📉 已开启【降价通知】！当有商品价格下调时将及时提醒您。"

    if action in ("关闭降价", "关降价"):
        binding.notify_price_drop = False
        db.commit()
        return "⚪ 已关闭【降价通知】。"

    if action in ("开启涨价", "开涨价"):
        binding.notify_price_hike = True
        db.commit()
        return "📈 已开启【涨价通知】。"

    if action in ("关闭涨价", "关涨价"):
        binding.notify_price_hike = False
        db.commit()
        return "⚪ 已关闭【涨价通知】。"

    return "未知设置指令，发送「我的」可查看当前配置。"


def query_user_subscriptions(db: Session, sender_id: str, channel: str = "qq") -> str:
    """Query user's subscriptions and latest prices from database."""
    if not sender_id:
        return f"⚠️ 未能识别您的账号，请先在官网个人中心扫码绑定：{SITE_BASE_URL}/account"

    from app.models import UserProductSubscription

    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == channel,
            UserBotBinding.target_id == sender_id,
        )
    )
    if not binding:
        return (
            f"ℹ️ 您的账号尚未绑定 PriceMemo 网页账号。\n"
            f"请访问官网个人中心生成专属绑定二维码：\n"
            f"🔗 {SITE_BASE_URL}/account\n"
            f"扫码添加机器人好友后即可同步您在网页上关注的所有商品及降价通知！"
        )

    subs = list(
        db.scalars(
            select(UserProductSubscription)
            .join(Product, UserProductSubscription.product_slug == Product.slug)
            .where(UserProductSubscription.user_id == binding.user_id, Product.is_visible.is_(True))
            .order_by(UserProductSubscription.id.asc())
        )
    )
    if not subs:
        return (
            f"📋 您当前在 PriceMemo 暂无关注的商品。\n"
            f"💡 前往官网商品列表点击「关注」即可添加订阅，降价时机器人会自动提醒：\n"
            f"🔗 {SITE_BASE_URL}/watchlist"
        )

    snapshot = _get_current_snapshot(db)
    lines = [
        f"📋【您在 PriceMemo 关注的商品清单】(共 {len(subs)} 项)",
        "------------------------------------",
    ]

    for idx, sub in enumerate(subs, 1):
        product = db.scalar(select(Product).where(Product.slug == sub.product_slug, Product.is_visible.is_(True)))
        p_name = product.display_name if product else sub.product_slug
        min_offer = None
        if snapshot and product:
            best_rows = get_product_recommendations(db, product.slug, snapshot=snapshot, limit=1)
            if best_rows:
                min_offer = best_rows[0]

        if min_offer:
            target_str = f"¥{sub.target_price:.2f}" if sub.target_price is not None else "未设阈值"
            status_flag = "✅ 已达标" if (sub.target_price is not None and min_offer.price <= sub.target_price) else "⏳ 监控中"
            lines.append(
                f"{idx}. 🎯 {p_name}\n"
                f"   最新低价: ¥{min_offer.price:.2f} ({_stock_label(min_offer)}) | {status_flag}\n"
                f"   目标价格: {target_str}\n"
                f"   🔗 {SITE_BASE_URL}/products/{sub.product_slug}"
            )
        else:
            lines.append(
                f"{idx}. 🎯 {p_name} (暂无现货报价)\n"
                f"   🔗 {SITE_BASE_URL}/products/{sub.product_slug}"
            )

    lines.append("------------------------------------")
    lines.append("💡 发送具体商品名如「plus」或「pro」可查看最低价店铺直达链接")
    return "\n".join(lines)


def help_menu() -> str:
    """Cheatsheet of all supported bot commands."""
    return "\n".join([
        "🤖【PriceMemo 比价机器人常用指令指南】",
        "------------------------------------",
        "🏷️ 品牌全系列比价:",
        "  • claude — Claude 全系列最低价一览 (5x / 20x / Team)",
        "  • openai / gpt — OpenAI 全系列最低价一览",
        "  • gemini — Gemini 全系列最低价一览",
        "  • grok — Grok 全系列最低价一览",
        "  • cursor — Cursor 全系列最低价一览",
        "  • x / twitter — X Premium 全系列最低价一览",
        "",
        "🔍 单品比价与店铺详情:",
        "  • 20x / claude 20x — 查询 Claude 20x 最低价",
        "  • chatgpt 20x — 查询 ChatGPT 20x 最低价",
        "  • chatgpt 5x / chatgpt go — 查询对应订阅型号最低价",
        "  • chatgpt接码 — 查询手机接码服务报价",
        "  • pro / 5x — 查询 Claude Pro (5x) 最低价",
        "  • claude team / chatgpt team — 查询对应品牌团队版报价",
        "  • plus — 查询 ChatGPT Plus 最低价",
        "  • gemini advanced — 查询 Gemini Advanced 最低价",
        "  • supergrok — 查询 SuperGrok 最低价",
        "  • cursor pro — 查询 Cursor Pro 最低价",
        "  • gemini账号 / claude账号 / cursor账号 — 查询对应品牌账号",
        "  • api / openai api — 查询 OpenAI API 额度商品",
        "  • 中转 / 中转站 — 查看跨品牌中转、反代商品报价",
        "  • 查 <关键词> — 搜索任意商品或服务最低价",
        "",
        "📊 大盘行情与发现:",
        "  • 行情 / 大盘 — 查看主流 AI 服务价格看板",
        "  • 降价 / 特惠 — 查看今日全网最新降价精选",
        "",
        "🔔 个人订阅与推送:",
        "  • 关注 / 订阅 — 查看我关注的商品最新价格与达标情况",
        "  • 我的 — 查看当前推送偏好与绑定状态",
        "  • 暂停推送 / 恢复推送 — 一键启停消息通知",
        "  • 开启降价 / 关闭降价 — 独立控制降价提醒",
        "",
        "🔗 绑定指令:",
        "  • /bind <6位验证码> — 绑定网页个人账号",
        "------------------------------------",
        f"🌐 官方网站: {SITE_BASE_URL}",
    ])



def handle_chat_command(
    raw_text: str,
    sender_id: str = "",
    channel: str = "qq",
    db: Session | None = None,
) -> str:
    """Main router for inbound chat messages from QQ Bot and Telegram Bot.

    Can be invoked with an existing DB session or will open a standalone one.
    """
    text = (raw_text or "").strip()
    if not text:
        return help_menu()

    # Normalize command
    low = text.casefold()

    # 1. Bind command: /bind 123456
    bind_match = re.match(r"^/?bind\s*([0-9a-zA-Z]{4,32})$", text, re.IGNORECASE)
    if bind_match:
        code = bind_match.group(1)
        if not sender_id:
            return "⚠️ 未能识别您的账号标识，无法完成绑定。"

        def _do_bind(s: Session) -> str:
            b = complete_qq_binding(s, code, sender_id)
            if b:
                return "🎉 绑定成功！您的 QQ 已成功连接至 PriceMemo，降价提醒已自动开启。"
            return "❌ 绑定码无效或已过期，请在网页个人中心重新生成。"

        if db is not None:
            return _do_bind(db)
        with SessionLocal() as session:
            return _do_bind(session)

    # 2. Help / Menu
    if low in ("help", "/help", "帮助", "菜单", "?", "？", "start", "/start"):
        return help_menu()

    # 3. Market Overview / Ticker
    if low in ("行情", "大盘", "概况", "市场", "价格", "汇总"):
        if db is not None:
            return query_market_overview(db)
        with SessionLocal() as session:
            return query_market_overview(session)

    # 4. Recent Drops
    if low in ("降价", "今日降价", "特价", "捡漏", "打折", "便宜", "特惠", "cheap"):
        if db is not None:
            return query_recent_drops(db)
        with SessionLocal() as session:
            return query_recent_drops(session)

    # 5. User Subscriptions Query
    if low in ("关注", "我的关注", "订阅", "我的订阅", "清单", "关注清单", "/watchlist"):
        if db is not None:
            return query_user_subscriptions(db, sender_id, channel)
        with SessionLocal() as session:
            return query_user_subscriptions(session, sender_id, channel)

    # 6. User Preference Query
    if low in ("我的", "状态", "设置", "偏好", "个人"):

        if db is not None:
            return query_user_status(db, sender_id, channel)
        with SessionLocal() as session:
            return query_user_status(session, sender_id, channel)

    # 6. User Preference Toggles
    if text in (
        "暂停推送", "恢复推送", "关闭推送", "开启推送",
        "开启降价", "关闭降价", "开降价", "关降价",
        "开启涨价", "关闭涨价", "开涨价", "关涨价",
        "/pause", "/resume",
    ):
        if db is not None:
            return toggle_user_preference(db, sender_id, text, channel)
        with SessionLocal() as session:
            return toggle_user_preference(session, sender_id, text, channel)

    # 7. Search prefix (e.g. 查 plus, 搜 claude, 价格 gpt)
    # Longer prefixes must come first, otherwise "查询 plus" would match "查"
    # and leave the query term as "询 plus".
    search_match = re.match(r"^(?:查询|搜索|价格|比价|查|搜|找)\s*(.+)$", text, re.IGNORECASE)
    query_term = search_match.group(1).strip() if search_match else text

    # 8. Check brand queries first (e.g. claude, openai, chatgpt, gemini, grok)
    matched_brand = BRAND_ALIASES.get(_normalize_query_alias(query_term))
    if matched_brand:
        if db is not None:
            return query_brand_lowest_prices(db, matched_brand)
        with SessionLocal() as session:
            return query_brand_lowest_prices(session, matched_brand)

    # 9. Product Lowest Price Query (e.g. plus, pro, 20x, team, etc.)
    if db is not None:
        return query_lowest_price(db, query_term)
    with SessionLocal() as session:
        return query_lowest_price(session, query_term)

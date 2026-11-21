from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.services.alert_reports import unique_price_events, unique_team_offers


BEIJING_TIME = timezone(timedelta(hours=8))
ITEM_SEPARATOR = "\n\n──────────\n\n"


def fresh_alert_item(item: Any, now: datetime, stale_offer_hours: int | None) -> bool:
    if stale_offer_hours is None:
        return True
    observed = getattr(item, "observed_at", None)
    if isinstance(observed, str):
        try:
            observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(observed, datetime):
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed >= now - timedelta(hours=stale_offer_hours)


def alert_report_url(view: str, site_base_url: str) -> str:
    return f"{site_base_url.rstrip('/')}/alerts?view={view}"


def format_end_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BEIJING_TIME).strftime("%m-%d %H:%M")


def offer_detail_url(offer_id: int, site_base_url: str = "https://ai.pricememo.cn") -> str:
    return f"{site_base_url.rstrip('/')}/offers/{offer_id}"


def format_detection_time(detected_at: datetime | None = None) -> str:
    value = detected_at or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BEIJING_TIME).strftime("%Y-%m-%d %H:%M:%S（北京时间 UTC+8）")


def format_currency_symbol(currency: str) -> str:
    c = currency.upper().strip()
    if c in ("CNY", "RMB"):
        return "¥"
    if c == "USD":
        return "$"
    return f"{c} "


def _esc(value: Any) -> str:
    """Escape dynamic text for Telegram HTML parse_mode."""
    return html.escape(str(value if value is not None else ""), quote=False)


def _display_name(value: str, limit: int = 240) -> str:
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _esc_attr(value: Any) -> str:
    """Escape dynamic text used inside an HTML attribute (e.g. href)."""
    return html.escape(str(value if value is not None else ""), quote=True)


def render_telegram_report(
    events: list[Any], site_base_url: str = "https://ai.pricememo.cn", *, detected_at: datetime | None = None,
) -> str:
    """Render an HTML formatted report suitable for Telegram Bot HTML parse_mode.

    All dynamic fields are HTML-escaped: product/shop names containing `<` or `&`
    would otherwise be parsed as tags and make Telegram reject the whole message.
    """
    events = unique_price_events(events)
    drops = [e for e in events if e.is_drop]
    hikes = [e for e in events if not e.is_drop]
    now_str = format_detection_time(detected_at)

    lines = ["🔔 <b>【PriceMemo 价格变动监控提醒】</b>", ""]

    if drops:
        lines.append(f"📉 <b>降价精选（共 {len(drops)} 款）:</b>")
        lines.append(f'<a href="{_esc_attr(alert_report_url("drops", site_base_url))}">查看最新降价榜</a>')
        for e in drops[:15]:  # Limit top 15 in message to avoid payload size overflow
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            url = offer_detail_url(e.offer_id, site_base_url)
            lines.append(
                f"• <b>{_esc(_display_name(e.product_name))}</b> ({_esc(_display_name(e.shop_name, 80))})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↓{symbol}{diff_abs}, <b>{e.percent_change}%</b>)\n"
                f"  🔗 <a href=\"{_esc_attr(url)}\">查看商品</a>\n\n──────────\n"
            )
        if len(drops) > 15:
            lines.append(f"... 其余 {len(drops) - 15} 条降价详见官网")
        lines.append("")

    if hikes:
        lines.append(f"📈 <b>涨价变动（共 {len(hikes)} 款）:</b>")
        lines.append(f'<a href="{_esc_attr(alert_report_url("rises", site_base_url))}">查看最新涨价</a>')
        for e in hikes[:10]:
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            url = offer_detail_url(e.offer_id, site_base_url)
            lines.append(
                f"• <b>{_esc(_display_name(e.product_name))}</b> ({_esc(_display_name(e.shop_name, 80))})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↑{symbol}{diff_abs}, +{e.percent_change}%)\n"
                f"  🔗 <a href=\"{_esc_attr(url)}\">查看商品</a>\n\n──────────\n"
            )
        if len(hikes) > 10:
            lines.append(f"... 其余 {len(hikes) - 10} 条涨价详见官网")
        lines.append("")

    lines.append(f"⏱ 同步检测时间: {now_str}")
    return "\n".join(lines)


def split_telegram_html(text: str, limit: int = 4000) -> list[str]:
    """Split an HTML report into chunks under Telegram's 4096-char entity limit.

    Splitting happens on line boundaries and the trailing tags opened by a line
    (e.g. `<b>`/`<a href=...>`) are re-opened in the next chunk, so no entity is
    ever cut in half.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    open_tags: list[str] = []

    def _reopen_prefix() -> str:
        return "".join(open_tags)

    for raw_line in text.split("\n"):
        line = raw_line
        # Close any tags left open by the previous chunk before measuring.
        projected = len(_reopen_prefix()) + len(line) + 1
        if current and current_len + projected > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        prefix = _reopen_prefix() if not current else ""
        current.append(prefix + line)
        current_len += projected

        # Track tags that remain open at the end of this line.
        for token in _tag_tokens(line):
            if token.startswith("</"):
                name = token[2:-1].strip().lower()
                open_tags = [t for t in open_tags if not t.startswith(f"<{name}")]
            elif not token.endswith("/>") and not token.startswith("<!"):
                name = token[1:].split()[0].rstrip(">").lower()
                if name not in ("br",):
                    open_tags.append(f"<{name}>")

    if current:
        chunks.append("\n".join(current))
    return chunks


def _tag_tokens(line: str) -> list[str]:
    tokens: list[str] = []
    idx = 0
    while True:
        start = line.find("<", idx)
        if start == -1:
            break
        end = line.find(">", start)
        if end == -1:
            break
        tokens.append(line[start : end + 1])
        idx = end + 1
    return tokens


def render_qq_report(
    events: list[Any], site_base_url: str = "https://ai.pricememo.cn", *, detected_at: datetime | None = None,
) -> str:
    """Render a clean plain-text/markdown report suitable for QQ Bot messages."""
    events = unique_price_events(events)
    drops = [e for e in events if e.is_drop]
    hikes = [e for e in events if not e.is_drop]
    now_str = format_detection_time(detected_at)

    lines = ["【PriceMemo 价格变动提醒】", ""]

    if drops:
        lines.append(f"📉 降价通知（{len(drops)} 款）:")
        lines.append(f"最新降价榜: {alert_report_url('drops', site_base_url)}\n")
        for index, e in enumerate(drops[:8], 1):
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            lines.append(
                f"{index}. {_display_name(e.product_name, 160)}\n"
                f"现价: {symbol}{e.new_price:.2f} · 降 {symbol}{diff_abs:.2f}\n"
                f"原价: {symbol}{e.old_price:.2f} · {_display_name(e.shop_name, 60)}"
            )
            lines.append(f"  🔗 商品详情: {offer_detail_url(e.offer_id, site_base_url)}")
            lines.append("\n──────────\n")
        if len(drops) > 8:
            lines.append(f"另有 {len(drops) - 8} 条降价，榜单链接始终展示最新一期，无需登录。")
        lines.append("")

    if hikes:
        lines.append(f"📈 涨价通知（{len(hikes)} 款）:")
        lines.append(f"最新涨价: {alert_report_url('rises', site_base_url)}\n")
        for index, e in enumerate(hikes[:5], 1):
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            lines.append(
                f"{index}. {_display_name(e.product_name, 160)}\n"
                f"现价: {symbol}{e.new_price:.2f} · 涨 {symbol}{diff_abs:.2f}\n"
                f"原价: {symbol}{e.old_price:.2f} · {_display_name(e.shop_name, 60)}\n"
                f"商品详情: {offer_detail_url(e.offer_id, site_base_url)}\n\n──────────\n"
            )
        lines.append("")

    lines.append(f"🔗 查看实时比价: {site_base_url}")
    lines.append(f"⏱ 检测时间: {now_str}")
    return "\n".join(lines)


def render_qq_team_reports(
    offers: list[Any], *, detected_at: datetime, site_base_url: str = "https://ai.pricememo.cn",
) -> list[str]:
    """Keep every qualifying offer, paging instead of dropping later results."""
    return list(iter_qq_team_reports(offers, detected_at=detected_at, site_base_url=site_base_url))


def iter_qq_team_reports(
    offers: list[Any], *, detected_at: datetime, site_base_url: str = "https://ai.pricememo.cn", current_time=None,
    stale_offer_hours: int | None = None,
):
    """Render each page immediately before delivery, dropping newly expired rows."""
    pending = unique_team_offers(offers)
    sent = 0
    title = 'OpenAI Team 头车≤¥30 / 其他≤¥20 提醒' if any(offer.is_head_car for offer in offers) else 'OpenAI Team ≤¥20 提醒'
    while pending:
        if current_time is not None:
            now = current_time()
            pending = [offer for offer in pending if offer.ends_at is not None and offer.ends_at > now
                       and fresh_alert_item(offer, now, stale_offer_hours)]
        if not pending:
            break
        total = sent + len(pending)
        header = (f"【PriceMemo {title}】\n同名取最低价 · {total} 款现货 · 时间均为北京时间\n"
                  f"最新 Team 车提醒: {alert_report_url('team', site_base_url)}\n\n")
        footer = f"\n\n⏱ 检测时间: {format_detection_time(detected_at)}"
        blocks = []
        for index, offer in enumerate(pending[:8], sent + 1):
            lines = [f"{index}. {_display_name(offer.product_name, 160)}\n现价: ¥{offer.price:.2f} · {_display_name(offer.shop_name, 60)}"]
            if offer.ends_at is not None:
                lines.append(f"结束时间: {format_end_time(offer.ends_at)}")
            lines.append(f"  🔗 商品详情: {offer_detail_url(offer.offer_id, site_base_url)}")
            block = "\n".join(lines)
            # Leave room for the item range. Each yielded page is one request,
            # so newly expired offers are checked again before the next send.
            if blocks and len((header + ITEM_SEPARATOR.join([*blocks, block]) + footer).encode("utf-8")) > 3430:
                break
            blocks.append(block)
        pending = pending[len(blocks):]
        item_range = f"（{sent + 1}–{sent + len(blocks)}/{total}）\n" if total > len(blocks) else ""
        sent += len(blocks)
        yield header + item_range + ITEM_SEPARATOR.join(blocks) + footer


def split_qq_messages(text: str, limit: int = 3500) -> list[str]:
    """Split QQ plain-text messages before the platform request is made.

    Product names and merchant URLs are untrusted and can make a nominal
    eight-item page exceed the platform's message limit. Prefer line breaks;
    hard-split an unusually long individual line so it cannot block delivery.
    """
    if len(text.encode("utf-8")) <= limit:
        return [text]
    if ITEM_SEPARATOR in text:
        chunks = []
        current = ""
        for block in text.split(ITEM_SEPARATOR):
            for part in split_qq_messages(block, limit=limit):
                candidate = current + (ITEM_SEPARATOR if current else "") + part
                if current and len(candidate.encode("utf-8")) > limit:
                    chunks.append(current)
                    current = part
                else:
                    current = candidate
        if current:
            chunks.append(current)
        return chunks
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        if "https://" in line and len(line.encode("utf-8")) > limit:
            line = "原站链接过长，请在官网查看该商品：https://ai.pricememo.cn/products"
        pieces = []
        piece = ""
        size = 0
        for char in line:
            width = len(char.encode("utf-8"))
            if size + width > limit:
                pieces.append(piece)
                piece, size = "", 0
            piece += char
            size += width
        pieces.append(piece)
        for piece in pieces:
            piece_len = len(piece.encode("utf-8"))
            needed = piece_len + (1 if current else 0)
            if current and current_len + needed > limit:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(piece)
            current_len += piece_len + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current))
    return chunks


def render_telegram_team_report(
    offers: list[Any], *, detected_at: datetime, site_base_url: str = "https://ai.pricememo.cn",
    total_count: int | None = None,
) -> str:
    offers = unique_team_offers(offers)
    title = 'OpenAI Team 头车≤¥30 / 其他≤¥20 提醒' if any(offer.is_head_car for offer in offers) else 'OpenAI Team ≤¥20 提醒'
    lines = [f"🔔 <b>【PriceMemo {title}】</b>", f"本次快照共 {total_count if total_count is not None else len(offers)} 款现货符合条件", ""]
    lines.append(f'<a href="{_esc_attr(alert_report_url("team", site_base_url))}">查看最新 Team 车提醒</a>\n时间均为北京时间\n')
    for offer in offers:
        lines.append(f"• <b>{_esc(_display_name(offer.product_name))}</b> ({_esc(_display_name(offer.shop_name, 80))})\n  现价: <b>¥{offer.price:.2f}</b>")
        if offer.ends_at is not None:
            lines.append(f"  ⏳ 结束时间: {format_end_time(offer.ends_at)}")
        url = offer_detail_url(offer.offer_id, site_base_url)
        lines.append(f'  🔗 <a href="{_esc_attr(url)}">商品详情</a>')
        lines.append("\n──────────\n")
    lines.append(f"\n⏱ 检测时间: {format_detection_time(detected_at)}")
    return "\n".join(lines)


def iter_telegram_team_reports(offers: list[Any], *, detected_at: datetime,
                               site_base_url: str = "https://ai.pricememo.cn", current_time, stale_offer_hours: int | None = None):
    pending = unique_team_offers(offers)
    sent = 0
    while pending:
        now = current_time()
        pending = [offer for offer in pending if offer.ends_at is not None and offer.ends_at > now
                   and fresh_alert_item(offer, now, stale_offer_hours)]
        if not pending:
            break
        batch = []
        message = ""
        for offer in pending[:8]:
            candidate = render_telegram_team_report([*batch, offer], detected_at=detected_at,
                site_base_url=site_base_url, total_count=sent + len(pending))
            if batch and len(candidate) > 3900:
                break
            batch.append(offer)
            message = candidate
        pending = pending[len(batch):]
        sent += len(batch)
        yield message


def render_qq_group_digest(events: list[Any], offers: list[Any], *, detected_at: datetime | None,
                           site_base_url: str = "https://ai.pricememo.cn") -> str:
    """One short group message per snapshot; full lists live on the website."""
    events = unique_price_events(events)
    offers = unique_team_offers(offers)
    sections = []
    for is_drop, label, view in ((True, "降价", "drops"), (False, "涨价", "rises")):
        selected = [event for event in events if event.is_drop == is_drop]
        if not selected:
            continue
        lines = [f"{label} {len(selected)} 款"]
        for event in selected[:2]:
            symbol = format_currency_symbol(event.currency)
            lines.append(f"{_display_name(event.product_name, 66)}\n"
                         f"{symbol}{event.old_price:.2f} → {symbol}{event.new_price:.2f} · {_display_name(event.shop_name, 20)}")
        lines.append(f"最新{label}榜: {alert_report_url(view, site_base_url)}")
        sections.append("\n\n".join(lines))
    if offers:
        lines = [f"Team 车 {len(offers)} 款 · 头车≤¥30 / 其他≤¥20"]
        for offer in offers[:3]:
            ending = f" · {format_end_time(offer.ends_at)}结束" if offer.ends_at else ""
            lines.append(f"{_display_name(offer.product_name, 66)}\n"
                         f"¥{offer.price:.2f}{ending} · {_display_name(offer.shop_name, 20)}")
        lines.append(f"最新 Team 车提醒: {alert_report_url('team', site_base_url)}")
        sections.append("\n\n".join(lines))
    return (f"【PriceMemo 群比价快报】\n{format_detection_time(detected_at)}\n\n"
            + ITEM_SEPARATOR.join(sections)
            + "\n\n同名取最低价，完整清单见榜单。群管理员可发送「关闭群推送」停止提醒。")


def iter_price_reports(events, *, telegram: bool, detected_at, site_base_url, current_time, stale_offer_hours=None):
    """Keep pending rows until each outbound request, so expiry never drops fresh siblings."""
    drops = [event for event in events if event.is_drop][:15 if telegram else 8]
    rises = [event for event in events if not event.is_drop][:10 if telegram else 5]
    pending = drops + rises
    renderer = render_telegram_report if telegram else render_qq_report
    while pending:
        now = current_time()
        pending = [event for event in pending if fresh_alert_item(event, now, stale_offer_hours)]
        if not pending:
            break
        batch, message = [], ""
        for event in pending:
            candidate = renderer([*batch, event], detected_at=detected_at, site_base_url=site_base_url)
            size = len(candidate) if telegram else len(candidate.encode("utf-8"))
            if batch and size > (3900 if telegram else 3400):
                break
            batch.append(event)
            message = candidate
        pending = pending[len(batch):]
        yield message

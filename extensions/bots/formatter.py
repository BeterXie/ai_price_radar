from __future__ import annotations

import html
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


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


def _esc_attr(value: Any) -> str:
    """Escape dynamic text used inside an HTML attribute (e.g. href)."""
    return html.escape(str(value if value is not None else ""), quote=True)


def render_telegram_report(events: list[Any], site_base_url: str = "https://ai.pricememo.cn") -> str:
    """Render an HTML formatted report suitable for Telegram Bot HTML parse_mode.

    All dynamic fields are HTML-escaped: product/shop names containing `<` or `&`
    would otherwise be parsed as tags and make Telegram reject the whole message.
    """
    drops = [e for e in events if e.is_drop]
    hikes = [e for e in events if not e.is_drop]
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = ["🔔 <b>【PriceMemo 价格变动监控提醒】</b>", ""]

    if drops:
        lines.append(f"📉 <b>降价精选（共 {len(drops)} 款）:</b>")
        for e in drops[:15]:  # Limit top 15 in message to avoid payload size overflow
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            url = e.product_url or site_base_url
            lines.append(
                f"• <b>{_esc(e.product_name)}</b> ({_esc(e.shop_name)})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↓{symbol}{diff_abs}, <b>{e.percent_change}%</b>)\n"
                f"  🔗 <a href=\"{_esc_attr(url)}\">查看商品</a>"
            )
        if len(drops) > 15:
            lines.append(f"... 其余 {len(drops) - 15} 条降价详见官网")
        lines.append("")

    if hikes:
        lines.append(f"📈 <b>涨价变动（共 {len(hikes)} 款）:</b>")
        for e in hikes[:10]:
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            url = e.product_url or site_base_url
            lines.append(
                f"• <b>{_esc(e.product_name)}</b> ({_esc(e.shop_name)})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↑{symbol}{diff_abs}, +{e.percent_change}%)\n"
                f"  🔗 <a href=\"{_esc_attr(url)}\">查看商品</a>"
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


def render_qq_report(events: list[Any], site_base_url: str = "https://ai.pricememo.cn") -> str:
    """Render a clean plain-text/markdown report suitable for QQ Bot messages."""
    drops = [e for e in events if e.is_drop]
    hikes = [e for e in events if not e.is_drop]
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    lines = ["【PriceMemo 价格变动提醒】", ""]

    if drops:
        lines.append(f"📉 降价通知（{len(drops)} 款）:")
        for e in drops[:8]:
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            lines.append(
                f"• {e.product_name} ({e.shop_name})\n"
                f"  原价:{symbol}{e.old_price} -> 现价:{symbol}{e.new_price} (降{symbol}{diff_abs}, {e.percent_change}%)"
            )
        if len(drops) > 8:
            lines.append(f"... 其余 {len(drops) - 8} 条降价请登录官网查看")
        lines.append("")

    if hikes:
        lines.append(f"📈 涨价通知（{len(hikes)} 款）:")
        for e in hikes[:5]:
            symbol = format_currency_symbol(e.currency)
            diff_abs = abs(Decimal(str(e.diff)))
            lines.append(
                f"• {e.product_name} ({e.shop_name})\n"
                f"  原价:{symbol}{e.old_price} -> 现价:{symbol}{e.new_price} (涨{symbol}{diff_abs})"
            )
        lines.append("")

    lines.append(f"🔗 查看实时比价: {site_base_url}")
    lines.append(f"⏱ 检测时间: {now_str}")
    return "\n".join(lines)

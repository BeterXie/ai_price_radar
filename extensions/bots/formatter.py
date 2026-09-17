from __future__ import annotations

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


def render_telegram_report(events: list[Any], site_base_url: str = "https://ai.pricememo.cn") -> str:
    """Render an HTML formatted report suitable for Telegram Bot HTML parse_mode."""
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
                f"• <b>{e.product_name}</b> ({e.shop_name})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↓{symbol}{diff_abs}, <b>{e.percent_change}%</b>)\n"
                f"  🔗 <a href=\"{url}\">查看商品</a>"
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
                f"• <b>{e.product_name}</b> ({e.shop_name})\n"
                f"  原价: {symbol}{e.old_price} ➔ <b>现价: {symbol}{e.new_price}</b> "
                f"(↑{symbol}{diff_abs}, +{e.percent_change}%)\n"
                f"  🔗 <a href=\"{url}\">查看商品</a>"
            )
        if len(hikes) > 10:
            lines.append(f"... 其余 {len(hikes) - 10} 条涨价详见官网")
        lines.append("")

    lines.append(f"⏱ 同步检测时间: {now_str}")
    return "\n".join(lines)


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

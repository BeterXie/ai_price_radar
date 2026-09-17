from __future__ import annotations

import importlib
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PriceChangeEvent:
    offer_id: int
    product_name: str
    shop_name: str
    source_platform: str
    old_price: Decimal
    new_price: Decimal
    currency: str
    product_url: str
    is_drop: bool
    diff: Decimal
    percent_change: float
    product_slug: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["old_price"] = str(self.old_price)
        data["new_price"] = str(self.new_price)
        data["diff"] = str(self.diff)
        return data


def create_price_change_event(
    *,
    offer_id: int,
    product_name: str,
    shop_name: str,
    source_platform: str,
    old_price: Decimal,
    new_price: Decimal,
    currency: str = "CNY",
    product_url: str = "",
    product_slug: str = "",
) -> PriceChangeEvent | None:
    if old_price is None or new_price is None or old_price == new_price:
        return None
    diff = new_price - old_price
    is_drop = diff < 0
    percent = float((diff / old_price) * 100) if old_price != 0 else 0.0
    return PriceChangeEvent(
        offer_id=offer_id,
        product_name=product_name or "未分类商品",
        shop_name=shop_name or "未知店铺",
        source_platform=source_platform or "ldxp",
        old_price=old_price,
        new_price=new_price,
        currency=currency or "CNY",
        product_url=product_url or "",
        is_drop=is_drop,
        diff=diff,
        percent_change=round(percent, 2),
        product_slug=product_slug or "",
    )



def dispatch_price_changes(events: list[PriceChangeEvent], db_session: Any = None) -> None:
    """Safely dispatch price change events to private bots if installed.

    If extensions/bots is not installed (e.g. in public open-source repos),
    this gracefully logs and exits without interrupting pipeline execution.
    """
    if not events:
        return

    if db_session is not None:
        try:
            from sqlalchemy import select
            from app.models import SystemSetting
            s = db_session.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled"))
            if s and s.value and s.value.strip().lower() not in ("true", "1", "yes", "on"):
                logger.info("Bot notifications are disabled by admin; skipped dispatching %d events", len(events))
                return
        except Exception as exc:
            logger.debug("Failed checking bot_enabled setting: %s", exc)

    try:
        # Dynamically import private extensions module
        module = importlib.import_module("extensions.bots.dispatcher")
        dispatch_fn = getattr(module, "dispatch_price_changes", None)
        if callable(dispatch_fn):
            dispatch_fn(events, db_session=db_session)
        else:
            logger.debug("extensions.bots.dispatcher has no dispatch_price_changes function")
    except ImportError:
        logger.info(
            "Private bot extensions not installed; skipped dispatching %d price change event(s)",
            len(events),
        )
    except Exception as exc:
        logger.error("Error in private bot notification dispatcher: %s", exc, exc_info=True)


def handle_inbound_chat_message(
    text: str,
    sender_id: str = "",
    channel: str = "qq",
    db_session: Any = None,
) -> str:
    """Safely route inbound chat message to private bot command handler.

    If extensions/bots is not installed, returns a default fallback.
    """
    if db_session is not None:
        try:
            from sqlalchemy import select
            from app.models import SystemSetting
            s = db_session.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled"))
            if s and s.value and s.value.strip().lower() not in ("true", "1", "yes", "on"):
                return "🤖 机器人比价服务已由管理员暂时关闭。"
        except Exception as exc:
            logger.debug("Failed checking bot_enabled setting: %s", exc)

    try:
        module = importlib.import_module("extensions.bots.chat_commands")
        handler_fn = getattr(module, "handle_chat_command", None)
        if callable(handler_fn):
            return handler_fn(text, sender_id=sender_id, channel=channel, db=db_session)
    except ImportError:
        logger.info("Private bot extensions not installed; cannot handle chat command")
    except Exception as exc:
        logger.error("Error executing private bot chat command: %s", exc)
    return "🤖 机器人比价服务正在维护中，请稍后访问官网查看：https://ai.pricememo.cn"

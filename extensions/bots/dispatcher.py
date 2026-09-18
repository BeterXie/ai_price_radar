from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from .clawbot_client import ClawBotClient
from .formatter import render_qq_report, render_telegram_report
from .qq_bot import QQBotClient
from .telegram_bot import TelegramBotClient

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dispatch_price_changes(events: list[Any], db_session: Any = None) -> None:
    """Entry point called by apps/api/app/services/notification_hub.py.

    1. Checks user_product_subscriptions and dispatches personalized alerts:
       - Via Email (enqueued to NotificationOutbox)
       - Via Bound Bot (Tencent ClawBot / QQ Bot)
    2. Dispatches admin summary report to Telegram Bot.
    3. Dispatches general updates to active QQ Bot bindings.
    """
    if not events:
        return

    site_url = os.getenv("NEXT_PUBLIC_SITE_URL", "https://ai.pricememo.cn").rstrip("/")

    # 1. Targeted Subscriptions Dispatch (Email & Personal Bot)
    if db_session is not None:
        try:
            from app.models import NotificationOutbox, Offer, Product, User, UserBotBinding, UserProductSubscription
            from app.services.credential_crypto import decrypt_bot_token

            # Cache product slugs from offer_id if not present
            offer_slug_cache: dict[int, str] = {}

            for evt in events:
                slug = getattr(evt, "product_slug", "") or ""
                if not slug:
                    offer_id = getattr(evt, "offer_id", None)
                    if offer_id:
                        if offer_id not in offer_slug_cache:
                            prod_slug = db_session.scalar(
                                select(Product.slug)
                                .join(Offer, Offer.product_id == Product.id)
                                .where(Offer.id == offer_id)
                            )
                            offer_slug_cache[offer_id] = prod_slug or ""
                        slug = offer_slug_cache.get(offer_id, "")

                if not slug:
                    continue

                is_drop = getattr(evt, "is_drop", False)
                new_price = getattr(evt, "new_price", Decimal(0))
                old_price = getattr(evt, "old_price", Decimal(0))
                diff = getattr(evt, "diff", Decimal(0))
                prod_name = getattr(evt, "product_name", "AI 订阅商品")
                shop_name = getattr(evt, "shop_name", "精选店铺")
                prod_url = getattr(evt, "product_url", "") or f"{site_url}/products/{slug}"

                # Query users subscribed to this product
                sub_rows = list(
                    db_session.execute(
                        select(UserProductSubscription, User)
                        .join(User, UserProductSubscription.user_id == User.id)
                        .where(
                            UserProductSubscription.product_slug == slug,
                            User.is_active == True,
                        )
                    ).all()
                )

                if not sub_rows:
                    continue

                for sub, user in sub_rows:
                    # `sub.notify_email` / `sub.notify_bot` gate the channels; the
                    # per-event drop/hike toggles live on the bot binding and are
                    # applied per binding below.
                    target_met = sub.target_price is not None and new_price <= sub.target_price
                    if not (is_drop or target_met):
                        continue

                    if is_drop:
                        subject_prefix = "降价提醒"
                        headline = f"您关注的「{prod_name}」降价至 ¥{new_price:.2f}！"
                        mail_intro = "您在 PriceMemo 关注的商品有最新降价动态："
                        change_line = f"📉 最新价格：¥{new_price:.2f} (原价 ¥{old_price:.2f}，直降 ¥{abs(diff):.2f})"
                        bot_headline = f"您关注的「{prod_name}」降价啦！"
                        bot_change = (
                            f"📉 最新现货价：¥{new_price:.2f}\n"
                            f"🏷️ 历史变动：¥{old_price:.2f} → ¥{new_price:.2f} (降 ¥{abs(diff):.2f})"
                        )
                    else:
                        subject_prefix = "到价提醒"
                        headline = f"您关注的「{prod_name}」已达到您的目标价 ¥{new_price:.2f}！"
                        mail_intro = "您在 PriceMemo 关注的商品已达到您设定的目标价："
                        change_line = f"🎯 当前价格：¥{new_price:.2f} (此前 ¥{old_price:.2f})"
                        bot_headline = f"您关注的「{prod_name}」已达目标价！"
                        bot_change = (
                            f"🎯 当前价格：¥{new_price:.2f}\n"
                            f"🏷️ 上次价格：¥{old_price:.2f}"
                        )

                    # Channel A: Email
                    if sub.notify_email and user.email:
                        # Key the dedupe on the actual price transition so a later,
                        # separate move to the same price is not suppressed.
                        email_key = f"sub-alert:{user.id}:{slug}:{int(old_price * 100)}:{int(new_price * 100)}"
                        existing = db_session.scalar(
                            select(NotificationOutbox.id).where(NotificationOutbox.dedupe_key == email_key)
                        )
                        if not existing:
                            now = utcnow()
                            db_session.add(
                                NotificationOutbox(
                                    event_type="price_subscription_alert",
                                    recipient=user.email,
                                    subject=f"【PriceMemo {subject_prefix}】{headline}",
                                    text_body=(
                                        f"尊敬的 {user.nickname or '用户'}，您好！\n\n"
                                        f"{mail_intro}\n\n"
                                        f"📦 商品名称：{prod_name}\n"
                                        f"{change_line}\n"
                                        f"🏪 店铺商家：{shop_name}\n"
                                        f"🎯 您的目标价：{'¥' + str(sub.target_price) if sub.target_price else '任意降价'}\n\n"
                                        f"🛒 直达查看比价详情：{site_url}/products/{slug}\n"
                                        f"🛒 店铺购买链接：{prod_url}\n\n"
                                        f"如需调整或取消订阅，请访问官网关注清单：{site_url}/watchlist\n\n"
                                        f"—— PriceMemo 比价雷达团队"
                                    ),
                                    dedupe_key=email_key,
                                    status="pending",
                                    next_attempt_at=now,
                                )
                            )
                            logger.info("Enqueued subscription price alert email to %s for %s", user.email, slug)

                    # Channel B: Personal Bot (ClawBot or QQ Bot)
                    if sub.notify_bot:
                        binding = db_session.scalar(
                            select(UserBotBinding).where(
                                UserBotBinding.user_id == user.id,
                                UserBotBinding.is_active == True,
                            )
                        )
                        # Respect the binding's own drop/hike toggles so a user who
                        # turned hikes off never receives a hike-flavored message.
                        if binding and binding.target_id:
                            wants_event = (
                                binding.notify_price_drop if is_drop else binding.notify_price_hike
                            )
                            if wants_event:
                                bot_msg = (
                                    f"🔔【PriceMemo {subject_prefix}】\n"
                                    f"{bot_headline}\n"
                                    f"------------------------------------\n"
                                    f"{bot_change}\n"
                                    f"🏪 报价店铺：{shop_name}\n"
                                    f"🎯 您的期望价：{'¥' + str(sub.target_price) if sub.target_price else '任意降价'}\n"
                                    f"------------------------------------\n"
                                    f"🔗 比价详情：{site_url}/products/{slug}\n"
                                    f"🛒 直达店铺：{prod_url}"
                                )
                                app_id = (binding.extra_meta or {}).get("app_id") if isinstance(binding.extra_meta, dict) else None
                                app_secret = decrypt_bot_token(binding.bot_token) or None
                                try:
                                    qq_client = QQBotClient(app_id=app_id, app_secret=app_secret)
                                    qq_client.send_c2c_message(
                                        binding.target_id,
                                        bot_msg,
                                        app_id=app_id,
                                        app_secret=app_secret,
                                    )
                                except Exception as q_err:
                                    logger.warning("Failed sending QQ Bot alert: %s", q_err)

            db_session.commit()

        except Exception as exc:
            logger.error("Error in targeted subscription dispatch: %s", exc, exc_info=True)

    # 2. Dispatch to Telegram Bot (Admin)
    telegram = TelegramBotClient()
    if telegram.is_configured:
        try:
            tg_text = render_telegram_report(events, site_base_url=site_url)
            delivered = telegram.send_admin_message(tg_text)
            if delivered:
                logger.info("Dispatched %d price change event(s) to Telegram Admin", len(events))
        except Exception as exc:
            logger.error("Failed dispatching price change report to Telegram: %s", exc)

    # 3. Dispatch to General Active QQ Bot Bindings
    if db_session is not None:
        try:
            from app.models import UserBotBinding

            bindings = list(
                db_session.scalars(
                    select(UserBotBinding).where(
                        UserBotBinding.channel == "qq",
                        UserBotBinding.is_active == True,
                    )
                )
            )

            sent_count = 0
            for binding in bindings:
                if not binding.target_id:
                    continue

                # Each binding only receives the events matching its own toggles,
                # so a drop-only subscriber never sees hike rows (and vice versa).
                allowed_events = [
                    e
                    for e in events
                    if (getattr(e, "is_drop", False) and binding.notify_price_drop)
                    or (not getattr(e, "is_drop", False) and binding.notify_price_hike)
                ]
                if not allowed_events:
                    continue

                app_id = (binding.extra_meta or {}).get("app_id") if isinstance(binding.extra_meta, dict) else None
                app_secret = decrypt_bot_token(binding.bot_token) or None
                # Build the client from this binding's credentials: Connector-based
                # bindings hold their own app_id/app_secret and may exist with no
                # global QQ_BOT_APP_ID/SECRET configured.
                qq = QQBotClient(app_id=app_id, app_secret=app_secret)
                if not qq.is_configured:
                    continue

                qq_text = render_qq_report(allowed_events, site_base_url=site_url)
                if qq.send_c2c_message(binding.target_id, qq_text, app_id=app_id, app_secret=app_secret):
                    sent_count += 1
            if sent_count:
                logger.info("Dispatched general price report to %d QQ Bot user(s)", sent_count)
        except Exception as exc:
            logger.error("Failed dispatching general price change report to QQ Bot users: %s", exc)

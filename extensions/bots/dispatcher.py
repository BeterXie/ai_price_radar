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
                    # Condition: price drop or target_price reached
                    target_met = sub.target_price is not None and new_price <= sub.target_price
                    should_alert = is_drop or target_met
                    if not should_alert:
                        continue

                    # Channel A: Email
                    if sub.notify_email and user.email:
                        email_key = f"sub-alert:{user.id}:{slug}:{int(new_price * 100)}"
                        existing = db_session.scalar(
                            select(NotificationOutbox.id).where(NotificationOutbox.dedupe_key == email_key)
                        )
                        if not existing:
                            now = utcnow()
                            db_session.add(
                                NotificationOutbox(
                                    event_type="price_subscription_alert",
                                    recipient=user.email,
                                    subject=f"【PriceMemo 降价提醒】您关注的「{prod_name}」降价至 ¥{new_price:.2f}！",
                                    text_body=(
                                        f"尊敬的 {user.nickname or '用户'}，您好！\n\n"
                                        f"您在 PriceMemo 关注的商品有最新降价动态：\n\n"
                                        f"📦 商品名称：{prod_name}\n"
                                        f"📉 最新价格：¥{new_price:.2f} (原价 ¥{old_price:.2f}，直降 ¥{abs(diff):.2f})\n"
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
                        if binding and binding.target_id:
                            bot_msg = (
                                f"🔔【PriceMemo 降价提醒】\n"
                                f"您关注的「{prod_name}」降价啦！\n"
                                f"------------------------------------\n"
                                f"📉 最新现货价：¥{new_price:.2f}\n"
                                f"🏷️ 历史变动：¥{old_price:.2f} → ¥{new_price:.2f} (降 ¥{abs(diff):.2f})\n"
                                f"🏪 报价店铺：{shop_name}\n"
                                f"🎯 您的期望价：{'¥' + str(sub.target_price) if sub.target_price else '任意降价'}\n"
                                f"------------------------------------\n"
                                f"🔗 比价详情：{site_url}/products/{slug}\n"
                                f"🛒 直达店铺：{prod_url}"
                            )
                            app_id = (binding.extra_meta or {}).get("app_id") if isinstance(binding.extra_meta, dict) else None
                            app_secret = binding.bot_token or None
                            try:
                                qq_client = QQBotClient()
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
    qq = QQBotClient()
    if qq.is_configured and db_session is not None:
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

            if bindings:
                qq_text = render_qq_report(events, site_base_url=site_url)
                sent_count = 0
                for binding in bindings:
                    if not binding.target_id or binding.bot_token:
                        # Skip if already handled via ClawBot targeted alert
                        continue
                    has_drops = any(getattr(e, "is_drop", False) for e in events)
                    has_hikes = any(not getattr(e, "is_drop", False) for e in events)
                    should_send = (has_drops and binding.notify_price_drop) or (
                        has_hikes and binding.notify_price_hike
                    )
                    if should_send:
                        if qq.send_c2c_message(binding.target_id, qq_text):
                            sent_count += 1
                if sent_count:
                    logger.info("Dispatched general price report to %d QQ Bot user(s)", sent_count)
        except Exception as exc:
            logger.error("Failed dispatching general price change report to QQ Bot users: %s", exc)

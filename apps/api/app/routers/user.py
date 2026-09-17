from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    CatalogSnapshot,
    CouponCampaign,
    Offer,
    Product,
    ShopCoupon,
    SystemSetting,
    User,
    UserBotBinding,
    UserProductSubscription,
)
from ..schemas import (
    BotCommandRequest,
    BotCommandResponse,
    CouponClaimResponse,
    CouponDropStatus,
    CouponRead,
    CouponRedeemRequest,
    QQBotBindingStartResponse,
    UserBotBindingRead,
    UserBotBindingUpdate,
    UserCouponListOut,
    UserRead,
    UserSubscriptionCreateOrUpdate,
    UserSubscriptionListOut,
    UserSubscriptionRead,
)
from ..security import get_current_user, require_current_user
from ..services.bot_binding import (
    bind_current_user_qq,
    check_qq_binding_session,
    complete_qq_binding,
    get_user_bindings,
    start_qq_binding_session,
    unbind_user_channel,
    update_binding_preferences,
)
from ..services.notification_hub import handle_inbound_chat_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])


def _is_bot_enabled(db: Session) -> bool:
    s = db.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled"))
    return True if not s or not s.value else s.value.strip().lower() in ("true", "1", "yes", "on")


def _binding_to_read(b: UserBotBinding) -> UserBotBindingRead:
    return UserBotBindingRead(
        id=b.id,
        channel=b.channel,
        target_id=b.target_id,
        is_active=b.is_active,
        notify_price_drop=b.notify_price_drop,
        notify_price_hike=b.notify_price_hike,
        created_at=b.created_at,
    )


@router.get("/profile")
def get_user_profile(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    bindings = get_user_bindings(db, current_user.id)
    qq_binding = next((b for b in bindings if b.channel == "qq"), None)
    return {
        "user": UserRead(
            id=current_user.id,
            email=current_user.email,
            nickname=current_user.nickname or (current_user.email.split("@")[0] if current_user.email else "用户"),
            avatar_url=current_user.avatar_url or "",
            has_qq_bound=bool(current_user.qq_openid),
            created_at=current_user.created_at,
        ),
        "qq_bot_binding": _binding_to_read(qq_binding) if qq_binding else None,
        "bot_enabled": _is_bot_enabled(db),
    }


def _subscription_to_read(
    sub: UserProductSubscription,
    db: Session,
    snapshot: CatalogSnapshot | None = None,
) -> UserSubscriptionRead:
    product = db.scalar(select(Product).where(Product.slug == sub.product_slug))
    p_name = product.display_name if product else sub.product_slug
    platform = product.platform if product else "AI"
    min_price = None
    stock_count = 0
    currency = "CNY"

    if snapshot is None:
        snapshot = db.scalar(
            select(CatalogSnapshot)
            .where(CatalogSnapshot.published_at.is_not(None))
            .order_by(CatalogSnapshot.id.desc())
            .limit(1)
        )

    if snapshot and product:
        min_offer = db.scalar(
            select(Offer)
            .where(
                Offer.snapshot_id == snapshot.id,
                Offer.product_id == product.id,
                Offer.is_comparable == True,
                Offer.stock_count > 0,
            )
            .order_by(Offer.price.asc())
            .limit(1)
        )
        if min_offer:
            min_price = min_offer.price
            stock_count = min_offer.stock_count
            currency = min_offer.currency or "CNY"

    return UserSubscriptionRead(
        id=sub.id,
        product_slug=sub.product_slug,
        product_name=p_name,
        platform=platform,
        target_price=sub.target_price,
        current_min_price=min_price,
        current_currency=currency,
        stock_count=stock_count,
        notify_email=sub.notify_email,
        notify_bot=sub.notify_bot,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.get("/subscriptions", response_model=UserSubscriptionListOut)
def get_user_subscriptions(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserSubscriptionListOut:
    subs = list(
        db.scalars(
            select(UserProductSubscription)
            .where(UserProductSubscription.user_id == current_user.id)
            .order_by(UserProductSubscription.id.desc())
        )
    )
    snapshot = db.scalar(
        select(CatalogSnapshot)
        .where(CatalogSnapshot.published_at.is_not(None))
        .order_by(CatalogSnapshot.id.desc())
        .limit(1)
    )
    items = [_subscription_to_read(s, db, snapshot) for s in subs]
    bindings = get_user_bindings(db, current_user.id)
    bot_bound = any(b.is_active for b in bindings)
    email_bound = bool(current_user.email)
    return UserSubscriptionListOut(
        items=items,
        count=len(items),
        email_bound=email_bound,
        bot_bound=bot_bound,
    )


@router.post("/subscriptions", response_model=UserSubscriptionRead)
def create_or_update_subscription(
    payload: UserSubscriptionCreateOrUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserSubscriptionRead:
    clean_slug = payload.product_slug.strip().casefold()
    product = db.scalar(select(Product).where(Product.slug == clean_slug))
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"商品「{clean_slug}」不存在")

    sub = db.scalar(
        select(UserProductSubscription).where(
            UserProductSubscription.user_id == current_user.id,
            UserProductSubscription.product_slug == clean_slug,
        )
    )
    now = datetime.now(timezone.utc)
    if sub is None:
        sub = UserProductSubscription(
            user_id=current_user.id,
            product_slug=clean_slug,
            target_price=payload.target_price,
            notify_email=payload.notify_email,
            notify_bot=payload.notify_bot,
            created_at=now,
            updated_at=now,
        )
        db.add(sub)
    else:
        sub.target_price = payload.target_price
        sub.notify_email = payload.notify_email
        sub.notify_bot = payload.notify_bot
        sub.updated_at = now

    db.commit()
    db.refresh(sub)
    return _subscription_to_read(sub, db)


@router.delete("/subscriptions/{slug}")
def delete_subscription(
    slug: str,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    clean_slug = slug.strip().casefold()
    res = db.execute(
        delete(UserProductSubscription).where(
            UserProductSubscription.user_id == current_user.id,
            UserProductSubscription.product_slug == clean_slug,
        )
    )
    db.commit()
    return {"success": bool(res.rowcount and res.rowcount > 0)}



@router.post("/notifications/qq/start", response_model=QQBotBindingStartResponse)
def start_qq_binding(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> QQBotBindingStartResponse:
    if not _is_bot_enabled(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="机器人功能已由管理员暂时关闭")
    res = start_qq_binding_session(current_user.id)
    return QQBotBindingStartResponse(
        session_id=res["session_id"],
        bind_code=res["bind_code"],
        qrcode_url=res.get("qrcode_url", ""),
        expires_in_seconds=res["expires_in_seconds"],
        instruction=res["instruction"],
    )


@router.get("/notifications/qq/status")
def get_qq_binding_status(
    session_id: str,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return check_qq_binding_session(session_id, db=db)


@router.post("/notifications/qq/bind-current")
def bind_current_qq(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Instantly bind bot using already authenticated QQ account."""
    if not _is_bot_enabled(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="机器人功能已由管理员暂时关闭")
    binding = bind_current_user_qq(db, current_user)
    if binding is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前账号尚未关联 QQ，请使用下方扫码绑定")
    return {"success": True, "binding": _binding_to_read(binding)}


@router.post("/notifications/qq/confirm")
def manual_confirm_qq_binding(
    bind_code: str,
    target_id: str,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fallback manual binding endpoint: bind by entering QQ ID / OpenID with the code."""
    if not _is_bot_enabled(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="机器人功能已由管理员暂时关闭")
    binding = complete_qq_binding(db, bind_code, target_id)
    if binding is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="绑定码无效或已失效")
    return {"success": True, "binding": _binding_to_read(binding)}


@router.put("/notifications/qq", response_model=UserBotBindingRead)
def update_qq_notification_preferences(
    payload: UserBotBindingUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserBotBindingRead:
    binding = update_binding_preferences(
        db,
        current_user.id,
        channel="qq",
        is_active=payload.is_active,
        notify_price_drop=payload.notify_price_drop,
        notify_price_hike=payload.notify_price_hike,
    )
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未绑定 QQ 机器人")
    return _binding_to_read(binding)


@router.delete("/notifications/qq")
def unbind_qq_bot(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    success = unbind_user_channel(db, current_user.id, channel="qq")
    return {"success": success}


@router.post("/notifications/bot/command", response_model=BotCommandResponse)
def execute_bot_command(
    payload: BotCommandRequest,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BotCommandResponse:
    """Execute or simulate a bot chat command (e.g. plus, pro, 行情, 我的, 暂停推送)."""
    sender_id = payload.sender_id
    if not sender_id and current_user:
        bindings = get_user_bindings(db, current_user.id)
        bound = next((b for b in bindings if b.channel == payload.channel), None)
        if bound:
            sender_id = bound.target_id
        elif current_user.qq_openid and payload.channel == "qq":
            sender_id = current_user.qq_openid
        else:
            sender_id = f"user_{current_user.id}"

    reply = handle_inbound_chat_message(
        text=payload.text,
        sender_id=sender_id,
        channel=payload.channel,
        db_session=db,
    )
    return BotCommandResponse(reply=reply)


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coupon_to_read(c: ShopCoupon) -> CouponRead:
    return CouponRead(
        id=c.id,
        name=c.name,
        code=c.code,
        discount_amount=c.discount_amount,
        min_spend=c.min_spend,
        shop_name=c.shop_name,
        shop_url=c.shop_url,
        is_assigned=c.is_assigned,
        assigned_at=c.assigned_at,
        expires_at=c.expires_at,
        is_used=c.is_used,
        created_at=c.created_at,
        coupon_batch_id=getattr(c, "coupon_batch_id", 0) or 0,
        campaign_id=getattr(c, "campaign_id", None),
    )


@router.get("/coupons", response_model=UserCouponListOut)
def list_user_coupons(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserCouponListOut:
    """List all shop coupons assigned to current user."""
    coupons = (
        db.scalars(
            select(ShopCoupon)
            .where(ShopCoupon.assigned_user_id == current_user.id)
            .order_by(ShopCoupon.assigned_at.desc(), ShopCoupon.id.desc())
        )
        .all()
    )
    return UserCouponListOut(
        items=[_coupon_to_read(c) for c in coupons],
        count=len(coupons),
    )


@router.post("/coupons/redeem", response_model=CouponClaimResponse)
def redeem_coupon(
    payload: CouponRedeemRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> CouponClaimResponse:
    """Redeem a coupon using a campaign code (e.g. RADAR888) or direct coupon code."""
    raw_code = payload.code.strip()
    if not raw_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码不能为空")

    now = datetime.now(timezone.utc)

    # 1. Check if it matches a marketing campaign code (case-insensitive)
    campaign = db.scalar(
        select(CouponCampaign).where(
            CouponCampaign.campaign_code.ilike(raw_code),
            CouponCampaign.is_active.is_(True),
        )
    )
    if campaign:
        if _ensure_utc(campaign.expires_at) < now:
            return CouponClaimResponse(success=False, message="该活动口令已过期", coupon=None)
        if campaign.claimed_count >= campaign.total_quota:
            return CouponClaimResponse(success=False, message="该活动口令名额已被领完", coupon=None)

        # Check how many coupons this user has already claimed from this specific campaign
        user_claimed_count = (
            db.scalar(
                select(func.count(ShopCoupon.id)).where(
                    ShopCoupon.assigned_user_id == current_user.id,
                    ShopCoupon.campaign_id == campaign.id,
                )
            )
            or 0
        )
        if user_claimed_count >= campaign.max_per_user:
            return CouponClaimResponse(
                success=False,
                message=f"您已参与过该活动（每人限领 {campaign.max_per_user} 张），已保存在您的卡包中",
                coupon=None,
            )

        # Find an unassigned coupon from the pool
        query = select(ShopCoupon).where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.expires_at > now,
        )
        coupon = None
        if campaign.coupon_batch_id > 0:
            coupon = db.scalar(
                query.where(ShopCoupon.coupon_batch_id == campaign.coupon_batch_id)
                .order_by(ShopCoupon.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        # If no specific batch coupon found, fallback to unassigned general coupons
        if not coupon:
            coupon = db.scalar(
                query.order_by(ShopCoupon.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        if not coupon:
            return CouponClaimResponse(success=False, message="优惠券库存暂时不足，请稍后再试", coupon=None)

        coupon.is_assigned = True
        coupon.assigned_user_id = current_user.id
        coupon.assigned_at = now
        coupon.campaign_id = campaign.id
        campaign.claimed_count += 1
        db.commit()
        db.refresh(coupon)
        return CouponClaimResponse(
            success=True,
            message=f"兑换成功！已将【{coupon.name}】存入您的卡包",
            coupon=_coupon_to_read(coupon),
        )

    # 2. Check if it's a direct coupon code in shop_coupons
    direct_coupon = db.scalar(
        select(ShopCoupon).where(ShopCoupon.code == raw_code)
    )
    if direct_coupon:
        if direct_coupon.assigned_user_id == current_user.id:
            return CouponClaimResponse(
                success=True,
                message="该优惠券已在您的卡包中，无需重复兑换",
                coupon=_coupon_to_read(direct_coupon),
            )
        if direct_coupon.is_assigned:
            return CouponClaimResponse(success=False, message="该优惠券码已被其他用户兑换", coupon=None)
        if _ensure_utc(direct_coupon.expires_at) < now:
            return CouponClaimResponse(success=False, message="该优惠券码已过期", coupon=None)

        direct_coupon.is_assigned = True
        direct_coupon.assigned_user_id = current_user.id
        direct_coupon.assigned_at = now
        db.commit()
        db.refresh(direct_coupon)
        return CouponClaimResponse(
            success=True,
            message=f"兑换成功！已将【{direct_coupon.name}】存入您的卡包",
            coupon=_coupon_to_read(direct_coupon),
        )

    return CouponClaimResponse(success=False, message="未找到对应的兑换码或活动口令", coupon=None)


def _get_setting_bool(db: Session, key: str, default: bool = True) -> bool:
    s = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not s or not s.value:
        return default
    return s.value.strip().lower() in ("true", "1", "yes", "on")


def _get_setting_int(db: Session, key: str, default: int = 0) -> int:
    s = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not s or not s.value:
        return default
    try:
        return int(s.value.strip())
    except (ValueError, TypeError):
        return default


@router.get("/coupons/drop-status", response_model=CouponDropStatus)
def get_coupon_drop_status(db: Session = Depends(get_db)) -> CouponDropStatus:
    """Check if lucky drop is enabled, its current dynamic probability, and remaining stock."""
    drop_enabled = _get_setting_bool(db, "coupon_drop_enabled", default=True)
    if not drop_enabled:
        return CouponDropStatus(enabled=False, probability=0, has_stock=False, remaining_stock=0)

    now = datetime.now(timezone.utc)
    remaining_stock = (
        db.scalar(
            select(func.count(ShopCoupon.id)).where(
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.expires_at > now,
            )
        )
        or 0
    )

    if remaining_stock <= 0:
        return CouponDropStatus(enabled=True, probability=0, has_stock=False, remaining_stock=0)

    base_prob = _get_setting_int(db, "coupon_drop_probability", default=20)
    dynamic_drop = _get_setting_bool(db, "coupon_dynamic_drop", default=True)

    probability = base_prob
    if dynamic_drop:
        # Dynamic rate scaling based on remaining unassigned coupons
        if remaining_stock < 5:
            probability = min(base_prob, 5)
        elif remaining_stock < 20:
            probability = min(base_prob, 15)

    return CouponDropStatus(
        enabled=True,
        probability=max(0, min(100, probability)),
        has_stock=True,
        remaining_stock=remaining_stock,
    )


@router.post("/coupons/claim-drop", response_model=CouponClaimResponse)
def claim_lucky_drop(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> CouponClaimResponse:
    """Claim a lucky easter egg drop coupon (rate-limited to 1 per user per 24 hours)."""
    if not _get_setting_bool(db, "coupon_drop_enabled", default=True):
        return CouponClaimResponse(success=False, message="优惠券掉落活动已暂时关闭", coupon=None)

    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(hours=24)

    # Daily global drop limit check
    daily_limit = _get_setting_int(db, "coupon_daily_drop_limit", default=100)
    if daily_limit > 0:
        today_claimed = (
            db.scalar(
                select(func.count(ShopCoupon.id)).where(
                    ShopCoupon.assigned_at >= cooldown_cutoff
                )
            )
            or 0
        )
        if today_claimed >= daily_limit:
            return CouponClaimResponse(
                success=False,
                message="今日专享优惠券发放已达上限，感谢支持，明天继续掉落哦~",
                coupon=None,
            )

    # Frequency check: Has user claimed a drop in last 24h?
    recent_coupon = db.scalar(
        select(ShopCoupon)
        .where(
            ShopCoupon.assigned_user_id == current_user.id,
            ShopCoupon.campaign_id.is_(None),
            ShopCoupon.assigned_at >= cooldown_cutoff,
        )
        .order_by(ShopCoupon.assigned_at.desc())
        .limit(1)
    )
    if recent_coupon:
        return CouponClaimResponse(
            success=False,
            message="您在 24 小时内已领取过专属立减券啦，已在您的卡包中生效！",
            coupon=_coupon_to_read(recent_coupon),
        )

    # Find an available unassigned valid coupon with row-level lock
    coupon = db.scalar(
        select(ShopCoupon)
        .where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.expires_at > now,
        )
        .order_by(ShopCoupon.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not coupon:
        return CouponClaimResponse(
            success=False,
            message="今日专享优惠券已被抢光啦，感谢支持，明天继续掉落哦~",
            coupon=None,
        )

    coupon.is_assigned = True
    coupon.assigned_user_id = current_user.id
    coupon.assigned_at = now
    db.commit()
    db.refresh(coupon)
    return CouponClaimResponse(
        success=True,
        message=f"🎉 恭喜获得彩头AI小铺【{coupon.name}】！已自动存入个人卡包。",
        coupon=_coupon_to_read(coupon),
    )



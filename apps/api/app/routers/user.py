import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import secrets
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
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
    UserActionLog,
    UserBotBinding,
    UserProductSubscription,
    UserSession,
)
from ..schemas import (
    BotCommandRequest,
    BotCommandResponse,
    CouponClaimResponse,
    CouponDropClaimRequest,
    CouponDropQualificationResponse,
    CouponDropStatus,
    CouponDropTrackRequest,
    CouponRead,
    CouponRedeemRequest,
    PasswordUpdateResponse,
    QQBotBindingStartResponse,
    SetPasswordRequest,
    UserBotBindingRead,
    UserBotBindingUpdate,
    UserCouponListOut,
    UserHeartbeatResponse,
    UserRead,
    UserSubscriptionCreateOrUpdate,
    UserSubscriptionPatch,
    UserSubscriptionListOut,
    UserSubscriptionRead,
    UserTrackClickRequest,
)
from ..security import get_current_user, get_token_from_request, require_current_user
from ..services.auth import _session_token_digest, get_session_by_token, settle_session_activity
from ..services.bot_binding import (
    bind_current_user_qq,
    check_qq_binding_session,
    get_user_bindings,
    start_qq_binding_session,
    unbind_user_channel,
    update_binding_preferences,
)
from ..core.config import get_settings
from ..services.catalog import _base_public_offer_query
from ..services.notification_hub import handle_inbound_chat_message
from ..services.source_platform import public_https_url_or_empty

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])

# Serializes lucky-drop claims within this process so per-user and global daily
# limits cannot be raced by concurrent requests (single-instance deployment).
_CLAIM_DROP_LOCK = threading.Lock()
_DROP_TOKEN_TTL_SECONDS = 15 * 60


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcard characters so codes match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _drop_probability(db: Session, remaining_stock: int) -> int:
    base_prob = _get_setting_int(db, "coupon_drop_probability", default=20)
    if _get_setting_bool(db, "coupon_dynamic_drop", default=True):
        if remaining_stock < 5:
            base_prob = min(base_prob, 5)
        elif remaining_stock < 20:
            base_prob = min(base_prob, 15)
    return max(0, min(100, base_prob))


def _encode_drop_claim_token(*, issued_at: datetime) -> str:
    payload = {
        "exp": int(issued_at.timestamp()) + _DROP_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(24),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(
        get_settings().session_secret_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _validate_drop_claim_token(token: str, *, now: datetime) -> str | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(
            get_settings().session_secret_key.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if int(payload.get("exp", 0)) < int(now.timestamp()):
            return None
        nonce = str(payload.get("nonce") or "")
        if len(nonce) < 20:
            return None
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


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
            has_password=bool(current_user.password_hash),
            created_at=current_user.created_at,
        ),
        "qq_bot_binding": _binding_to_read(qq_binding) if qq_binding else None,
        "bot_enabled": _is_bot_enabled(db),
    }


@router.post("/password", response_model=PasswordUpdateResponse)
def set_user_password(
    payload: SetPasswordRequest,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> PasswordUpdateResponse:
    """Set a login password (first time) or change the existing one.

    First-time setup is allowed for any authenticated session because the
    session itself was established through a verified channel (email code or
    QQ OAuth). Changing an existing password requires the current password.
    """
    from .public import _client_address, _enforce_client_rate_limit
    from ..services.password_auth import hash_password, validate_password_strength, verify_password

    # Per-user limiter: throttles in-session guessing of the current password.
    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"user-password-{current_user.id}",
        max_requests=20,
        window_seconds=600,
        detail="密码操作过于频繁，请稍后再试",
    )

    if not (current_user.email or "").strip():
        return PasswordUpdateResponse(
            success=False,
            message="当前账号未绑定邮箱，暂不支持密码登录；请使用 QQ 扫码或邮箱验证码登录",
            has_password=bool(current_user.password_hash),
        )

    has_password = bool(current_user.password_hash)
    if has_password:
        if not payload.current_password:
            return PasswordUpdateResponse(success=False, message="请输入当前密码", has_password=True)
        if not verify_password(payload.current_password, current_user.password_hash):
            return PasswordUpdateResponse(success=False, message="当前密码不正确", has_password=True)

    policy_error = validate_password_strength(payload.password)
    if policy_error:
        return PasswordUpdateResponse(success=False, message=policy_error, has_password=has_password)

    client_ip = _client_address(request)
    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)
    current_user.password_hash = hash_password(payload.password)
    current_user.updated_at = now
    db.add(
        UserActionLog(
            user_id=current_user.id,
            action_type="password_change" if has_password else "password_set",
            action_name="修改登录密码" if has_password else "设置登录密码",
            ip_address=client_ip,
            user_agent=ua,
            created_at=now,
        )
    )
    if has_password:
        # Credential rotation: revoke every other session so a leaked old
        # password cannot keep an attacker's session alive. The session making
        # this change stays signed in (match both digest and legacy plaintext).
        current_token = get_token_from_request(request)
        current_digest = _session_token_digest(current_token) if current_token else ""
        db.execute(
            delete(UserSession).where(
                UserSession.user_id == current_user.id,
                UserSession.token != current_digest,
                UserSession.token != (current_token or ""),
            )
        )
    db.commit()
    return PasswordUpdateResponse(
        success=True,
        message="登录密码已修改，其他设备已退出登录" if has_password else "登录密码已设置，下次可直接用邮箱 + 密码登录",
        has_password=True,
    )


def _subscription_to_read(
    sub: UserProductSubscription,
    db: Session,
    snapshot: CatalogSnapshot | None = None,
) -> UserSubscriptionRead:
    product = db.scalar(
        select(Product).where(Product.slug == sub.product_slug, Product.is_visible.is_(True))
    )
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
            _base_public_offer_query(db, include_details=False, snapshot=snapshot)
            .where(
                Offer.product_id == product.id,
                Offer.is_comparable.is_(True),
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
    product = db.scalar(
        select(Product).where(Product.slug == clean_slug, Product.is_visible.is_(True))
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"商品「{clean_slug}」不存在")

    sub = db.scalar(
        select(UserProductSubscription).where(
            UserProductSubscription.user_id == current_user.id,
            UserProductSubscription.product_slug == clean_slug,
        ).with_for_update()
    )
    now = datetime.now(timezone.utc)
    if sub is None:
        try:
            with db.begin_nested():
                sub = UserProductSubscription(
                    user_id=current_user.id,
                    product_slug=clean_slug,
                    created_at=now,
                    updated_at=now,
                )
                db.add(sub)
                db.flush()
        except IntegrityError:
            sub = db.scalar(
                select(UserProductSubscription)
                .where(
                    UserProductSubscription.user_id == current_user.id,
                    UserProductSubscription.product_slug == clean_slug,
                )
                .with_for_update()
            )
            if sub is None:
                raise
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


@router.patch("/subscriptions/{slug}", response_model=UserSubscriptionRead)
def patch_subscription(
    slug: str,
    payload: UserSubscriptionPatch,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserSubscriptionRead:
    clean_slug = slug.strip().casefold()
    sub = db.scalar(
        select(UserProductSubscription).where(
            UserProductSubscription.user_id == current_user.id,
            UserProductSubscription.product_slug == clean_slug,
        )
    )
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关注记录不存在")
    fields = payload.model_fields_set
    if not fields:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="至少提供一个更新字段")
    if "target_price" in fields:
        sub.target_price = payload.target_price
    if "notify_email" in fields:
        sub.notify_email = bool(payload.notify_email)
    if "notify_bot" in fields:
        sub.notify_bot = bool(payload.notify_bot)
    sub.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sub)
    return _subscription_to_read(sub, db)



@router.post("/notifications/qq/start", response_model=QQBotBindingStartResponse)
def start_qq_binding(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> QQBotBindingStartResponse:
    if not _is_bot_enabled(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="机器人功能已由管理员暂时关闭")
    res = start_qq_binding_session(db, current_user.id)
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
    return check_qq_binding_session(session_id, db=db, user_id=current_user.id)


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
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> BotCommandResponse:
    """Execute or simulate a bot chat command (e.g. plus, pro, 行情, 我的, 暂停推送).

    Identity is always derived from the authenticated user's own bindings;
    payload.sender_id is intentionally ignored (an anonymous caller must never
    be able to impersonate another user by supplying a known target id).
    """
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
        shop_id=getattr(c, "shop_id", None),
        shop_name=c.shop_name,
        shop_url=public_https_url_or_empty(c.shop_url),
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
    request: Request,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> CouponClaimResponse:
    """Redeem a coupon using a campaign code (e.g. RADAR888) or direct coupon code."""
    raw_code = payload.code.strip()
    if not raw_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码不能为空")

    from .public import _client_address, _enforce_client_rate_limit

    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"coupon-redeem-user-{current_user.id}",
        max_requests=20,
        window_seconds=10 * 60,
        detail="兑换尝试过于频繁，请稍后再试",
    )
    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"coupon-redeem-ip-{_client_address(request)}",
        max_requests=40,
        window_seconds=10 * 60,
        detail="兑换尝试过于频繁，请稍后再试",
    )

    now = datetime.now(timezone.utc)

    # 1. Check if it matches a marketing campaign code (case-insensitive, literal match)
    campaign = db.scalar(
        select(CouponCampaign).where(
            CouponCampaign.campaign_code.ilike(_escape_like(raw_code), escape="\\"),
            CouponCampaign.is_active.is_(True),
        )
    )
    if campaign:
        # Lock the campaign row (Postgres) so quota / per-user checks and the
        # claim below happen inside one serialized critical section per campaign.
        campaign = db.scalar(
            select(CouponCampaign).where(CouponCampaign.id == campaign.id).with_for_update()
        )
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
                message=f"您已参与过该活动（每人限领 {campaign.max_per_user} 张），优惠券已保存在“我的优惠券”中",
                coupon=None,
            )

        # Find an unassigned coupon from the pool strictly for this shop
        query = select(ShopCoupon).where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.is_used.is_(False),
            ShopCoupon.expires_at > now,
        )
        if campaign.shop_id:
            query = query.where(ShopCoupon.shop_id == campaign.shop_id)
        elif campaign.shop_url:
            normalized_shop_url = campaign.shop_url.strip().rstrip("/").casefold()
            query = query.where(
                func.lower(func.rtrim(ShopCoupon.shop_url, "/")) == normalized_shop_url
            )

        coupon = None
        if campaign.coupon_batch_id > 0:
            coupon = db.scalar(
                query.where(ShopCoupon.coupon_batch_id == campaign.coupon_batch_id)
                .order_by(ShopCoupon.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        # If no specific batch coupon found, fallback to unassigned coupons of the same shop
        if not coupon:
            coupon = db.scalar(
                query.order_by(ShopCoupon.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        if not coupon:
            shop_label = campaign.shop_name or "该店铺"
            return CouponClaimResponse(
                success=False,
                message=f"{shop_label}专属优惠券已被领完或库存不足",
                coupon=None,
            )

        coupon.is_assigned = True
        coupon.assigned_user_id = current_user.id
        coupon.assigned_at = now
        coupon.campaign_id = campaign.id
        # Atomic quota increment; loses the coupon claim if another request took
        # the last slot between the check above and this update.
        quota_taken = db.execute(
            update(CouponCampaign)
            .where(
                CouponCampaign.id == campaign.id,
                CouponCampaign.claimed_count < CouponCampaign.total_quota,
            )
            .values(claimed_count=CouponCampaign.claimed_count + 1)
        )
        if quota_taken.rowcount != 1:
            db.rollback()
            return CouponClaimResponse(success=False, message="该活动口令名额已被领完", coupon=None)
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
        if direct_coupon.is_used:
            return CouponClaimResponse(success=False, message="该优惠券码已核销", coupon=None)
        if _ensure_utc(direct_coupon.expires_at) < now:
            return CouponClaimResponse(success=False, message="该优惠券码已过期", coupon=None)

        # Atomic claim: only one concurrent request can flip is_assigned=False.
        claimed = db.execute(
            update(ShopCoupon)
            .where(
                ShopCoupon.id == direct_coupon.id,
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.is_used.is_(False),
            )
            .values(
                is_assigned=True,
                assigned_user_id=current_user.id,
                assigned_at=now,
            )
        )
        if claimed.rowcount != 1:
            return CouponClaimResponse(success=False, message="该优惠券码已被其他用户兑换", coupon=None)
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
                ShopCoupon.is_used.is_(False),
                ShopCoupon.expires_at > now,
            )
        )
        or 0
    )

    if remaining_stock <= 0:
        return CouponDropStatus(enabled=True, probability=0, has_stock=False, remaining_stock=0)

    return CouponDropStatus(
        enabled=True,
        probability=_drop_probability(db, remaining_stock),
        has_stock=True,
        remaining_stock=remaining_stock,
    )


@router.post("/coupons/claim-drop", response_model=CouponClaimResponse)
def claim_lucky_drop(
    payload: CouponDropClaimRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> CouponClaimResponse:
    """Claim a lucky easter egg drop coupon (rate-limited to 1 per user per 24 hours)."""
    if not _get_setting_bool(db, "coupon_drop_enabled", default=True):
        return CouponClaimResponse(success=False, message="优惠券掉落活动已暂时关闭", coupon=None)

    with _CLAIM_DROP_LOCK:
        now = datetime.now(timezone.utc)
        token_hash = _validate_drop_claim_token(payload.claim_token, now=now)
        if token_hash is None:
            return CouponClaimResponse(success=False, message="掉落资格无效或已过期，请重新参与活动", coupon=None)
        cooldown_cutoff = now - timedelta(hours=24)

        # Serialize per-user claims (Postgres row lock on the user) so the 24h
        # frequency check cannot be raced by concurrent requests of the same user.
        db.execute(select(User.id).where(User.id == current_user.id).with_for_update())

        token_used = db.scalar(
            select(UserActionLog.id).where(
                UserActionLog.action_type == "coupon_drop_claim_token",
                UserActionLog.target_id == token_hash,
            )
        )
        if token_used is not None:
            return CouponClaimResponse(success=False, message="该掉落资格已使用", coupon=None)

        # Daily global drop limit check
        daily_limit = _get_setting_int(db, "coupon_daily_drop_limit", default=100)
        if daily_limit > 0:
            today_claimed = (
                db.scalar(
                    select(func.count(UserActionLog.id)).where(
                        UserActionLog.action_type == "coupon_drop_claim_token",
                        UserActionLog.created_at >= cooldown_cutoff,
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
        recent_drop = db.scalar(
            select(UserActionLog)
            .where(
                UserActionLog.user_id == current_user.id,
                UserActionLog.action_type == "coupon_drop_claim_token",
                UserActionLog.created_at >= cooldown_cutoff,
            )
            .order_by(UserActionLog.created_at.desc(), UserActionLog.id.desc())
            .limit(1)
        )
        if recent_drop:
            coupon_id = (recent_drop.extra_data or {}).get("coupon_id")
            recent_coupon = db.get(ShopCoupon, coupon_id) if isinstance(coupon_id, int) else None
            if recent_coupon is None:
                recent_coupon = db.scalar(
                    select(ShopCoupon)
                    .where(
                        ShopCoupon.assigned_user_id == current_user.id,
                        ShopCoupon.assigned_at >= recent_drop.created_at,
                    )
                    .order_by(ShopCoupon.assigned_at.asc(), ShopCoupon.id.asc())
                    .limit(1)
                )
            return CouponClaimResponse(
                success=False,
                message="您在 24 小时内已领取过专属立减券啦，已在您的卡包中生效！",
                coupon=_coupon_to_read(recent_coupon) if recent_coupon else None,
            )

        # Find an available unassigned valid coupon with row-level lock
        coupon = db.scalar(
            select(ShopCoupon)
            .where(
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.is_used.is_(False),
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
        db.add(
            UserActionLog(
                user_id=current_user.id,
                action_type="coupon_drop_claim_token",
                action_name="消费优惠券掉落资格",
                target_id=token_hash,
                extra_data={"coupon_id": coupon.id},
                created_at=now,
            )
        )
        db.add(
            UserActionLog(
                user_id=current_user.id,
                action_type="coupon_claim",
                action_name=f"领取优惠券: {coupon.name}",
                target_id=str(coupon.id),
                extra_data={"code": coupon.code, "shop_name": coupon.shop_name, "discount": str(coupon.discount_amount)},
                created_at=now,
            )
        )
        db.commit()
        db.refresh(coupon)
    return CouponClaimResponse(
        success=True,
        message=f"🎉 恭喜获得{coupon.shop_name or '店铺'}【{coupon.name}】！已自动存入个人卡包。",
        coupon=_coupon_to_read(coupon),
    )


@router.post("/coupons/record-drop-trigger", response_model=CouponDropQualificationResponse)
def record_coupon_drop_trigger(
    payload: CouponDropTrackRequest,
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CouponDropQualificationResponse:
    """Perform the server-side drop draw and return a signed claim capability."""
    from .public import _client_address, _enforce_client_rate_limit

    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"coupon-drop-draw-{current_user.id if current_user else 'anonymous'}",
        max_requests=1,
        window_seconds=60,
        detail="掉落抽签过于频繁，请稍后再试",
    )
    client_ip = _client_address(request)
    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)

    user_id = current_user.id if current_user else None

    remaining_stock = (
        db.scalar(
            select(func.count(ShopCoupon.id)).where(
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.is_used.is_(False),
                ShopCoupon.expires_at > now,
            )
        )
        or 0
    )
    enabled = _get_setting_bool(db, "coupon_drop_enabled", default=True)
    probability = _drop_probability(db, remaining_stock) if enabled and remaining_stock > 0 else 0
    eligible = probability > 0 and secrets.randbelow(10_000) < probability * 100

    log = UserActionLog(
        user_id=user_id,
        action_type="coupon_drop_trigger",
        action_name="前台优惠券彩蛋触发",
        target_id="lucky_coupon_drop",
        page=payload.page or "",
        ip_address=client_ip,
        user_agent=ua,
        extra_data={**(payload.extra_data or {}), "eligible": eligible, "probability": probability},
        created_at=now,
    )
    db.add(log)

    # UserActionLog is the canonical, concurrency-safe trigger counter. The
    # admin stats endpoint counts these rows and only reads the legacy setting
    # as a migration floor.
    db.commit()
    return CouponDropQualificationResponse(
        success=True,
        eligible=eligible,
        claim_token=_encode_drop_claim_token(issued_at=now) if eligible else "",
    )


@router.post("/heartbeat", response_model=UserHeartbeatResponse)
def user_heartbeat(
    request: Request,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> UserHeartbeatResponse:
    now = datetime.now(timezone.utc)
    token = get_token_from_request(request)
    session = get_session_by_token(db, token) if token else None

    # Settle online seconds from the session's own activity baseline so that
    # clicks and logout cannot double- or under-count the same interval.
    settle_session_activity(db, current_user, session, now=now)

    db.commit()
    return UserHeartbeatResponse(
        status="ok",
        online_seconds=current_user.total_duration_seconds or 0,
        is_online=True,
    )


@router.post("/track-click")
def user_track_click(
    payload: UserTrackClickRequest,
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .public import _client_address, _enforce_client_rate_limit

    _enforce_client_rate_limit(
        request,
        db,
        namespace="user-click-telemetry",
        max_requests=120,
        window_seconds=60,
        detail="too many click events",
    )
    client_ip = _client_address(request)
    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)

    user_id = current_user.id if current_user else None
    session = None
    if current_user:
        token = get_token_from_request(request)
        session = get_session_by_token(db, token) if token else None
        # Settle online seconds from the same baseline the heartbeat uses, then
        # atomically bump the click counter (read-modify-write loses updates).
        settle_session_activity(db, current_user, session, now=now)
        db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(button_click_count=User.button_click_count + 1)
        )

    log = UserActionLog(
        user_id=user_id,
        action_type="button_click",
        action_name=payload.button_name,
        target_id=payload.button_id or "",
        page=payload.page or "",
        ip_address=client_ip,
        user_agent=ua,
        extra_data=payload.extra_data or {},
        created_at=now,
    )
    db.add(log)
    db.commit()
    if current_user:
        db.refresh(current_user)
    return {
        "status": "ok",
        "recorded": True,
        "click_count": current_user.button_click_count if current_user else 0,
    }

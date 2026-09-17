from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CatalogSnapshot, Offer, Product, SystemSetting, User, UserBotBinding, UserProductSubscription
from ..schemas import (
    BotCommandRequest,
    BotCommandResponse,
    QQBotBindingStartResponse,
    UserBotBindingRead,
    UserBotBindingUpdate,
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

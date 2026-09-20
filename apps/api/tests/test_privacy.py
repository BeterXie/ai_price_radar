from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import Base
from app.models import AuthCode, NotificationOutbox, OfferClick, Shop, User, UserActionLog, UserSession
from app.services.privacy import cleanup_privacy_data


def test_cleanup_privacy_data_bounds_transient_and_click_records():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=31)
    recent = now - timedelta(hours=1)
    with Session(engine) as db:
        shop = Shop(
            token="privacy-shop",
            name="Privacy Shop",
            source_url="https://privacy.example.com",
            platform="woocommerce",
            status="normal",
        )
        db.add(shop)
        db.flush()
        user = User(email="privacy@example.com")
        db.add(user)
        db.flush()
        db.add_all([
            AuthCode(
                email="expired@example.com",
                code="123456",
                expires_at=now - timedelta(minutes=1),
                created_at=recent,
            ),
            AuthCode(
                email="active@example.com",
                code="654321",
                expires_at=now + timedelta(minutes=10),
                created_at=recent,
            ),
            NotificationOutbox(
                event_type="auth_login_code",
                recipient="old-code@example.com",
                subject="code",
                text_body="verification code 123456",
                dedupe_key="privacy-old-auth-code",
                created_at=now - timedelta(days=2),
            ),
            NotificationOutbox(
                event_type="shop_request.submitted.applicant",
                recipient="old@example.com",
                subject="old",
                text_body="old",
                dedupe_key="privacy-old-notification",
                created_at=old,
            ),
            NotificationOutbox(
                event_type="test.recent",
                recipient="recent@example.com",
                subject="recent",
                text_body="recent",
                dedupe_key="privacy-recent-notification",
                created_at=recent,
            ),
            OfferClick(shop_id=shop.id, ip_hash="old", user_agent="old", created_at=old),
            OfferClick(shop_id=shop.id, ip_hash="recent", user_agent="recent", created_at=recent),
            UserActionLog(action_name="old", ip_address="203.0.113.1", user_agent="old", created_at=old),
            UserActionLog(action_name="recent", ip_address="203.0.113.2", user_agent="recent", created_at=recent),
            UserSession(
                token="old-active-session",
                user_id=user.id,
                ip_address="203.0.113.9",
                user_agent="old browser",
                created_at=old,
                last_active_at=recent,
                expires_at=now + timedelta(days=30),
            ),
        ])
        db.commit()

        result = cleanup_privacy_data(
            db,
            Settings(_env_file=None, privacy_log_retention_days=30),
        )

        assert result["expired_auth_codes"] == 1
        assert result["notification_outbox"] == 2
        assert result["offer_clicks"] == 1
        assert result["action_logs"] == 1
        assert result["anonymized_sessions"] == 1
        assert len(list(db.scalars(select(AuthCode)))) == 1
        assert [row.dedupe_key for row in db.scalars(select(NotificationOutbox))] == [
            "privacy-recent-notification"
        ]
        assert [row.ip_hash for row in db.scalars(select(OfferClick))] == ["recent"]
        assert [row.action_name for row in db.scalars(select(UserActionLog))] == ["recent"]
        active_session = db.get(UserSession, "old-active-session")
        assert active_session is not None
        assert active_session.ip_address == ""
        assert active_session.user_agent == ""

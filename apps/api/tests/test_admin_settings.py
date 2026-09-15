from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.routers.admin import get_admin_settings, update_admin_settings
from app.routers.public import meta
from app.schemas import AdminSettingsUpdate


def test_admin_settings_advertise_toggle():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # 1. Default should be False
        default_settings = get_admin_settings(db=db)
        assert default_settings.advertise_enabled is False

        public_meta = meta(db=db)
        assert public_meta.advertise_enabled is False

        # 2. Toggle to True
        updated = update_admin_settings(payload=AdminSettingsUpdate(advertise_enabled=True), db=db)
        assert updated.advertise_enabled is True

        read_again = get_admin_settings(db=db)
        assert read_again.advertise_enabled is True

        public_meta_on = meta(db=db)
        assert public_meta_on.advertise_enabled is True

        # 3. Toggle back to False
        updated_off = update_admin_settings(payload=AdminSettingsUpdate(advertise_enabled=False), db=db)
        assert updated_off.advertise_enabled is False

        public_meta_off = meta(db=db)
        assert public_meta_off.advertise_enabled is False


def test_admin_settings_site_notice():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # 1. Default should be enabled with default text
        default_settings = get_admin_settings(db=db)
        assert default_settings.site_notice_enabled is True
        assert default_settings.site_notice_badge == "最新动态"
        assert "16688" in default_settings.site_notice_title

        public_meta = meta(db=db)
        assert public_meta.site_notice is not None
        assert public_meta.site_notice.enabled is True
        assert "16688" in public_meta.site_notice.title

        # 2. Update notice text and toggle
        update_admin_settings(
            payload=AdminSettingsUpdate(
                site_notice_enabled=False,
                site_notice_badge="紧急维护",
                site_notice_title="系统将在今日 24:00 维护",
                site_notice_content="请广大用户提前安排。",
                site_notice_link_text="详情",
                site_notice_link_url="/maintenance",
            ),
            db=db,
        )

        read_again = get_admin_settings(db=db)
        assert read_again.site_notice_enabled is False
        assert read_again.site_notice_badge == "紧急维护"
        assert read_again.site_notice_title == "系统将在今日 24:00 维护"
        assert read_again.site_notice_content == "请广大用户提前安排。"
        assert read_again.site_notice_link_text == "详情"
        assert read_again.site_notice_link_url == "/maintenance"

        public_meta_updated = meta(db=db)
        assert public_meta_updated.site_notice is not None
        assert public_meta_updated.site_notice.enabled is False
        assert public_meta_updated.site_notice.badge == "紧急维护"
        assert public_meta_updated.site_notice.title == "系统将在今日 24:00 维护"


def test_admin_settings_community_toggle():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # Default
        default_settings = get_admin_settings(db=db)
        assert default_settings.community_enabled is True
        assert default_settings.community_title == "加入 AI 比价交流群"
        assert default_settings.community_qq_group == "938741334"

        public_meta = meta(db=db)
        assert public_meta.community_notice is not None
        assert public_meta.community_notice.enabled is True
        assert public_meta.community_notice.qq_group == "938741334"

        # Update
        update_admin_settings(
            payload=AdminSettingsUpdate(
                community_enabled=False,
                community_title="官方微信群",
                community_desc="扫码进群",
                community_qq_group="123456",
                community_btn_text="立即加群",
            ),
            db=db,
        )

        read_again = get_admin_settings(db=db)
        assert read_again.community_enabled is False
        assert read_again.community_title == "官方微信群"
        assert read_again.community_qq_group == "123456"

        public_meta_updated = meta(db=db)
        assert public_meta_updated.community_notice is not None
        assert public_meta_updated.community_notice.enabled is False
        assert public_meta_updated.community_notice.title == "官方微信群"



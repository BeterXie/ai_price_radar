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

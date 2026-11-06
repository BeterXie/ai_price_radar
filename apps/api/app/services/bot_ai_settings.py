"""Admin-managed QQ price AI configuration, encrypted at rest and read per request."""
from __future__ import annotations

import json
import logging

from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import SystemSetting
from ..schemas import BotAISettings, BotAISettingsOut, BotAISettingsUpdate
from .credential_crypto import decrypt_secret, encrypt_secret, is_encrypted_secret

logger = logging.getLogger(__name__)
SETTING_KEY = "qq_price_ai"


class BotAIConfig(BotAISettings):
    api_key: SecretStr = SecretStr("")


class BotAIConfigurationError(RuntimeError):
    pass


def read_stored_config(db: Session) -> BotAIConfig:
    row = db.get(SystemSetting, SETTING_KEY)
    return BotAIConfig.model_validate_json(row.value) if row else BotAIConfig()


def public_config(config: BotAIConfig) -> BotAISettingsOut:
    return BotAISettingsOut(
        **config.model_dump(exclude={"api_key"}),
        api_key_configured=bool(config.api_key.get_secret_value()),
    )


def prepare_config(payload: BotAISettingsUpdate, stored: BotAIConfig) -> BotAIConfig:
    """Resolve a draft without saving it; a blank key preserves the stored key."""
    replacement = payload.api_key.get_secret_value().strip() if payload.api_key else ""
    if replacement and payload.clear_api_key:
        raise ValueError("不能同时填写新密钥和清除密钥")
    if replacement and (not replacement.isascii() or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in replacement)):
        raise ValueError("密钥格式无效，请检查是否包含空白字符")
    encrypted = stored.api_key.get_secret_value()
    if payload.base_url != stored.base_url and encrypted and not replacement and not payload.clear_api_key:
        raise ValueError("更换接口地址时，请同时填写该接口的密钥，或清除旧密钥")
    if payload.clear_api_key:
        api_key = ""
    elif replacement:
        api_key = replacement
    else:
        if encrypted and not is_encrypted_secret(encrypted):
            raise BotAIConfigurationError("已保存的密钥格式无效，请重新填写密钥")
        api_key = decrypt_secret(encrypted)
    config = BotAIConfig(**payload.model_dump(exclude={"api_key", "clear_api_key"}), api_key=SecretStr(api_key))
    if config.enabled and not (config.base_url and config.model and api_key):
        raise ValueError("启用 AI 前请填写接口地址、模型和密钥")
    return config


def save_config(db: Session, config: BotAIConfig) -> None:
    data = config.model_dump(exclude={"api_key"})
    data["api_key"] = encrypt_secret(config.api_key.get_secret_value())
    row = db.get(SystemSetting, SETTING_KEY)
    if row is None:
        row = SystemSetting(key=SETTING_KEY)
        db.add(row)
    row.value = json.dumps(data, ensure_ascii=False)
    db.commit()


def load_runtime_config() -> BotAIConfig:
    try:
        # Read the entire configuration atomically and close before any model I/O.
        # No cache: another API process sees the next committed admin update too.
        with SessionLocal() as db:
            config = read_stored_config(db)
        if config.enabled:
            encrypted = config.api_key.get_secret_value()
            if encrypted and not is_encrypted_secret(encrypted):
                raise ValueError("unencrypted AI credential")
            config.api_key = SecretStr(decrypt_secret(encrypted))
        return config
    except (SQLAlchemyError, ValueError, RuntimeError) as exc:
        logger.warning("QQ AI configuration unavailable: %s", type(exc).__name__)
        raise BotAIConfigurationError("AI 配置暂时无法读取") from None

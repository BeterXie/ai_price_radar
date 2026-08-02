import ipaddress
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
PLACEHOLDERS = {
    "change-me-now",
    "replace-with-a-long-random-string",
    "replace-with-a-separate-intake-worker-key",
    "admin@example.invalid",
    "re_xxxxxxxxx",
    "onboarding@resend.dev",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load_env(path: Path) -> Dict[str, str]:
    values = {}  # type: Dict[str, str]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_production_env(env: Dict[str, str]) -> List[str]:
    errors = []  # type: List[str]
    password = env.get("POSTGRES_PASSWORD", "")
    admin_key = env.get("ADMIN_API_KEY", "")
    intake_worker_key = env.get("INTAKE_WORKER_KEY", "")
    intake_admin_emails = env.get("SHOP_INTAKE_ADMIN_EMAILS", "")
    resend_api_key = env.get("RESEND_API_KEY", "").strip()
    resend_from = env.get("RESEND_FROM", "").strip()
    smtp_host = env.get("SMTP_HOST", "").strip()
    smtp_from = env.get("SMTP_FROM", "").strip()
    database_url = env.get("DATABASE_URL", "")

    if not password or password in PLACEHOLDERS or len(password) < 16:
        errors.append("POSTGRES_PASSWORD must be changed and contain at least 16 characters")
    if not admin_key or admin_key in PLACEHOLDERS or len(admin_key.encode()) < 32:
        errors.append("ADMIN_API_KEY must contain at least 32 bytes")
    if not intake_worker_key or intake_worker_key in PLACEHOLDERS or len(intake_worker_key.encode()) < 32:
        errors.append("INTAKE_WORKER_KEY must contain at least 32 bytes")
    if intake_worker_key and intake_worker_key == admin_key:
        errors.append("INTAKE_WORKER_KEY must be different from ADMIN_API_KEY")
    admin_emails = [value.strip() for value in intake_admin_emails.split(",") if value.strip()]
    if (
        not admin_emails
        or any(value in PLACEHOLDERS for value in admin_emails)
        or any(EMAIL_RE.fullmatch(value) is None for value in admin_emails)
    ):
        errors.append("SHOP_INTAKE_ADMIN_EMAILS must contain a real administrator address")
    resend_requested = bool(resend_api_key or resend_from)
    smtp_requested = bool(smtp_host or smtp_from)
    if resend_requested:
        if not resend_api_key or resend_api_key in PLACEHOLDERS or not resend_api_key.startswith("re_"):
            errors.append("RESEND_API_KEY must contain a real Resend API key")
        if not resend_from or resend_from in PLACEHOLDERS or EMAIL_RE.fullmatch(resend_from) is None:
            errors.append("RESEND_FROM must use a verified sender address")
    elif smtp_requested:
        if not smtp_host or smtp_host in PLACEHOLDERS or any(character.isspace() for character in smtp_host):
            errors.append("SMTP_HOST must be configured for production mail delivery")
        if not smtp_from or smtp_from in PLACEHOLDERS or EMAIL_RE.fullmatch(smtp_from) is None:
            errors.append("SMTP_FROM must be a real sender address")
    else:
        errors.append("Configure RESEND_API_KEY/RESEND_FROM or SMTP_HOST/SMTP_FROM for production mail delivery")
    if not database_url or any(value in database_url for value in PLACEHOLDERS):
        errors.append("DATABASE_URL must contain the production database credentials")
    if env.get("SEED_DEMO_DATA", "").casefold() not in {"false", "0", "no"}:
        errors.append("SEED_DEMO_DATA must be false")
    for key in ("PUBLIC_SITE_URL", "WEB_ORIGIN", "NEXT_PUBLIC_API_BASE_URL", "SITE_ADDRESS"):
        if not is_https_url(env.get(key, "")):
            errors.append(f"{key} must be an absolute https URL")
    proxy_cidrs = env.get("TRUSTED_PROXY_CIDRS", "").strip()
    if not proxy_cidrs:
        errors.append("TRUSTED_PROXY_CIDRS must include the private proxy network")
    else:
        try:
            for value in proxy_cidrs.split(","):
                ipaddress.ip_network(value.strip())
        except ValueError:
            errors.append("TRUSTED_PROXY_CIDRS must be a comma-separated CIDR list")

    if env.get("NEXT_PUBLIC_SUPPORT_ENABLED", "").casefold() in {"true", "1", "yes"}:
        for key in ("NEXT_PUBLIC_SUPPORT_WECHAT_QR_URL", "NEXT_PUBLIC_SUPPORT_ALIPAY_QR_URL"):
            qr_url = env.get(key, "")
            hostname = urlparse(qr_url).hostname or ""
            if not is_https_url(qr_url) or hostname == "example.com" or hostname.endswith(".example.com"):
                errors.append(f"{key} must be an absolute https URL when author support is enabled")

    return errors


def main() -> int:
    if not ENV_FILE.is_file():
        print("production preflight failed: copy .env.example to .env and configure it")
        return 2

    errors = validate_production_env(load_env(ENV_FILE))
    if errors:
        print("production preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 2
    print("production preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

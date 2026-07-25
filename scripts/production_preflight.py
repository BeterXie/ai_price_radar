import ipaddress
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
PLACEHOLDERS = {
    "change-me-now",
    "replace-with-a-long-random-string",
}


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


def main() -> int:
    if not ENV_FILE.is_file():
        print("production preflight failed: copy .env.example to .env and configure it")
        return 2

    env = load_env(ENV_FILE)
    errors = []  # type: List[str]
    password = env.get("POSTGRES_PASSWORD", "")
    admin_key = env.get("ADMIN_API_KEY", "")
    database_url = env.get("DATABASE_URL", "")

    if not password or password in PLACEHOLDERS or len(password) < 16:
        errors.append("POSTGRES_PASSWORD must be changed and contain at least 16 characters")
    if not admin_key or admin_key in PLACEHOLDERS or len(admin_key.encode()) < 32:
        errors.append("ADMIN_API_KEY must contain at least 32 bytes")
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

    if errors:
        print("production preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 2
    print("production preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

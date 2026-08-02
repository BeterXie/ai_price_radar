from scripts.production_preflight import validate_production_env


def _valid_env() -> dict[str, str]:
    return {
        "POSTGRES_PASSWORD": "a" * 24,
        "ADMIN_API_KEY": "b" * 40,
        "INTAKE_WORKER_KEY": "c" * 40,
        "SHOP_INTAKE_ADMIN_EMAILS": "ops@example.com",
        "RESEND_API_KEY": "re_" + "d" * 32,
        "RESEND_FROM": "notice@example.com",
        "DATABASE_URL": "postgresql+psycopg://price_radar:password@db:5432/price_radar",
        "SEED_DEMO_DATA": "false",
        "PUBLIC_SITE_URL": "https://ai.example.com",
        "WEB_ORIGIN": "https://ai.example.com",
        "NEXT_PUBLIC_API_BASE_URL": "https://ai.example.com",
        "SITE_ADDRESS": "https://ai.example.com",
        "TRUSTED_PROXY_CIDRS": "172.16.0.0/12",
    }


def test_production_preflight_requires_working_mail_configuration():
    env = _valid_env()
    env["RESEND_API_KEY"] = ""
    env["RESEND_FROM"] = ""
    errors = validate_production_env(env)
    assert any("production mail delivery" in error for error in errors)


def test_production_preflight_accepts_real_mail_configuration():
    assert validate_production_env(_valid_env()) == []


def test_production_preflight_rejects_resend_placeholders():
    env = _valid_env()
    env["RESEND_API_KEY"] = "re_xxxxxxxxx"
    env["RESEND_FROM"] = "onboarding@resend.dev"
    errors = validate_production_env(env)
    assert any("RESEND_API_KEY" in error for error in errors)
    assert any("RESEND_FROM" in error for error in errors)


def test_production_preflight_accepts_smtp_fallback():
    env = _valid_env()
    env["RESEND_API_KEY"] = ""
    env["RESEND_FROM"] = ""
    env["SMTP_HOST"] = "smtp.example.com"
    env["SMTP_FROM"] = "no-reply@example.com"
    assert validate_production_env(env) == []

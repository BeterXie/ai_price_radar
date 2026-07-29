from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..models import Shop


@dataclass(frozen=True, slots=True)
class SourceHealth:
    score: int
    label: str
    reasons: tuple[str, ...]


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def source_health(shop: Shop, *, now: datetime | None = None) -> SourceHealth:
    """Describe scan health using only observable crawler facts.

    This is deliberately not a merchant reputation or fraud score.
    """
    current = now or datetime.now(timezone.utc)
    last_success = _aware(shop.last_success_at)
    reasons: list[str] = []
    score = 100

    if last_success is None:
        score -= 45
        reasons.append("尚无成功扫描时间")
    else:
        age = current - last_success
        if age > timedelta(days=7):
            score -= 45
            reasons.append("超过 7 天未成功扫描")
        elif age > timedelta(days=3):
            score -= 30
            reasons.append("超过 3 天未成功扫描")
        elif age > timedelta(hours=24):
            score -= 15
            reasons.append("超过 24 小时未成功扫描")
        else:
            reasons.append("最近 24 小时内扫描成功")

    failures = max(0, int(shop.consecutive_failures or 0))
    if failures:
        score -= min(35, failures * 7)
        reasons.append(f"连续扫描失败 {failures} 次")
    else:
        reasons.append("当前无连续扫描失败")

    status = (shop.status or "unknown").lower()
    if status in {"blocked", "challenge_required", "rate_limited"}:
        score -= 25
        reasons.append(f"最近扫描状态：{status}")
    elif status in {"network_error", "parse_error", "api_changed", "failed"}:
        score -= 15
        reasons.append(f"最近扫描状态：{status}")
    elif status in {"matched", "success", "ok"}:
        reasons.append("最近扫描状态正常")

    score = max(0, min(100, score))
    if score >= 85:
        label = "稳定"
    elif score >= 65:
        label = "一般"
    else:
        label = "需复核"
    return SourceHealth(score=score, label=label, reasons=tuple(reasons))

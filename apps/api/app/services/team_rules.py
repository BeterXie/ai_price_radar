"""Shared public Team eligibility and deadline parsing."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from .account_plans import account_plan

TEAM_PRICE_LIMIT = Decimal("20.00")
TEAM_HEAD_PRICE_LIMIT = Decimal("30.00")
BEIJING = timezone(timedelta(hours=8))
_NUMBER = r"(?:\d{1,2}|[零〇一二两三四五六七八九十]{1,3})"
_CLOCK = re.compile(
    rf"(?<![\d.])(?P<period>凌晨|清晨|早上|上午|中午|下午|傍晚|晚上|夜里|明早|明晚|今晚|今早|昨晚|昨早)?\s*"
    rf"(?P<hour>{_NUMBER})\s*(?:[:.]\s*(?P<minute>\d{{1,2}})(?!\d)|"
    rf"[点时]\s*(?:(?P<half>半)|(?P<chinese_minute>{_NUMBER})\s*分?)?)"
)
_DATE = re.compile(r"(?<![\d.])(?:(?P<year>20\d{2}|[零〇一二三四五六七八九]{4})[年/.-])?"
                   r"(?P<month>0?[1-9]|1[0-2]|[一二三四五六七八九十]{1,2})[月/.-]"
                   r"(?P<day>0?[1-9]|[12]\d|3[01]|[一二三四五六七八九十]{1,3})(?:日|号)?(?!\d)")
_DAY = re.compile(rf"(?P<day>{_NUMBER})[日号]")
_END_AFTER = re.compile(r"^\s*(?:左右|之前|前后|前|后|开始)?\s*(?:开踢|踢|下车|到期|结束|截止|回收|失效|停用)")


def _title_text(title: str) -> str:
    return unicodedata.normalize("NFKC", title).casefold().replace("×", "x").replace("✖", "x").replace("\ufe0f", "")


def is_head_car_title(title: str) -> bool:
    text = _title_text(title)
    if re.search(r"(?:二|2)\s*车|(?:非|不是|并非|不是真|不算)\s*(?:真)?(?:头车|首车|第?[一1]\s*车)", text):
        return False
    return bool(re.search(r"头车|首车|(?<![一二三四五六七八九十百零\d])(?:第?一|第?1)\s*车", text))


def _number(value: str) -> int:
    if value.isascii() and value.isdigit():
        return int(value)
    digits = {char: value for value, char in enumerate("零一二三四五六七八九")}
    digits.update({"〇": 0, "两": 2})
    if "十" in value:
        tens, _, ones = value.partition("十")
        return (digits[tens] if tens else 1) * 10 + (digits[ones] if ones else 0)
    return int("".join(str(digits[char]) for char in value))


def _title_date(prefix: str, anchor: date) -> tuple[date | None, bool]:
    candidates = []
    full_dates = [match for match in _DATE.finditer(prefix)
                  if not re.match(r"分钟|小时|天|刀|元", prefix[match.end():])]
    if re.search(r"(?:上|下|本)周|(?:上|下|本)星期", prefix):
        return None, True
    if not full_dates and re.search(r"去年|明年|上个?月|下个?月|本月|这个月|星期|(?:本|上|下)?周[一二三四五六日天]", prefix):
        return None, True
    if re.search(r"去年|明年|上个?月|下个?月|本月|这个月", prefix) and not any(m['year'] for m in full_dates):
        return None, True
    for match in full_dates:
        month, day = _number(match['month']), _number(match['day'])
        year = _number(match['year']) if match['year'] else anchor.year
        if not match['year']:
            if month - anchor.month > 6:
                year -= 1
            elif anchor.month - month > 6:
                year += 1
        try:
            resolved = date(year, month, day)
        except ValueError:
            resolved = None
        candidates.append((match.start(), resolved))
    for match in _DAY.finditer(prefix):
        if any(full.start() <= match.start() < full.end() for full in full_dates):
            continue
        valid = []
        for delta in (-1, 0, 1):
            month_index = anchor.year * 12 + anchor.month - 1 + delta
            try:
                valid.append(date(month_index // 12, month_index % 12 + 1, _number(match['day'])))
            except (ValueError, KeyError):
                pass
        candidates.append((match.start(), min(valid, key=lambda value: abs((value - anchor).days)) if valid else None))
    for match in re.finditer(r"大后天|后天|大前天|前天|昨天|昨日|昨晚|昨早|明天|明日|明早|明晚|今天|今日|今晚|今早|当日", prefix):
        days = {'大后天': 3, '后天': 2, '大前天': -3, '前天': -2}.get(match[0],
            1 if match[0].startswith('明') else -1 if match[0].startswith('昨') else 0)
        candidates.append((match.start(), anchor + timedelta(days=days)))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1], True
    return anchor, False


def team_title_ends_at(title: str, *, observed_at: datetime) -> datetime | None:
    """Resolve the title against its observation date, never roll old quotes forward daily."""
    text = _title_text(title)
    anchor = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at
    anchor = anchor.astimezone(BEIJING)
    clocks = list(_CLOCK.finditer(text))
    date_spans = []
    for calendar in _DATE.finditer(text):
        explicit_date = calendar['year'] or any(marker in calendar[0] for marker in ('月', '日', '号'))
        followed_by_clock = any(other.start() >= calendar.end() and not text[calendar.end():other.start()].strip(' \t\r\n,;|/[]():【】')
                                for other in clocks)
        ambiguous_dotted_date = '.' in calendar[0] and (re.search(
            r"(?:截止|到期|结束|有效至|下车时间)\s*$", text[max(0, calendar.start() - 12):calendar.start()])
            or re.match(r"\s*(?:到期|截止|结束)", text[calendar.end():]))
        if explicit_date or followed_by_clock or ambiguous_dotted_date:
            date_spans.append(calendar.span())
    clocks = [match for match in clocks if not any(start <= match.start('hour') < end for start, end in date_spans)]
    clocks = [match for match in clocks if not re.match(r"\s*(?:补货|上架|售卖|开售)", text[match.end():])]
    explicit = [match for match in clocks if _END_AFTER.search(text[match.end():]) or re.search(
        r"(?:截止|到期|结束|有效至|下车时间)[^|\n,，;；。]{0,24}$", text[max(0, match.start() - 35):match.start()],
    )]
    if explicit:
        clocks = explicit
    elif len(clocks) != 1 or re.search(r"开车|发车|开通|开始|上线|出发|补货|上架|售卖|开售", text):
        return None
    elif '.' in clocks[0][0] or re.match(r"\s*(?:元|刀|倍|x|美元|人民币)", text[clocks[0].end():]):
        return None  # A bare decimal can be a price or date, rather than a deadline.
    endings = set()
    for match in clocks:
        if re.match(r"\s*(?:[ap]\.?m\.?|utc|gmt|pst|est)(?![a-z])", text[match.end():]):
            return None
        try:
            hour = _number(match['hour'])
            minute = 30 if match['half'] else _number(match['minute'] or match['chinese_minute'] or '0')
        except (ValueError, KeyError):
            return None
        period = match['period'] or ''
        if hour > 24 or minute > 59 or (hour == 24 and minute):
            return None
        if period in ('下午', '傍晚', '晚上', '明晚', '今晚', '昨晚', '夜里') and 1 <= hour < 12:
            hour += 12
        if period == '中午' and 1 <= hour <= 4:
            hour += 12
        if period in ('凌晨', '清晨') and hour == 12:
            hour = 0
        if period in ('晚上', '明晚', '今晚', '昨晚', '夜里') and hour == 12:
            hour = 24
        try:
            day, dated = _title_date(text[max(0, match.start() - 60):match.start('hour')], anchor.date())
        except (KeyError, ValueError, OverflowError):
            return None
        if day is None:
            return None
        if not dated and anchor.hour >= 12 and hour < 12 and (
            period in ('凌晨', '清晨', '早上', '上午') or '过夜' in text
        ):
            day += timedelta(days=1)
        endings.add(datetime(day.year, day.month, day.day, hour % 24, minute, tzinfo=BEIJING) + timedelta(days=hour // 24))
    return next(iter(endings)) if len(endings) == 1 else None


def is_team_account_title(title: str) -> bool:
    text = _title_text(title)
    text = re.sub(r"(?:附带|附赠|附|赠送)(?:使用|上车)?教程", "", text)
    # A free/base account advertised as usable for opening Team is not a Team
    # subscription. Other vendors also sell products called "Team 5x".
    if account_plan("chatgpt", text, "") == "chatgpt-account" or re.search(
        r"claude|anthropic|cursor|gemini|(?<![a-z])free(?![a-z])|未开通|待开通|可开通|基础账号|无订阅|教程",
        text,
    ):
        return False
    has_team = bool(
        re.search(r"(?<![a-z])team(?![a-z])|(?<![a-z0-9])(?:5|10)\s*x\s*team(?![a-z])", text)
    )
    has_team_multiplier = bool(re.search(r"(?<![\d.])(?:5|10)\s*(?:倍|x(?=team|[^a-z0-9]|$))", text))
    if has_team and has_team_multiplier:
        return True
    return bool(
        re.search(r"(?<![a-z])team(?![a-z])", text)
        and (re.search(r"(?<![一二三四五六七八九十百零\d])(?:二|2)\s*车", text) or is_head_car_title(text))
    )

"""Calendar facts derived solely from a sample's explicit current-time context."""

from datetime import datetime, timedelta
from typing import Any


_WEEKDAYS_VI = (
    "thứ hai",
    "thứ ba",
    "thứ tư",
    "thứ năm",
    "thứ sáu",
    "thứ bảy",
    "chủ nhật",
)


def build_time_context(context: dict[str, Any]) -> dict[str, Any]:
    """Build bounded date/weekday facts; return empty when the anchor is unusable."""
    raw = context.get("current_time")
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        anchor = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return {}
    if anchor.utcoffset() is None:
        return {}

    today = anchor.date()
    monday = today - timedelta(days=today.weekday())
    calendar = []
    for offset in range(14):
        date = monday + timedelta(days=offset)
        calendar.append({"date": date.isoformat(), "weekday_vi": _WEEKDAYS_VI[date.weekday()]})
    return {
        "anchor": raw,
        "today": today.isoformat(),
        "tomorrow": (today + timedelta(days=1)).isoformat(),
        "day_after_tomorrow": (today + timedelta(days=2)).isoformat(),
        "calendar": calendar,
    }

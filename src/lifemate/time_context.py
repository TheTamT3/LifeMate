"""Calendar facts derived solely from a sample's explicit current-time context."""

from datetime import datetime, timedelta
from typing import Any


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
    calendar = [
        {"date": (monday + timedelta(days=offset)).isoformat(), "iso_weekday": (monday + timedelta(days=offset)).isoweekday()}
        for offset in range(14)
    ]
    return {
        "anchor": raw,
        "today": today.isoformat(),
        "tomorrow": (today + timedelta(days=1)).isoformat(),
        "day_after_tomorrow": (today + timedelta(days=2)).isoformat(),
        "calendar": calendar,
    }

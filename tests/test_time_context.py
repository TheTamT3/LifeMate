from lifemate.time_context import build_time_context


def test_calendar_uses_sample_time_and_current_and_next_week():
    result = build_time_context({"current_time": "2026-11-03T23:30:00+07:00"})
    assert result["anchor"] == "2026-11-03T23:30:00+07:00"
    assert result["today"] == "2026-11-03"
    assert result["tomorrow"] == "2026-11-04"
    assert result["day_after_tomorrow"] == "2026-11-05"
    assert len(result["calendar"]) == 14
    assert result["calendar"][0] == {"date": "2026-11-02", "iso_weekday": 1}
    assert result["calendar"][-1] == {"date": "2026-11-15", "iso_weekday": 7}


def test_calendar_crosses_year():
    result = build_time_context({"current_time": "2026-12-31T23:30:00+07:00"})
    assert result["tomorrow"] == "2027-01-01"


def test_invalid_or_naive_anchor_has_no_fallback():
    assert build_time_context({}) == {}
    assert build_time_context({"current_time": "bad"}) == {}
    assert build_time_context({"current_time": "2026-11-03T23:30:00"}) == {}


def test_offset_date_is_not_host_utc_date():
    result = build_time_context({"current_time": "2026-11-03T00:30:00+14:00"})
    assert result["today"] == "2026-11-03"


def test_offset_is_authoritative_while_timezone_label_remains_unmodified():
    context = {"current_time": "2026-11-03T23:30:00+07:00", "timezone": "America/New_York"}
    assert build_time_context(context)["today"] == "2026-11-03"
    assert context["timezone"] == "America/New_York"

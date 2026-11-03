import json
import sys
from pathlib import Path


DATA = Path("train+public_test/train+public_test/train")


def test_runtime_ignores_order_history_limit_and_preserves_other_contracts():
    sys.path.insert(0, str(DATA))
    from zaic_tools import Session

    catalog = json.loads((DATA / "train_tools_catalog.json").read_text(encoding="utf-8"))
    entry = {
        "_meta": {
            "tools": [
                "food_delivery.order_history", "bill_payment.schedule_autopay",
                "ride_hailing.get_quotes", "calendar.update_event",
            ],
            "current_time": "2026-11-03T12:00:00+07:00",
        },
        "food_delivery": {"orders": [{"id": f"order_{i}"} for i in range(3)]},
        "bill_payment": {"bills": [{"id": "bill_1", "paid": False}], "autopays": []},
        "ride_hailing": {"quotes": [{"id": "quote_1", "pickup": "A", "dropoff": "B", "vehicle": "car4"}], "rides": []},
        "calendar": {"events": [{"id": "evt_1", "status": "cancelled", "title": "Canceled"}]},
    }
    session = Session("contract_fixture", entry, catalog)
    limited = session.call("food_delivery.order_history", {"limit": 1})
    all_orders = session.call("food_delivery.order_history", {})
    assert limited == all_orders
    assert len(limited["orders"]) == 3

    session.call("bill_payment.schedule_autopay", {"type": "electricity", "enabled": True})
    assert session.states["bill_payment"]["bills"] == [{"id": "bill_1", "paid": False}]
    assert session.call("ride_hailing.get_quotes", {"pickup": "A", "dropoff": "B", "vehicle": "car4"})["quotes"] == entry["ride_hailing"]["quotes"]
    assert session.states["ride_hailing"]["rides"] == []
    session.call("calendar.update_event", {"event_id": "evt_1", "title": "Renamed"})
    assert session.states["calendar"]["events"][0]["status"] == "cancelled"


def test_query_contract_preserves_omitted_and_literal_none_and_since_lower_bound():
    sys.path.insert(0, str(DATA))
    from zaic_tools import Session

    catalog = json.loads((DATA / "train_tools_catalog.json").read_text(encoding="utf-8"))
    entry = {
        "_meta": {"tools": ["package_tracking.track", "home_security.list_alerts"], "current_time": "2026-11-03T12:00:00+07:00"},
        "package_tracking": {"shipments": [{"id": "shipment_1", "tracking_id": "TRACK-1"}]},
        "home_security": {"alerts": [
            {"id": "old", "time": "2026-11-03T11:00:00+07:00"},
            {"id": "at", "time": "2026-11-03T12:00:00+07:00"},
            {"id": "new", "time": "2026-11-03T13:00:00+07:00"},
        ]},
    }
    session = Session("query_fixture", entry, catalog)
    assert session.call("package_tracking.track", {})["shipments"] == entry["package_tracking"]["shipments"]
    assert session.call("package_tracking.track", {"tracking_id": "None"})["shipments"] == []
    assert [a["id"] for a in session.call("home_security.list_alerts", {"since": "2026-11-03T12:00:00+07:00"})["alerts"]] == ["at", "new"]


def test_optional_climate_and_priority_use_runtime_defaults_only_when_omitted():
    sys.path.insert(0, str(DATA))
    from zaic_tools import Session
    from lifemate.pydantic_agent import validate_catalog_arguments

    catalog = json.loads((DATA / "train_tools_catalog.json").read_text(encoding="utf-8"))
    entry = {
        "_meta": {"tools": ["smart_home.climate_set", "tasks.add"], "current_time": "2026-11-03T12:00:00+07:00"},
        "smart_home": {"devices": [{"id": "climate_1", "type": "climate", "state": {"temperature": 23, "mode": "cool"}}]},
        "tasks": {"tasks": []},
    }
    session = Session("optional_fixture", entry, catalog)
    omitted = {"device_id": "climate_1", "mode": "cool"}
    explicit = {"device_id": "climate_1", "mode": "cool", "temperature": 26}
    climate_tool = next(tool for app in catalog["apps"] for tool in app["tools"] if tool["name"] == "smart_home.climate_set")
    assert validate_catalog_arguments(climate_tool, explicit) == explicit
    session.call("smart_home.climate_set", omitted)
    assert session.states["smart_home"]["devices"][0]["state"]["temperature"] == 23
    session.call("smart_home.climate_set", explicit)
    assert session.states["smart_home"]["devices"][0]["state"]["temperature"] == 26

    session.call("tasks.add", {"title": "default priority"})
    session.call("tasks.add", {"title": "explicit priority", "priority": "high"})
    assert [task["priority"] for task in session.states["tasks"]["tasks"]] == ["normal", "high"]

import json
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "mechanism_cases.json"
REMAINING = {"R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "V01", "Q01", "C01", "X01", "X02"}


def test_manifest_covers_remaining_clusters():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert {case["cluster"] for case in cases} == REMAINING
    assert all(case["sample_id"] and case["bucket"] and case["finding"] and case["evidence"] for case in cases)
    assert all(case["scope"] in {"local_difference", "action_sequence", "unresolved"} for case in cases)


def test_overlap_is_not_whole_sample_success():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    overlap = [case for case in cases if case["sample_id"] == "train_1533"]
    # The current source crosswalk also assigns Q01; all memberships are retained.
    assert {"V01", "R03"}.issubset({case["cluster"] for case in overlap})
    assert next(case for case in overlap if case["cluster"] == "V01")["scope"] == "local_difference"
    assert all("whole_sample_correct" not in case for case in overlap)


def test_manifest_contains_all_v01_memberships_from_crosswalk():
    expected = set(json.loads((FIXTURE.parent / "v01_sample_ids.json").read_text(encoding="utf-8")))
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = {case["sample_id"] for case in cases if case["cluster"] == "V01"}
    assert actual == expected
    assert len(expected) == 83


def test_x01_and_x02_cases_keep_individual_evidence_status():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    x01 = {case["sample_id"] for case in cases if case["cluster"] == "X01"}
    x02 = {case["sample_id"] for case in cases if case["cluster"] == "X02"}
    assert len(x01) == 22
    assert {"train_1178", "train_1564", "train_1750"}.issubset(x02)
    x01_findings = {case["finding"] for case in cases if case["cluster"] == "X01"}
    assert len(x01_findings) >= 20
    assert all(len(case["evidence"]) > 20 for case in cases if case["cluster"] == "X01")
    by_id = {case["sample_id"]: case for case in cases if case["cluster"] == "X02"}
    assert "available=true" in by_id["train_1178"]["finding"]
    assert "số dư không đủ" in by_id["train_1564"]["finding"]
    assert "Ngoài P01" in by_id["train_1750"]["finding"]

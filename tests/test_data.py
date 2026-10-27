import json

from lifemate.data import allowed_tools, load_catalog, read_jsonl, split_paths


def test_jsonl_and_catalog_preserve_unicode_and_flatten(tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text('{"text":"Đà Nẵng"}\n', encoding="utf-8")
    assert read_jsonl(rows)[0]["text"] == "Đà Nẵng"
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps({"apps": [{"tools": [{"name": "x.y", "kind": "read"}]}]}, ensure_ascii=False), encoding="utf-8")
    assert load_catalog(catalog_path)["x.y"]["kind"] == "read"


def test_allowed_tools_deduplicates_and_skips_missing_names():
    sample = {"context": {"installed_apps": {"a": {"tools": ["x.y", "x.y", "missing"]}}}}
    catalog = {"x.y": {"name": "x.y", "kind": "read"}}
    assert allowed_tools(sample, catalog) == [catalog["x.y"]]


def test_empty_installed_apps_and_split_paths(tmp_path):
    sample = {"context": {"installed_apps": {}}}
    assert allowed_tools(sample, {}) == []
    assert allowed_tools(sample, {"sys.ask_missing_info": {"name": "sys.ask_missing_info"}})[0]["name"] == "sys.ask_missing_info"
    (tmp_path / "train").mkdir()
    data, catalog = split_paths(tmp_path, "train")
    assert data.name == "train.jsonl"
    assert catalog.name == "train_tools_catalog.json"

from lifemate.agent_schema import parse_calls


def test_parser_accepts_array_and_fenced_or_surrounding_prose():
    expected = [{"name": "weather.get_current", "arguments": {}}]
    for raw in [
        '[{"name":"weather.get_current","arguments":{}}]',
        '```json\n[{"name":"weather.get_current","arguments":{}}]\n```',
        'Here is the result: [{"name":"weather.get_current","arguments":{}}]',
    ]:
        assert [item.model_dump() for item in parse_calls(raw, {"weather.get_current"})] == expected


def test_parser_rejects_invalid_unknown_and_non_object_arguments():
    assert parse_calls("not json", {"x.y"}) == []
    assert parse_calls('[{"name":"x.y","arguments":[]}]', {"x.y"}) == []
    assert parse_calls('[{"name":"other.z","arguments":{}}]', {"x.y"}) == []


def test_parser_accepts_empty_array():
    assert parse_calls("[]", {"x.y"}) == []

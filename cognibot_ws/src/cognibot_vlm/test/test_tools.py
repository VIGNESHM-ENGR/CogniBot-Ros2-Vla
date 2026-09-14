import pytest
from cognibot_vlm.tools import TOOLS, ToolError, validate_arguments


def test_every_tool_has_a_flat_object_schema():
    for tool in TOOLS:
        params = tool["function"]["parameters"]
        assert params["type"] == "object" and params["additionalProperties"] is False
        for spec in params["properties"].values():
            assert spec["type"] in {"number", "string"}


def test_validate_converts_numbers_and_checks_enum():
    assert validate_arguments("fetch_object", {"x": 0.3, "y": 0, "z": 0.01}) == {
        "x": 0.3,
        "y": 0.0,
        "z": 0.01,
    }
    assert validate_arguments("set_gripper", {"state": "open"}) == {"state": "open"}
    with pytest.raises(ToolError, match="one of"):
        validate_arguments("set_gripper", {"state": "half"})


def test_validate_rejects_unknown_missing_extra_and_wrong_types():
    with pytest.raises(ToolError, match="unknown tool"):
        validate_arguments("teleport", {})
    with pytest.raises(ToolError, match="missing"):
        validate_arguments("place_object", {"x": 0.1, "y": 0.2})
    with pytest.raises(ToolError, match="unexpected"):
        validate_arguments("move_home", {"speed": 1})
    with pytest.raises(ToolError, match="must be a number"):
        validate_arguments("check_reachability", {"x": "0.1", "y": 0, "z": 0})

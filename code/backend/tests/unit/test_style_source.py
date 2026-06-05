import pytest

from app.services.style_service import validate_style_source


def test_builtin_style_is_valid():
    source = validate_style_source({"kind": "builtin", "builtin_style": "suspense"})
    assert source.kind == "builtin"


def test_text_and_file_are_mutually_exclusive():
    with pytest.raises(ValueError):
        validate_style_source(
            {
                "kind": "custom",
                "style_text": "更悬疑，对白短促",
                "reference_file_ids": ["file_1"],
            }
        )


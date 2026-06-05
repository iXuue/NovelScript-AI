from app.services.export_service import to_user_clean_json, to_yaml_preview


def test_clean_json_removes_internal_fields():
    internal = {
        "title": "雨夜归来",
        "characters": [],
        "scenes": [{"scene_id": "S001", "content_blocks": [{"content_block_id": "CB001", "text": "她回来了。"}]}],
    }
    clean = to_user_clean_json(internal)
    assert "content_block_id" not in str(clean)


def test_yaml_preview_matches_clean_json_shape():
    clean = {"title": "雨夜归来", "characters": [], "scenes": []}
    yaml_text = to_yaml_preview(clean)
    assert "title: 雨夜归来" in yaml_text


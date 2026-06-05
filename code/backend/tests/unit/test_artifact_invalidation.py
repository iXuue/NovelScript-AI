from app.services.artifact_service import invalidate_after_scene_plan_change, invalidate_after_style_change


def test_style_change_before_confirmation_invalidates_style_and_scene_plan():
    changed = invalidate_after_style_change(scene_plan_confirmed=False)
    assert "style_profile" in changed
    assert "scene_plan" in changed
    assert "script_json" in changed


def test_scene_plan_change_invalidates_script_and_exports():
    changed = invalidate_after_scene_plan_change()
    assert changed == ["script_json", "traceability_index", "yaml_preview", "exports"]


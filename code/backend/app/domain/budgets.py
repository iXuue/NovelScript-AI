DEFAULT_PROJECT_BUDGET = {
    "max_chapters": 5,
    "max_total_characters": 50000,
    "max_llm_calls": 120,
    "max_tool_calls": 200,
    "max_active_runs": 1,
}

DEFAULT_RUN_BUDGETS = {
    "initial_analysis_scene_plan": {"llm": 60, "tools": 100},
    "scene_plan_regeneration": {"llm": 12, "tools": 25},
    "script_generation": {"llm": 80, "tools": 120},
    "conversation_edit": {"llm": 6, "tools": 15},
    "validation_rerun": {"llm": 4, "tools": 10},
    "export": {"llm": 0, "tools": 10},
}


from app.services.run_service import add_run_step, consume_llm_call, create_run


def test_auto_repair_is_step_not_new_run():
    run = create_run(trigger_type="script_generation")
    validation_step = add_run_step(run, "validation")
    repair_step = add_run_step(run, "repair")

    assert validation_step.run_id == run.run_id
    assert repair_step.run_id == run.run_id


def test_run_budget_stops_when_limit_reached():
    run = create_run(trigger_type="conversation_edit", llm_limit=1)
    consume_llm_call(run, step_type="conversation_edit")
    result = consume_llm_call(run, step_type="validation")
    assert result.allowed is False
    assert result.reason == "llm_budget_exceeded"


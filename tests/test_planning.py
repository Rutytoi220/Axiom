"""Tests for deterministic execution-plan lifecycle behavior."""

import pytest

from axiom.planning import ExecutionPlan, PlanError, PlanStep, StepStatus, TaskPlanner


def test_dependency_steps_become_ready_after_completion():
    plan = ExecutionPlan(
        objective="Prepare a report",
        steps=[
            PlanStep("collect", "Collect the source data"),
            PlanStep("write", "Write the report", depends_on=("collect",)),
        ],
    )

    assert [step.id for step in plan.ready_steps()] == ["collect"]
    plan.start_step("collect")
    plan.complete_step("collect", {"records": 3})

    assert [step.id for step in plan.ready_steps()] == ["write"]


def test_confirmation_gates_execution_until_explicitly_confirmed():
    plan = ExecutionPlan(
        objective="Delete a temporary file",
        steps=[PlanStep("delete", "Delete temporary file", requires_confirmation=True)],
    )

    assert plan.ready_steps() == []
    assert [step.id for step in plan.ready_steps(confirmed=True)] == ["delete"]
    with pytest.raises(PlanError, match="not ready"):
        plan.start_step("delete")

    plan.start_step("delete", confirmed=True)
    assert plan.steps[0].status == StepStatus.RUNNING


@pytest.mark.parametrize(
    "steps, error",
    [
        ([PlanStep("a", "A"), PlanStep("a", "Duplicate")], "unique"),
        ([PlanStep("a", "A", depends_on=("missing",))], "unknown dependencies"),
        ([PlanStep("a", "A", depends_on=("b",)), PlanStep("b", "B", depends_on=("a",))], "cycle"),
    ],
)
def test_invalid_dependency_graphs_are_rejected(steps, error):
    with pytest.raises(PlanError, match=error):
        ExecutionPlan(objective="Invalid", steps=steps)


def test_plan_round_trip_preserves_execution_state():
    plan = ExecutionPlan(
        objective="Inspect then decide",
        steps=[PlanStep("inspect", "Inspect input", metadata={"source": "local"})],
    )
    plan.start_step("inspect")
    plan.fail_step("inspect", "Input was unavailable")

    restored = ExecutionPlan.from_dict(plan.to_dict())

    assert restored.id == plan.id
    assert restored.steps[0].status == StepStatus.FAILED
    assert restored.steps[0].error == "Input was unavailable"
    assert restored.is_complete is True
    assert restored.succeeded is False


def test_task_planner_creates_validated_plan():
    plan = TaskPlanner().create_plan(
        "Run diagnostics",
        [PlanStep("diagnose", "Gather diagnostic information")],
        metadata={"origin": "cli"},
    )

    assert plan.objective == "Run diagnostics"
    assert plan.metadata == {"origin": "cli"}

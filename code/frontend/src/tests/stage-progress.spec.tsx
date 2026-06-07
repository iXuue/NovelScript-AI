import { render, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { StageProgress } from "../components/StageProgress";
import type { AgentProgress } from "../types";

test("marks chapter summary as running for the backend chapter_summary step", () => {
  const progress: AgentProgress = {
    run_id: "run_001",
    status: "running",
    stage: "scene_plan",
    current_step: "chapter_summary",
    steps: [
      {
        run_step_id: "step_001",
        step_type: "chapter_summary",
        status: "running",
        summary: "Chapter summaries are running"
      }
    ],
    failure_message: null
  };

  const { container } = render(
    <StageProgress
      activeLabel={null}
      progress={progress}
      projectSteps={[]}
      hasNovelUpload={false}
      styleSelected={false}
      chaptersConfirmed={false}
    />
  );

  const runningChip = container.querySelector(".figma-stage-chip.running");
  expect(runningChip).not.toBeNull();
  expect(within(runningChip as HTMLElement).getByText("章节摘要")).toBeInTheDocument();
  expect(runningChip?.querySelector(".figma-stage-chip-dot.running")).not.toBeNull();
});

test("marks scene plan edit as done when scene plan is complete and no edit is running", () => {
  const { container } = render(
    <StageProgress
      activeLabel={null}
      progress={null}
      projectSteps={[
        {
          step_type: "scene_plan",
          status: "succeeded",
          summary: "Scene Plan completed"
        }
      ]}
      hasNovelUpload={false}
      styleSelected={false}
      chaptersConfirmed={false}
    />
  );

  const doneChips = Array.from(container.querySelectorAll(".figma-stage-chip.done"));
  const scenePlanEditChip = doneChips.find((chip) =>
    within(chip as HTMLElement).queryByText("场景规划修改")
  );
  expect(scenePlanEditChip).toBeDefined();
  expect(scenePlanEditChip?.querySelector(".figma-stage-chip-dot.done")).not.toBeNull();
});

test("marks scene plan edit as running for scene_plan_feedback runs", () => {
  const progress: AgentProgress = {
    run_id: "run_002",
    status: "running",
    stage: "scene_plan",
    trigger_type: "scene_plan_feedback",
    current_step: "scene_plan",
    steps: [
      {
        run_step_id: "step_002",
        step_type: "scene_plan",
        status: "running",
        summary: "Scene Plan regenerated from feedback"
      }
    ],
    failure_message: null
  };

  const { container } = render(
    <StageProgress
      activeLabel={null}
      progress={progress}
      projectSteps={[
        {
          step_type: "scene_plan",
          status: "succeeded",
          summary: "Scene Plan completed"
        }
      ]}
      hasNovelUpload={false}
      styleSelected={false}
      chaptersConfirmed={false}
    />
  );

  const runningChip = container.querySelector(".figma-stage-chip.running");
  expect(runningChip).not.toBeNull();
  expect(within(runningChip as HTMLElement).getByText("场景规划修改")).toBeInTheDocument();
  expect(runningChip?.querySelector(".figma-stage-chip-dot.running")).not.toBeNull();
});

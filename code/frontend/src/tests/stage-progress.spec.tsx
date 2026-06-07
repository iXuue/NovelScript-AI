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

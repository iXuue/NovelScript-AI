import { useState } from "react";
import type { AgentProgress as AgentProgressType } from "../types";
import type { ProjectProgressStep } from "../api/client";

const STAGES = [
  "上传文件",
  "风格确认",
  "段落确认",
  "章节摘要",
  "风格解析",
  "场景规划",
  "场景规划修改",
  "剧本生成",
  "剧本修改",
] as const;

const SCENE_PLAN_STAGE = "场景规划";
const SCENE_PLAN_EDIT_STAGE = "场景规划修改";

const STEP_TO_STAGE: Record<string, string> = {
  chapter_summary: "章节摘要",
  chapter_summaries: "章节摘要",
  style_profile: "风格解析",
  scene_plan: "场景规划",
  script_generation: "剧本生成",
  feedback_plan: "剧本修改",
};

type Props = {
  activeLabel: string | null;
  progress: AgentProgressType | null;
  projectSteps: ProjectProgressStep[];
  hasNovelUpload: boolean;
  styleSelected: boolean;
  chaptersConfirmed: boolean;
};

export function StageProgress({
  activeLabel,
  progress,
  projectSteps = [],
  hasNovelUpload,
  styleSelected,
  chaptersConfirmed,
}: Props) {
  const [open, setOpen] = useState(false);

  const stageStatus: Record<string, "running" | "done" | "pending"> = {};
  for (const stage of STAGES) stageStatus[stage] = "pending";

  // 用户操作驱动
  if (hasNovelUpload) stageStatus["上传文件"] = "done";
  if (styleSelected) stageStatus["风格确认"] = "done";
  if (chaptersConfirmed) stageStatus["段落确认"] = "done";

  // 持久化步骤：标记历史完成的阶段
  for (const step of projectSteps) {
    const stage = STEP_TO_STAGE[step.step_type];
    if (!stage) continue;
    if (step.status === "succeeded" && stageStatus[stage] !== "running") {
      stageStatus[stage] = "done";
      if (step.step_type === "scene_plan" && /feedback|regenerated/i.test(step.summary)) {
        stageStatus[SCENE_PLAN_EDIT_STAGE] = "done";
      }
    }
  }

  // 活跃 run 的步骤：标记正在运行的阶段
  const activeSteps = progress?.steps ?? [];
  const isScenePlanFeedbackRun = progress?.trigger_type === "scene_plan_feedback";
  for (const step of activeSteps) {
    const stage = STEP_TO_STAGE[step.step_type];
    if (!stage) continue;
    if (step.status === "running") {
      if (step.step_type === "scene_plan" && isScenePlanFeedbackRun) {
        stageStatus[SCENE_PLAN_EDIT_STAGE] = "running";
      } else {
        stageStatus[stage] = "running";
      }
    }
  }

  // 首次点击生成到首次轮询之间的间隙：用 activeLabel 立即反馈
  if (activeSteps.length === 0 && projectSteps.length === 0 && activeLabel) {
    const fallbackMap: Record<string, string> = {
      "正在生成场景计划": "场景规划",
      "正在逐场生成剧本": "剧本生成",
      "正在执行修改计划": "剧本修改",
      "正在修复场景规划": "场景规划",
      "正在修复剧本场景": "剧本生成",
    };
    const current = fallbackMap[activeLabel];
    if (current) {
      stageStatus[current] = "running";
    }
  }

  if (stageStatus[SCENE_PLAN_STAGE] === "done" && stageStatus[SCENE_PLAN_EDIT_STAGE] === "pending") {
    stageStatus[SCENE_PLAN_EDIT_STAGE] = "done";
  }

  const hasRunning = Object.values(stageStatus).some((s) => s === "running");

  return (
    <div className={`figma-stage-bottom ${open ? "open" : ""}`} aria-label="生成进度">
      <button
        className="figma-stage-handle"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "收起进度" : "展开进度"}
      >
        <span className="figma-stage-handle-bar" aria-hidden="true" />
      </button>

      <div className="figma-stage-panel">
        <span className="figma-stage-panel-title">
          {hasRunning ? "正在生成" : "进度"}
        </span>
        {STAGES.map((stage) => {
          const status = stageStatus[stage];
          return (
            <div className={`figma-stage-chip ${status}`} key={stage}>
              <span className={`figma-stage-chip-dot ${status}`} aria-hidden="true" />
              <span className="figma-stage-chip-label">{stage}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { useState } from "react";

import type { AgentProgress as AgentProgressType } from "../types";

type Props = {
  progress: AgentProgressType | null;
  activeLabel: string | null;
};

const defaultSteps = [
  "正在解析上传文件",
  "正在识别章节",
  "正在生成章节摘要",
  "正在生成原文证据索引",
  "正在生成 Story Bible",
  "正在生成 Style Profile",
  "正在生成 Scene Plan",
  "正在等待用户确认 Scene Plan",
  "正在逐场生成剧本",
  "正在运行校验与修复"
];

function LegacyAgentProgress({ progress, activeLabel }: Props) {
  const [open, setOpen] = useState(true);
  const steps = progress?.steps.map((step) => step.summary) ?? defaultSteps;

  return (
    <section className="agent-progress">
      <button className="collapse-button" type="button" onClick={() => setOpen((value) => !value)}>
        <span className={open ? "disclosure-icon open" : "disclosure-icon"} aria-hidden="true" />
        Agent 执行进度
        {activeLabel ? <span className="active-step">{activeLabel}</span> : null}
      </button>
      {open ? (
        <ol>
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

export function AgentProgress({ progress, activeLabel }: Props) {
  const [open, setOpen] = useState(false);
  const steps = progress?.steps.map((step) => step.summary) ?? defaultSteps;
  const completed = progress?.steps.filter((step) => step.status === "succeeded").length ?? 0;
  const total = progress?.steps.length ?? steps.length;

  return (
    <section className="figma-agent-progress">
      <button className="figma-progress-trigger" type="button" onClick={() => setOpen((value) => !value)}>
        <span className={open ? "figma-chevron open" : "figma-chevron"} aria-hidden="true" />
        <span>Agent 执行进度</span>
        {activeLabel ? <small>{activeLabel}</small> : <small>{completed}/{total}</small>}
      </button>
      {open ? (
        <ol className="figma-progress-steps">
          {steps.map((step, index) => (
            <li key={`${step}-${index}`}>
              <span className={index < completed ? "done" : index === completed ? "running" : ""} aria-hidden="true" />
              <span>{step}</span>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

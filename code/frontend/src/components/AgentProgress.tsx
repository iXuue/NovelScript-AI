import { useState } from "react";

import type { AgentProgress as AgentProgressType } from "../types";

type Props = {
  progress: AgentProgressType | null;
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

export function AgentProgress({ progress }: Props) {
  const [open, setOpen] = useState(true);
  const steps = progress?.steps.map((step) => step.summary) ?? defaultSteps;

  return (
    <section className="agent-progress">
      <button className="collapse-button" type="button" onClick={() => setOpen((value) => !value)}>
        <span aria-hidden="true">{open ? "v" : ">"}</span>
        Agent 执行进度
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

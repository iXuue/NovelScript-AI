const STAGES = ["章节摘要", "风格解析", "场景规划", "剧本生成", "剧本修改"] as const;

type StageName = (typeof STAGES)[number];

/** loadingLabel → 当前所在阶段 */
const LABEL_TO_STAGE: Record<string, StageName> = {
  "正在解析上传文件": "章节摘要",
  "正在确认章节": "章节摘要",
  "正在生成场景规划": "场景规划",
  "正在确认场景规划": "场景规划",
  "正在保存风格设计": "风格解析",
  "正在上传风格参考": "风格解析",
  "正在逐场生成剧本": "剧本生成",
  "正在生成修改计划": "剧本修改",
  "正在执行修改计划": "剧本修改",
  "正在修复场景规划": "场景规划",
  "正在修复剧本场景": "剧本生成",
};

type Props = {
  activeLabel: string | null;
};

export function StageProgress({ activeLabel }: Props) {
  const currentStage = activeLabel ? LABEL_TO_STAGE[activeLabel] ?? null : null;
  if (!currentStage) return null;

  const currentIndex = STAGES.indexOf(currentStage);

  return (
    <div className="figma-stage-progress" aria-label="生成进度">
      {STAGES.map((stage, index) => {
        const isCurrent = index === currentIndex;
        const isDone = index < currentIndex;
        const isPending = index > currentIndex;

        let dotClass = "figma-stage-dot";
        if (isCurrent) dotClass += " current";
        else if (isDone) dotClass += " done";
        else if (isPending) dotClass += " pending";

        let textClass = "figma-stage-label";
        if (isCurrent) textClass += " current";
        else if (isDone) textClass += " done";
        else if (isPending) textClass += " pending";

        return (
          <span className="figma-stage-item" key={stage}>
            <span className={dotClass} aria-hidden="true" />
            <span className={textClass}>{stage}</span>
            {index < STAGES.length - 1 ? <span className="figma-stage-sep" aria-hidden="true" /> : null}
          </span>
        );
      })}
    </div>
  );
}

import { useState } from "react";

import type { EvidenceLookupResult, ScenePlan, ScriptCurrentForUi } from "../types";
import { EvidenceModal } from "./EvidenceModal";
import { YamlPreview } from "./YamlPreview";

type Props = {
  projectId: string;
  viewMode: "conversation" | "scene-plan" | "script";
  scenePlan: ScenePlan | null;
  scriptForUi: ScriptCurrentForUi | null;
  yaml: string | null;
  statusText: string;
  failedStage?: string | null;
  scenePlanConfirmed: boolean;
  loading: boolean;
  fallbackEvidence: Record<string, EvidenceLookupResult>;
  onGenerateScenePlan: () => void;
  onConfirmScenePlan: () => void;
  onGenerateScript: () => void;
};

export function ResultPane({
  projectId,
  viewMode,
  scenePlan,
  scriptForUi,
  yaml,
  statusText,
  failedStage,
  scenePlanConfirmed,
  loading,
  fallbackEvidence,
  onGenerateScenePlan,
  onConfirmScenePlan,
  onGenerateScript
}: Props) {
  const [evidenceBlockId, setEvidenceBlockId] = useState<string | null>(null);

  return (
    <aside className="result-pane" aria-label="成果区">
      {failedStage ? (
        <section className="failure-state">
          <h2>本次生成未完成，请调整要求后重新发起</h2>
          <p>失败阶段：{failedStage}</p>
        </section>
      ) : null}

      {viewMode === "scene-plan" && scenePlan ? (
        <section className="scene-plan-panel">
          <div className="panel-title-row">
            <div>
              <h2>Scene Plan</h2>
              <p>{scenePlan.confirmed || scenePlanConfirmed ? "已确认，可继续生成剧本。" : "确认前只能查看，不提供字段编辑。"}</p>
            </div>
            <button className="primary-button" disabled={loading || scenePlan.confirmed || scenePlanConfirmed} type="button" onClick={onConfirmScenePlan}>
              {scenePlan.confirmed || scenePlanConfirmed ? "已确认" : "确认 Scene Plan"}
            </button>
          </div>
          {scenePlan.scenes.map((scene) => (
            <article className="scene-card" key={scene.scene_id}>
              <div className="scene-title">
                {scene.scene_id} {scene.title}
              </div>
              <p>{scene.scene_function}</p>
              <p className="muted-text">{scene.core_conflict}</p>
            </article>
          ))}
        </section>
      ) : null}

      {viewMode === "script" && yaml ? (
        <section className="script-panel">
          <div className="panel-header">
            <h2>YAML 剧本预览</h2>
          </div>
          <YamlPreview yaml={yaml} />
          <div className="evidence-actions" aria-label="来源证据入口">
            {scriptForUi?.content_blocks.map((block) => (
              <button
                className="ghost-button"
                key={block.content_block_id}
                type="button"
                onClick={() => setEvidenceBlockId(block.content_block_id)}
              >
                {block.display_label} 来源证据
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {(!scenePlan && viewMode === "scene-plan") || (!yaml && viewMode === "script") || viewMode === "conversation" ? (
        <section className="empty-result" aria-label="成果空状态">
          <div className="pulse-mark" aria-hidden="true" />
          <p>{statusText}</p>
          {viewMode === "scene-plan" ? (
            <button className="primary-button" disabled={loading} type="button" onClick={onGenerateScenePlan}>
              {loading ? "生成中" : "生成 Scene Plan"}
            </button>
          ) : null}
          {viewMode === "script" ? (
            <button className="primary-button" disabled={loading || !scenePlanConfirmed} type="button" onClick={onGenerateScript}>
              {loading ? "生成中" : "生成剧本"}
            </button>
          ) : null}
        </section>
      ) : null}

      {evidenceBlockId ? (
        <EvidenceModal
          projectId={projectId}
          contentBlockId={evidenceBlockId}
          fallback={fallbackEvidence[evidenceBlockId]}
          onClose={() => setEvidenceBlockId(null)}
        />
      ) : null}
    </aside>
  );
}

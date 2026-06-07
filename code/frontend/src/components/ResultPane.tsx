import { useState } from "react";

import previewEmptyArt from "../assets/coda-reading-book-3x.webp";
import type { AgentProgress as AgentProgressType, EvidenceLookupResult, ExportFormat, ExportResult, ScenePlan, ScriptCurrentForUi } from "../types";
import { AgentProgress } from "./AgentProgress";
import { EvidenceModal } from "./EvidenceModal";
import { ExportMenu } from "./ExportMenu";
import { ScriptPreviewPanel } from "./ScriptPreviewPanel";
import { YamlPreview } from "./YamlPreview";

type Props = {
  projectId: string;
  viewMode: "conversation" | "scene-plan" | "script";
  scenePlan: ScenePlan | null;
  scriptForUi: ScriptCurrentForUi | null;
  latestExport: ExportResult | null;
  yaml: string | null;
  statusText: string;
  failedStage?: string | null;
  scenePlanConfirmed: boolean;
  loading: boolean;
  fallbackEvidence: Record<string, EvidenceLookupResult>;
  progress: AgentProgressType | null;
  activeLabel: string | null;
  onExport: (format: ExportFormat) => void;
  onConfirmScenePlan: () => void;
  onGenerateScenePlan: () => void;
  onGenerateScript: () => void;
  onRepairScenePlan: () => void;
  onRepairScriptScene: (sceneId: string) => void;
};

export function ResultPane({
  activeLabel,
  failedStage,
  fallbackEvidence,
  latestExport,
  loading,
  projectId,
  progress,
  scenePlan,
  scenePlanConfirmed,
  scriptForUi,
  statusText,
  viewMode,
  yaml,
  onConfirmScenePlan,
  onGenerateScenePlan,
  onGenerateScript,
  onRepairScenePlan,
  onRepairScriptScene,
  onExport
}: Props) {
  const [evidenceBlockId, setEvidenceBlockId] = useState<string | null>(null);
  void onRepairScenePlan;
  void onRepairScriptScene;

  const showAgentProgress = Boolean(activeLabel) || progress?.status === "queued" || progress?.status === "running";
  const hasScript = Boolean(scriptForUi || yaml);

  return (
    <aside className="figma-result-panel" aria-label="成果区">
      <header className="figma-result-header">
        <div>
          <h2>预览</h2>
        </div>
        <ExportMenu disabled={!yaml} latestExport={latestExport} loading={loading} onExport={onExport} />
      </header>

      <div className="figma-result-body">
        {failedStage ? (
          <section className="figma-failure">
            <h3>本次生成未完成</h3>
            <p>失败阶段：{failedStage}</p>
          </section>
        ) : null}

        {viewMode === "scene-plan" && !scenePlan ? (
          <section className="figma-result-empty" aria-label="成果空状态">
            <img className="figma-empty-art" src={previewEmptyArt} alt="" aria-hidden="true" />
            <p>{statusText}</p>
            <button className="figma-primary" disabled={loading || !projectId} type="button" onClick={onGenerateScenePlan}>
              生成场景规划
            </button>
          </section>
        ) : null}

        {viewMode === "scene-plan" && scenePlan ? (
          <section className="figma-scene-plan">
            <div className="figma-result-title-row">
              <div>
                <h3>场景规划</h3>
                <p>{scenePlan.confirmed || scenePlanConfirmed ? "已确认，可以继续生成剧本。" : "确认前仅用于查看，不开放字段编辑。"}</p>
              </div>
              {scenePlan.confirmed || scenePlanConfirmed ? (
                <button className="figma-primary" disabled={loading || Boolean(yaml)} type="button" onClick={onGenerateScript}>
                  {yaml ? "剧本已生成" : "生成剧本"}
                </button>
              ) : (
                <button className="figma-primary" disabled={loading} type="button" onClick={onConfirmScenePlan}>
                  确认场景规划
                </button>
              )}
            </div>
            <div className="figma-scene-cards">
              {scenePlan.scenes.map((scene) => (
                <article className="figma-scene-card" key={scene.scene_id}>
                  <div className="figma-scene-card-title">
                    <span>{scene.scene_id}</span>
                    <strong>{scene.title}</strong>
                  </div>
                  <p>{scene.scene_function}</p>
                  <dl>
                    <div>
                      <dt>冲突</dt>
                      <dd>{scene.core_conflict}</dd>
                    </div>
                    <div>
                      <dt>人物</dt>
                      <dd>{scene.characters.join("、") || "待定"}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {viewMode === "script" && !hasScript ? (
          <section className="figma-result-empty" aria-label="成果空状态">
            <img className="figma-empty-art" src={previewEmptyArt} alt="" aria-hidden="true" />
            <p>{statusText}</p>
            {scenePlanConfirmed ? (
              <button className="figma-primary" disabled={loading || !projectId} type="button" onClick={onGenerateScript}>
                生成剧本
              </button>
            ) : null}
          </section>
        ) : null}

        {viewMode === "script" && hasScript ? (
          <>
            <div className="figma-result-title-row">
              <div>
                <h3>剧本预览</h3>
              </div>
            </div>
            {scriptForUi ? <ScriptPreviewPanel script={scriptForUi} onEvidenceClick={setEvidenceBlockId} /> : <YamlPreview yaml={yaml ?? ""} />}
          </>
        ) : null}

        {viewMode === "conversation" ? (
          <section className="figma-result-empty" aria-label="成果空状态">
            <img className="figma-empty-art" src={previewEmptyArt} alt="" aria-hidden="true" />
            <p>{statusText}</p>
          </section>
        ) : null}
      </div>

      {showAgentProgress ? <AgentProgress activeLabel={activeLabel} progress={progress} /> : null}

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

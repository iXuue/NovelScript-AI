import { useState } from "react";

import previewEmptyArt from "../assets/coda-reading-book-3x.webp";
import type { AgentProgress as AgentProgressType, EvidenceLookupResult, ExportFormat, ExportResult, ScenePlan, ScriptCurrentForUi } from "../types";
import { AgentProgress } from "./AgentProgress";
import { EvidenceModal } from "./EvidenceModal";
import { ExportMenu } from "./ExportMenu";
import { ScriptTextPreview } from "./ScriptTextPreview";
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

function LegacyResultPane({
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
  onConfirmScenePlan
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
              <h2>场景计划</h2>
              <p>{scenePlan.confirmed || scenePlanConfirmed ? "已确认，可继续生成剧本。" : "确认前只能查看，不提供字段编辑。"}</p>
            </div>
            <button className="primary-button" disabled={loading || scenePlan.confirmed || scenePlanConfirmed} type="button" onClick={onConfirmScenePlan}>
              {scenePlan.confirmed || scenePlanConfirmed ? "已确认" : "确认场景计划"}
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
            <h2>剧本文本预览</h2>
          </div>
          <ScriptTextPreview script={scriptForUi} />
          <h3>YAML 只读预览</h3>
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

  return (
    <aside className="figma-result-panel" aria-label="成果区">
      <header className="figma-result-header">
        <div>
          <h2>剧本预览</h2>
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
              生成场景计划
            </button>
          </section>
        ) : null}

        {viewMode === "scene-plan" && scenePlan ? (
          <section className="figma-scene-plan">
            <div className="figma-result-title-row">
              <div>
                <h3>场景计划</h3>
                <p>{scenePlan.confirmed || scenePlanConfirmed ? "已确认，可继续生成剧本。" : "确认前仅用于查看，不开放字段编辑。"}</p>
              </div>
              {scenePlan.confirmed || scenePlanConfirmed ? (
                <button className="figma-primary" disabled={loading || Boolean(yaml)} type="button" onClick={onGenerateScript}>
                  {yaml ? "剧本已生成" : "生成剧本"}
                </button>
              ) : (
                <button className="figma-primary" disabled={loading} type="button" onClick={onConfirmScenePlan}>
                  确认场景计划
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

        {viewMode === "script" && !yaml ? (
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

        {viewMode === "script" && yaml ? (
          <section className="figma-script-panel">
            <div className="figma-result-title-row">
              <div>
                <h3>剧本文本预览</h3>
                <p>只读预览。需要修订时，在对话区追加要求。</p>
              </div>
            </div>
            <ScriptTextPreview script={scriptForUi} />
            <div className="figma-result-title-row yaml-title-row">
              <div>
                <h3>YAML 只读预览</h3>
              </div>
            </div>
            <YamlPreview yaml={yaml} />
            <div className="figma-evidence-actions" aria-label="来源证据入口">
              {scriptForUi?.content_blocks.map((block) => (
                <button
                  className="figma-secondary"
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

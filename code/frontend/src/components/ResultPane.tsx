import { useState } from "react";
import type {
  EvidenceLookupResult,
  ExportFormat,
  ExportResult,
  ScenePlan,
  ScriptCurrentForUi,
} from "../types";
import { EvidenceModal } from "./EvidenceModal";
import { ExportMenu } from "./ExportMenu";
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
  onExport: (format: ExportFormat) => void;
  onConfirmScenePlan: () => void;
  onRepairScenePlan: () => void;
  onRepairScriptScene: (sceneId: string) => void;
};

type ValidationLike = {
  passed: boolean;
  issues: Array<{ code?: string; message: string }>;
  suggestions: string[];
};

export function ResultPane({
  projectId,
  viewMode,
  scenePlan,
  scriptForUi,
  latestExport,
  yaml,
  statusText,
  failedStage,
  scenePlanConfirmed,
  loading,
  fallbackEvidence,
  onExport,
  onConfirmScenePlan,
  onRepairScenePlan,
  onRepairScriptScene,
}: Props) {
  const [evidenceBlockId, setEvidenceBlockId] = useState<string | null>(null);
  const selectedEvidence = evidenceBlockId ? fallbackEvidence[evidenceBlockId] : null;
  const canExport = Boolean(scriptForUi || yaml || latestExport);
  const scenePlanValidation = scenePlan?.validation ?? null;
  const scenePlanFailed = Boolean(scenePlanValidation && !scenePlanValidation.passed);

  return (
    <section className="figma-result-panel">
      <header className="figma-result-header">
        <div>
          <p className="figma-eyebrow">PROJECT {projectId}</p>
          <h2>结果预览</h2>
          <span>{statusText}</span>
        </div>
        <ExportMenu disabled={!canExport} loading={loading} latestExport={latestExport} onExport={onExport} />
      </header>

      <div className="figma-result-body">
        {failedStage && (
          <div className="validation-summary failed">
            <strong>当前阶段需要修复</strong>
            <p>{failedStage}</p>
          </div>
        )}

        {viewMode === "scene-plan" && scenePlan ? (
          <div className="figma-scene-plan">
            <div className="figma-result-title-row">
              <h3>{scenePlan.title || "Scene Plan"}</h3>
              <div className="figma-inline-actions">
                {scenePlanFailed && (
                  <button className="figma-secondary" disabled={loading} onClick={onRepairScenePlan}>
                    修复场景规划
                  </button>
                )}
                <button
                  className="figma-primary"
                  disabled={loading || scenePlanConfirmed || scenePlanFailed}
                  onClick={onConfirmScenePlan}
                >
                  {scenePlanConfirmed ? "已确认" : "确认 Scene Plan"}
                </button>
              </div>
            </div>

            {scenePlanValidation && <ValidationSummary validation={scenePlanValidation} />}

            <div className="figma-scene-cards">
              {scenePlan.scenes.map((scene) => (
                <article key={scene.scene_id} className="figma-scene-card">
                  <div className="figma-scene-card-title">
                    <span>{scene.scene_id}</span>
                    <h4>{scene.title}</h4>
                  </div>
                  <p>{scene.scene_function}</p>
                  <dl>
                    <dt>内外景</dt>
                    <dd>{scene.interior_exterior || "未指定"}</dd>
                    <dt>核心冲突</dt>
                    <dd>{scene.core_conflict}</dd>
                    <dt>人物</dt>
                    <dd>{scene.characters.join("、") || "未指定"}</dd>
                    <dt>必须覆盖</dt>
                    <dd>{scene.must_cover_plot.join("；") || "未指定"}</dd>
                    <dt>保留对白</dt>
                    <dd>{scene.must_keep_dialogue.join("；") || "无"}</dd>
                    <dt>视觉元素</dt>
                    <dd>{scene.must_keep_visual_elements.join("；") || "无"}</dd>
                    <dt>伏笔</dt>
                    <dd>{scene.must_keep_foreshadowing.join("；") || "无"}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>
        ) : viewMode === "script" ? (
          <div className="figma-script-panel">
            {scriptForUi?.scenes?.length ? (
              <div className="figma-script-validation-list">
                {scriptForUi.scenes.map((scene) => (
                  <article key={scene.scene_id} className="validation-summary">
                    <div className="figma-result-title-row">
                      <strong>{scene.title || scene.scene_id}</strong>
                      {scene.validation && !scene.validation.passed && (
                        <button
                          className="figma-secondary"
                          disabled={loading}
                          onClick={() => onRepairScriptScene(scene.scene_id)}
                        >
                          修复本场
                        </button>
                      )}
                    </div>
                    {scene.validation && <ValidationSummary validation={scene.validation} />}
                    <p>
                      {scene.characters.join("、") || "未指定人物"} · {scene.scene_purpose || "未指定目的"}
                    </p>
                  </article>
                ))}
              </div>
            ) : null}

            {yaml ? <YamlPreview yaml={yaml} /> : <p className="figma-result-empty">剧本 YAML 尚未生成。</p>}

            {scriptForUi?.content_blocks?.length ? (
              <div className="figma-evidence-actions">
                <h4>证据追踪</h4>
                {scriptForUi.content_blocks.map((block) => (
                  <button
                    key={block.content_block_id}
                    className="figma-chip"
                    onClick={() => setEvidenceBlockId(block.content_block_id)}
                  >
                    {block.block_type} · {block.scene_id}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="figma-result-empty">
            <h3>等待生成结果</h3>
            <p>完成左侧流程后，这里会显示章节、Scene Plan、剧本 YAML 和导出结果。</p>
          </div>
        )}
      </div>

      {evidenceBlockId ? (
        <EvidenceModal
          projectId={projectId}
          contentBlockId={evidenceBlockId}
          fallback={selectedEvidence ?? undefined}
          onClose={() => setEvidenceBlockId(null)}
        />
      ) : null}
    </section>
  );
}

function ValidationSummary({ validation }: { validation: ValidationLike }) {
  return (
    <div className={`validation-summary ${validation.passed ? "passed" : "failed"}`}>
      <strong>{validation.passed ? "校验通过" : "校验未通过"}</strong>
      {validation.issues.length > 0 && (
        <ul>
          {validation.issues.map((issue, index) => (
            <li key={`${issue.code ?? "issue"}-${index}`}>
              {issue.code ? `${issue.code}: ` : ""}
              {issue.message}
            </li>
          ))}
        </ul>
      )}
      {validation.suggestions.length > 0 && (
        <p>建议：{validation.suggestions.join("；")}</p>
      )}
    </div>
  );
}

import { useState } from "react";
import type {
  EvidenceLookupResult,
  ExportFormat,
  ExportResult,
  ScenePlan,
  ScenePlanScene,
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
  issues?: Array<{ code?: string; message: string }>;
  suggestions?: string[];
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
  const scenes = Array.isArray(scenePlan?.scenes) ? scenePlan.scenes : [];
  const scriptScenes = Array.isArray(scriptForUi?.scenes) ? scriptForUi.scenes : [];
  const contentBlocks = Array.isArray(scriptForUi?.content_blocks) ? scriptForUi.content_blocks : [];

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
        {failedStage ? (
          <div className="validation-summary failed">
            <strong>当前阶段需要修复</strong>
            <p>{failedStage}</p>
          </div>
        ) : null}

        {viewMode === "scene-plan" && scenePlan ? (
          <div className="figma-scene-plan">
            <div className="figma-result-title-row">
              <h3>Scene Plan</h3>
              <div className="figma-inline-actions">
                {scenePlanFailed ? (
                  <button className="figma-secondary" disabled={loading} type="button" onClick={onRepairScenePlan}>
                    修复场景规划
                  </button>
                ) : null}
                <button
                  className="figma-primary"
                  disabled={loading || scenePlanConfirmed || scenePlanFailed}
                  type="button"
                  onClick={onConfirmScenePlan}
                >
                  {scenePlanConfirmed ? "已确认" : "确认 Scene Plan"}
                </button>
              </div>
            </div>

            {scenePlanValidation ? <ValidationSummary validation={scenePlanValidation} /> : null}

            {scenes.length > 0 ? (
              <div className="figma-scene-cards">
                {scenes.map((scene) => (
                  <SceneCard key={scene.scene_id} scene={scene} />
                ))}
              </div>
            ) : (
              <p className="figma-result-empty">Scene Plan 暂无场景数据。</p>
            )}
          </div>
        ) : viewMode === "script" ? (
          <div className="figma-script-panel">
            {scriptScenes.length ? (
              <div className="figma-script-validation-list">
                {scriptScenes.map((scene) => (
                  <article key={scene.scene_id} className="validation-summary">
                    <div className="figma-result-title-row">
                      <strong>{scene.title || scene.scene_id}</strong>
                      {scene.validation && !scene.validation.passed ? (
                        <button
                          className="figma-secondary"
                          disabled={loading}
                          type="button"
                          onClick={() => onRepairScriptScene(scene.scene_id)}
                        >
                          修复本场
                        </button>
                      ) : null}
                    </div>
                    {scene.validation ? <ValidationSummary validation={scene.validation} /> : null}
                    <p>
                      {joinText(scene.characters, "未指定人物")} · {scene.scene_purpose || "未指定目的"}
                    </p>
                  </article>
                ))}
              </div>
            ) : null}

            {yaml ? <YamlPreview yaml={yaml} /> : <p className="figma-result-empty">剧本 YAML 尚未生成。</p>}

            {contentBlocks.length ? (
              <div className="figma-evidence-actions">
                <h4>证据追踪</h4>
                {contentBlocks.map((block) => (
                  <button
                    key={block.content_block_id}
                    className="figma-chip"
                    type="button"
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

function SceneCard({ scene }: { scene: ScenePlanScene }) {
  return (
    <article className="figma-scene-card">
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
        <dd>{joinText(scene.characters, "未指定")}</dd>
        <dt>必须覆盖</dt>
        <dd>{joinText(scene.must_cover_plot, "未指定")}</dd>
        <dt>保留对白</dt>
        <dd>{joinText(scene.must_keep_dialogue, "无")}</dd>
        <dt>视觉元素</dt>
        <dd>{joinText(scene.must_keep_visual_elements, "无")}</dd>
        <dt>伏笔</dt>
        <dd>{joinText(scene.must_keep_foreshadowing, "无")}</dd>
      </dl>
    </article>
  );
}

function ValidationSummary({ validation }: { validation: ValidationLike }) {
  const issues = validation.issues ?? [];
  const suggestions = validation.suggestions ?? [];
  return (
    <div className={`validation-summary ${validation.passed ? "passed" : "failed"}`}>
      <strong>{validation.passed ? "校验通过" : "校验未通过"}</strong>
      {issues.length > 0 ? (
        <ul>
          {issues.map((issue, index) => (
            <li key={`${issue.code ?? "issue"}-${index}`}>
              {issue.code ? `${issue.code}: ` : ""}
              {issue.message}
            </li>
          ))}
        </ul>
      ) : null}
      {suggestions.length > 0 ? <p>建议：{suggestions.join("；")}</p> : null}
    </div>
  );
}

function joinText(value: string[] | undefined, fallback: string): string {
  return Array.isArray(value) && value.length > 0 ? value.join("；") : fallback;
}

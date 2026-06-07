import { useState, type ChangeEvent, type FormEvent } from "react";

import type { ChapterDraft, ConversationMessage, FeedbackPlan, StyleSource, UiMode } from "../types";
import { ChapterConfirmation } from "./ChapterConfirmation";
import { StyleSourceSelector } from "./StyleSourceSelector";

type Props = {
  messages: ConversationMessage[];
  projectName: string;
  mode: UiMode;
  statusMessage: string | null;
  error: string | null;
  uploadedNovelName: string | null;
  styleLocked: boolean;
  selectedStyle: StyleSource | null;
  hasNovelUpload: boolean;
  chapters: ChapterDraft[];
  chaptersConfirmed: boolean;
  pendingFeedbackPlan?: FeedbackPlan | null;
  feedbackChapterOptions?: Array<{ chapterId: string; label: string }>;
  feedbackTargetMode?: "script" | "chapters";
  selectedFeedbackChapterIds?: string[];
  canGenerateScenePlan: boolean;
  canGenerateScript: boolean;
  loading: boolean;
  onStyleChange: (source: StyleSource | null) => void;
  onStyleReferenceSelected: (file: File) => void;
  onNovelSelected: (file: File) => void;
  onConfirmChapters: () => void;
  onGenerateScenePlan: () => void;
  onGenerateScript: () => void;
  onConfirmFeedbackPlan?: () => void;
  onCancelFeedbackPlan?: () => void;
  onFeedbackTargetModeChange?: (mode: "script" | "chapters") => void;
  onFeedbackChapterToggle?: (chapterId: string, selected: boolean) => void;
  onSubmitMessage: (content: string) => void;
};

export function ConversationPane({
  chapters,
  chaptersConfirmed,
  canGenerateScenePlan,
  canGenerateScript,
  error,
  hasNovelUpload,
  loading,
  messages,
  pendingFeedbackPlan,
  feedbackChapterOptions = [],
  feedbackTargetMode = "script",
  selectedFeedbackChapterIds = [],
  selectedStyle,
  styleLocked,
  uploadedNovelName,
  onConfirmChapters,
  onConfirmFeedbackPlan = () => undefined,
  onCancelFeedbackPlan = () => undefined,
  onFeedbackTargetModeChange = () => undefined,
  onFeedbackChapterToggle = () => undefined,
  onGenerateScenePlan,
  onGenerateScript,
  onNovelSelected,
  onStyleChange,
  onStyleReferenceSelected,
  onSubmitMessage
}: Props) {
  const [draft, setDraft] = useState("");
  const [feedbackTargetOpen, setFeedbackTargetOpen] = useState(false);
  const needsSetup = !hasNovelUpload || !selectedStyle;
  const showSetupHint = needsSetup && messages.length === 0;
  const showGenerateAction = canGenerateScenePlan || canGenerateScript;
  const generateLabel = canGenerateScenePlan ? "开始生成 Scene Plan" : "开始生成剧本";
  const handleGenerate = canGenerateScenePlan ? onGenerateScenePlan : onGenerateScript;
  const feedbackTargetSummary = selectedFeedbackChapterIds.length > 0 ? `已选 ${selectedFeedbackChapterIds.length} 章` : "全部章节";

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      onNovelSelected(file);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.trim()) {
      onSubmitMessage(draft.trim());
      setDraft("");
      event.currentTarget.reset();
    }
  }

  return (
    <main className="figma-conversation" aria-label="对话区">
      {error ? (
        <header className="figma-panel-header figma-panel-header-error">
          <div className="figma-connection error">
            <span className="figma-status-dot" aria-hidden="true" />
            <span>{error}</span>
          </div>
        </header>
      ) : null}

      <div className="figma-conversation-body">
        {showSetupHint ? (
          <section className="figma-empty-prompt">
            <h2>请上传小说并完成风格设计</h2>
            <p>完成章节确认和风格选择后，就可以开始生成 Scene Plan。</p>
            {showGenerateAction ? (
              <button className="figma-primary figma-generate-cta" disabled={loading} type="button" onClick={handleGenerate}>
                {generateLabel}
              </button>
            ) : null}
          </section>
        ) : null}

        <ChapterConfirmation chapters={chapters} confirmed={chaptersConfirmed} loading={loading} onConfirm={onConfirmChapters} />

        {showGenerateAction && !showSetupHint ? (
          <section className="figma-next-step-panel" aria-label="下一步操作">
            <div>
              <strong>{canGenerateScenePlan ? "章节和风格已就绪" : "Scene Plan 已确认"}</strong>
              <p>{canGenerateScenePlan ? "现在可以生成场景规划。" : "现在可以逐场生成剧本。"}</p>
            </div>
            <button className="figma-primary figma-generate-cta" disabled={loading} type="button" onClick={handleGenerate}>
              {generateLabel}
            </button>
          </section>
        ) : null}

        <section className="figma-message-list" aria-label="对话记录">
          {messages.map((message) => (
            <article className={`figma-message ${message.role}`} key={message.message_id}>
              <div className="figma-message-role">{message.role === "user" ? "用户" : "Agent"}</div>
              <p>{message.content}</p>
            </article>
          ))}
        </section>

        {pendingFeedbackPlan ? (
          <section className="figma-next-step-panel" aria-label="修改计划">
            <div>
              <strong>{pendingFeedbackPlan.cache_hit ? "已命中缓存修改计划" : "修改计划待确认"}</strong>
              <ul>
                {pendingFeedbackPlan.modification_plan.modification_plan.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {pendingFeedbackPlan.modification_plan.needs_source_text ? <p>执行时会按计划精确读取必要原文。</p> : null}
            </div>
            <div className="figma-composer-main-actions">
              <button className="figma-primary" disabled={loading} type="button" onClick={onConfirmFeedbackPlan}>
                确认执行
              </button>
              <button className="figma-secondary" disabled={loading} type="button" onClick={onCancelFeedbackPlan}>
                取消
              </button>
            </div>
          </section>
        ) : null}
      </div>

      <form className="figma-composer" onSubmit={handleSubmit}>
        <div className="figma-composer-field">
          <textarea
            aria-label="对话输入"
            disabled={loading}
            placeholder="请先上传文档并选择风格；"
            rows={4}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="figma-composer-actions">
            <div className="figma-composer-tools">
              <label className="figma-attachment-icon figma-composer-tool-button figma-composer-control-button" title="上传文档">
                <span aria-hidden="true">+</span>
                <strong>上传文档</strong>
                <input aria-label="上传小说附件" disabled={loading} type="file" accept=".md,.txt,.docx,.pdf" onChange={handleFileChange} />
              </label>
              <StyleSourceSelector
                locked={styleLocked}
                loading={loading}
                selected={selectedStyle}
                onChange={onStyleChange}
                onReferenceFileSelected={onStyleReferenceSelected}
              />
              {uploadedNovelName ? <span className="figma-uploaded-name">{uploadedNovelName}</span> : null}
              {feedbackChapterOptions.length > 0 ? (
                <div className="figma-feedback-target-menu">
                  <button
                    aria-controls="feedback-target-popover"
                    aria-expanded={feedbackTargetOpen}
                    className="figma-feedback-target-trigger figma-composer-control-button"
                    disabled={loading}
                    type="button"
                    onClick={() => setFeedbackTargetOpen((value) => !value)}
                  >
                    <strong>修改目标</strong>
                    <span className="figma-feedback-target-summary">{feedbackTargetSummary}</span>
                    <span className="figma-feedback-target-chevron" aria-hidden="true" />
                  </button>
                  {feedbackTargetOpen ? (
                    <fieldset className="figma-feedback-target-popover" id="feedback-target-popover" aria-label="修改目标选项">
                  <legend>修改目标</legend>
                  <label className="figma-feedback-target-choice">
                    <input
                      checked={feedbackTargetMode === "script"}
                      disabled={loading}
                      name="feedback-target"
                      type="radio"
                      onChange={() => onFeedbackTargetModeChange("script")}
                    />
                    <span>全部章节</span>
                  </label>
                  <div className="figma-feedback-chapter-group">
                    <span>指定章节（可多选）</span>
                    <div className="figma-feedback-chapter-list">
                      {feedbackChapterOptions.map((option) => (
                        <label className="figma-feedback-target-choice" key={option.chapterId}>
                          <input
                            checked={feedbackTargetMode === "chapters" && selectedFeedbackChapterIds.includes(option.chapterId)}
                            disabled={loading}
                            type="checkbox"
                            onChange={(event) => onFeedbackChapterToggle(option.chapterId, event.target.checked)}
                          />
                          <span>{option.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                    </fieldset>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="figma-composer-main-actions">
              {showGenerateAction ? (
                <button className="figma-primary" disabled={loading} type="button" onClick={handleGenerate}>
                  {canGenerateScenePlan ? "开始生成" : "生成剧本"}
                </button>
              ) : null}
              <button className="figma-secondary" type="submit" disabled={loading || needsSetup}>
                {loading ? "处理中" : "发送"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}

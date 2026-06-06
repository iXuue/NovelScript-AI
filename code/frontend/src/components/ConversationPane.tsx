import { useState, type ChangeEvent, type FormEvent } from "react";

import type { AgentProgress as AgentProgressType, ChapterDraft, ConversationMessage, StyleSource, UiMode } from "../types";
import { AgentProgress } from "./AgentProgress";
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
  canGenerateScenePlan: boolean;
  canGenerateScript: boolean;
  progress: AgentProgressType | null;
  loading: boolean;
  activeLabel: string | null;
  onStyleChange: (source: StyleSource | null) => void;
  onStyleReferenceSelected: (file: File) => void;
  onNovelSelected: (file: File) => void;
  onConfirmChapters: () => void;
  onGenerateScenePlan: () => void;
  onGenerateScript: () => void;
  onSubmitMessage: (content: string) => void;
};

export function ConversationPane({
  activeLabel,
  chapters,
  chaptersConfirmed,
  canGenerateScenePlan,
  canGenerateScript,
  error,
  hasNovelUpload,
  loading,
  messages,
  progress,
  selectedStyle,
  styleLocked,
  uploadedNovelName,
  onConfirmChapters,
  onGenerateScenePlan,
  onGenerateScript,
  onNovelSelected,
  onStyleChange,
  onStyleReferenceSelected,
  onSubmitMessage,
}: Props) {
  const [draft, setDraft] = useState("");
  const needsSetup = !hasNovelUpload || !selectedStyle;
  const showSetupHint = needsSetup && messages.length === 0;
  const showAgentProgress = Boolean(activeLabel) || progress?.status === "queued" || progress?.status === "running";
  const showGenerateAction = canGenerateScenePlan || canGenerateScript;
  const generateLabel = canGenerateScenePlan ? "开始生成 Scene Plan" : "开始生成剧本";
  const handleGenerate = canGenerateScenePlan ? onGenerateScenePlan : onGenerateScript;

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

      <StyleSourceSelector
        locked={styleLocked}
        loading={loading}
        selected={selectedStyle}
        onChange={onStyleChange}
        onReferenceFileSelected={onStyleReferenceSelected}
      />

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

        {showAgentProgress ? <AgentProgress activeLabel={activeLabel} progress={progress} /> : null}
      </div>

      <form className="figma-composer" onSubmit={handleSubmit}>
        <div className="figma-composer-field">
          <textarea
            aria-label="对话输入"
            disabled={loading}
            placeholder="输入要求，例如：把第一场对白改得更短。"
            rows={4}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="figma-composer-actions">
            <div className="figma-composer-tools">
              <label className="figma-attachment-icon" title="上传小说附件">
                <span aria-hidden="true">+</span>
                <input aria-label="上传小说附件" disabled={loading} type="file" accept=".md,.txt,.docx,.pdf" onChange={handleFileChange} />
              </label>
              {uploadedNovelName ? <span className="figma-uploaded-name">{uploadedNovelName}</span> : null}
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

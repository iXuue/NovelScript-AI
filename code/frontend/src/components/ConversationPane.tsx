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
  progress: AgentProgressType | null;
  loading: boolean;
  activeLabel: string | null;
  onStyleChange: (source: StyleSource | null) => void;
  onStyleReferenceSelected: (file: File) => void;
  onNovelSelected: (file: File) => void;
  onConfirmChapters: () => void;
  onSubmitMessage: (content: string) => void;
};

function LegacyConversationPane({
  messages,
  styleLocked,
  selectedStyle,
  hasNovelUpload,
  chapters,
  chaptersConfirmed,
  progress,
  loading,
  activeLabel,
  onStyleChange,
  onStyleReferenceSelected,
  onNovelSelected
  ,
  onConfirmChapters,
  onSubmitMessage
}: Props) {
  const [draft, setDraft] = useState("");
  const needsSetup = !hasNovelUpload || !selectedStyle;

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
    <main className="conversation-pane" aria-label="对话区">
      <StyleSourceSelector
        locked={styleLocked}
        loading={loading}
        selected={selectedStyle}
        onChange={onStyleChange}
        onReferenceFileSelected={onStyleReferenceSelected}
      />
      {needsSetup ? <p className="setup-hint">请上传小说并完成风格设计</p> : null}
      <ChapterConfirmation chapters={chapters} confirmed={chaptersConfirmed} loading={loading} onConfirm={onConfirmChapters} />
      <section className="message-list" aria-label="对话记录">
        {messages.map((message) => (
          <article className={`message ${message.role}`} key={message.message_id}>
            <div className="message-role">{message.role === "user" ? "用户" : "Agent"}</div>
            <p>{message.content}</p>
          </article>
        ))}
      </section>
      <AgentProgress activeLabel={activeLabel} progress={progress} />
      <form className="composer" onSubmit={handleSubmit}>
        <label className="attachment-button">
          上传小说附件
          <input aria-label="上传小说附件" disabled={loading} type="file" accept=".md,.txt,.docx,.pdf" onChange={handleFileChange} />
        </label>
        <input
          aria-label="对话输入"
          disabled={loading}
          placeholder="输入要求，例如：把第一场对白改得更短"
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button className="primary-button" type="submit" disabled={loading || needsSetup}>
          {loading ? "处理中" : "发送"}
        </button>
      </form>
    </main>
  );
}

export function ConversationPane({
  activeLabel,
  chapters,
  chaptersConfirmed,
  error,
  hasNovelUpload,
  loading,
  messages,
  progress,
  selectedStyle,
  styleLocked,
  uploadedNovelName,
  onConfirmChapters,
  onNovelSelected,
  onStyleChange,
  onStyleReferenceSelected,
  onSubmitMessage
}: Props) {
  const [draft, setDraft] = useState("");
  const needsSetup = !hasNovelUpload || !selectedStyle;
  const showSetupHint = needsSetup && messages.length === 0;
  const showAgentProgress =
    Boolean(activeLabel) || progress?.status === "queued" || progress?.status === "running";

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
            <p>上传后系统会识别章节、生成摘要、建立证据索引，并进入场景计划阶段。</p>
          </section>
        ) : null}

        <ChapterConfirmation chapters={chapters} confirmed={chaptersConfirmed} loading={loading} onConfirm={onConfirmChapters} />

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
            placeholder="输入要求，例如：把第一场对白改得更短"
            rows={4}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="figma-composer-actions">
            <div className="figma-composer-tools">
              <label className="figma-attachment-icon" title="上传小说附件">
                <span aria-hidden="true">🔗</span>
                <input aria-label="上传小说附件" disabled={loading} type="file" accept=".md,.txt,.docx,.pdf" onChange={handleFileChange} />
              </label>
              {uploadedNovelName ? <span className="figma-uploaded-name">{uploadedNovelName}</span> : null}
            </div>
            <button className="figma-primary" type="submit" disabled={loading || needsSetup}>
              {loading ? "处理中" : "发送"}
            </button>
          </div>
        </div>
      </form>
    </main>
  );
}

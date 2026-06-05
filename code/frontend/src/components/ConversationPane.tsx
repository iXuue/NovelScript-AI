import { useState, type ChangeEvent, type FormEvent } from "react";

import type { AgentProgress as AgentProgressType, ChapterDraft, ConversationMessage, StyleSource } from "../types";
import { AgentProgress } from "./AgentProgress";
import { ChapterConfirmation } from "./ChapterConfirmation";
import { StyleSourceSelector } from "./StyleSourceSelector";

type Props = {
  messages: ConversationMessage[];
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

export function ConversationPane({
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
      {needsSetup ? <p className="setup-hint">请上传小说并选择风格来源</p> : null}
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

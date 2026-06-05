import type { ChangeEvent } from "react";

import type { AgentProgress as AgentProgressType, ConversationMessage, StyleSource } from "../types";
import { AgentProgress } from "./AgentProgress";
import { StyleSourceSelector } from "./StyleSourceSelector";

type Props = {
  messages: ConversationMessage[];
  styleLocked: boolean;
  selectedStyle: StyleSource | null;
  hasNovelUpload: boolean;
  progress: AgentProgressType | null;
  onStyleChange: (source: StyleSource | null) => void;
  onNovelSelected: (file: File) => void;
};

export function ConversationPane({
  messages,
  styleLocked,
  selectedStyle,
  hasNovelUpload,
  progress,
  onStyleChange,
  onNovelSelected
}: Props) {
  const needsSetup = !hasNovelUpload || !selectedStyle;

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      onNovelSelected(file);
    }
  }

  return (
    <main className="conversation-pane" aria-label="对话区">
      <StyleSourceSelector locked={styleLocked} selected={selectedStyle} onChange={onStyleChange} />
      {needsSetup ? <p className="setup-hint">请上传小说并选择风格来源</p> : null}
      <section className="message-list" aria-label="对话记录">
        {messages.map((message) => (
          <article className={`message ${message.role}`} key={message.message_id}>
            <div className="message-role">{message.role === "user" ? "用户" : "Agent"}</div>
            <p>{message.content}</p>
          </article>
        ))}
      </section>
      <AgentProgress progress={progress} />
      <form className="composer" onSubmit={(event) => event.preventDefault()}>
        <label className="attachment-button">
          上传小说附件
          <input aria-label="上传小说附件" type="file" accept=".md,.txt,.docx,.pdf" onChange={handleFileChange} />
        </label>
        <input aria-label="对话输入" placeholder="输入要求..." type="text" />
        <button className="primary-button" type="submit" disabled={needsSetup}>
          发送
        </button>
      </form>
    </main>
  );
}


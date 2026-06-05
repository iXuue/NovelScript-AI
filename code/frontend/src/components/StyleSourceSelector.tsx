import { useState } from "react";

import type { StyleSource } from "../types";

const builtins = [
  { key: "realism", label: "现实主义" },
  { key: "suspense", label: "悬疑/惊悚" },
  { key: "romance", label: "爱情/情感" },
  { key: "comedy", label: "喜剧" },
  { key: "short_drama", label: "短剧/网剧" }
] as const;

type Props = {
  locked: boolean;
  loading: boolean;
  selected: StyleSource | null;
  onChange: (source: StyleSource | null) => void;
  onReferenceFileSelected: (file: File) => void;
};

function LegacyStyleSourceSelector({ locked, loading, selected, onChange, onReferenceFileSelected }: Props) {
  const [customText, setCustomText] = useState("");
  const [referenceFileName, setReferenceFileName] = useState("");
  const hasText = customText.trim().length > 0;
  const hasReference = referenceFileName.length > 0;

  return (
    <section className="style-source" aria-label="风格来源">
      <div className="section-label">风格来源</div>
      <div className="style-cards">
        {builtins.map((style) => (
          <button
            key={style.key}
            className={selected?.kind === "builtin" && selected.builtin_style === style.key ? "style-card active" : "style-card"}
            disabled={locked || loading}
            type="button"
            onClick={() => onChange({ kind: "builtin", builtin_style: style.key })}
          >
            {style.label}
          </button>
        ))}
      </div>
      <div className="custom-style">
        <label htmlFor="custom-style-text">自定义风格描述</label>
        <textarea
          id="custom-style-text"
          value={customText}
          disabled={locked || loading || hasReference}
          rows={3}
          placeholder="例如：对白短促，节奏紧张，保留现实质感。"
          onChange={(event) => {
            const value = event.target.value;
            setCustomText(value);
            if (referenceFileName) {
              setReferenceFileName("");
            }
            onChange(value.trim() ? { kind: "custom_text", style_text: value } : null);
          }}
        />
        <label className="file-control">
          <span>历史剧本参考</span>
          <input
            aria-label="上传历史剧本参考"
            disabled={locked || loading || hasText}
            type="file"
            accept=".md,.txt,.docx,.pdf"
            onChange={(event) => {
              const file = event.target.files?.[0];
              setReferenceFileName(file?.name ?? "");
              if (file) {
                onReferenceFileSelected(file);
              }
            }}
          />
        </label>
        {referenceFileName ? <div className="file-name">{referenceFileName}</div> : null}
      </div>
    </section>
  );
}

const styleChoices: Array<{ key: Extract<StyleSource, { kind: "builtin" }>["builtin_style"]; label: string }> = [
  { key: "realism", label: "现实主义" },
  { key: "suspense", label: "悬疑/惊悚" },
  { key: "romance", label: "爱情/情感" },
  { key: "comedy", label: "喜剧" },
  { key: "short_drama", label: "短剧/网剧" }
];

export function StyleSourceSelector({ locked, loading, selected, onChange, onReferenceFileSelected }: Props) {
  const [customText, setCustomText] = useState("");
  const [referenceFileName, setReferenceFileName] = useState("");
  const [expanded, setExpanded] = useState(false);
  const hasText = customText.trim().length > 0;
  const hasReference = referenceFileName.length > 0;
  const selectedBuiltin = selected?.kind === "builtin" ? styleChoices.find((style) => style.key === selected.builtin_style) : null;
  const selectedLabel =
    selectedBuiltin?.label ??
    (selected?.kind === "custom_text"
      ? "自定义风格描述"
      : selected?.kind === "reference_scripts"
        ? referenceFileName || "已上传参考剧本"
        : "请选择风格来源");

  return (
    <section className="figma-style-source" aria-label="风格来源">
      <button
        className="figma-style-trigger"
        type="button"
        disabled={locked || loading}
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        <div className="figma-style-summary">
          <div className="figma-section-label">风格来源</div>
          <h2>{selectedLabel}</h2>
        </div>
        <span className={expanded ? "figma-chevron open" : "figma-chevron"} aria-hidden="true" />
      </button>

      {locked ? <span className="figma-lock-badge">已锁定</span> : null}

      {expanded ? (
        <div className="figma-style-expanded">
          <div className="figma-style-options">
            {styleChoices.map((style) => (
              <button
                key={style.key}
                className={selected?.kind === "builtin" && selected.builtin_style === style.key ? "figma-style-pill active" : "figma-style-pill"}
                disabled={locked || loading}
                type="button"
                onClick={() => {
                  onChange({ kind: "builtin", builtin_style: style.key });
                  setExpanded(false);
                }}
              >
                {style.label}
              </button>
            ))}
          </div>

          <div className="figma-style-custom">
            <label htmlFor="custom-style-text">
              <span>自定义风格描述</span>
              <textarea
                id="custom-style-text"
                value={customText}
                disabled={locked || loading || hasReference}
                rows={3}
                placeholder="例如：对白短促，节奏紧张，保留现实质感。"
                onChange={(event) => {
                  const value = event.target.value;
                  setCustomText(value);
                  if (referenceFileName) {
                    setReferenceFileName("");
                  }
                  onChange(value.trim() ? { kind: "custom_text", style_text: value } : null);
                }}
              />
            </label>

            <label className="figma-reference-upload">
              <span>历史剧本参考</span>
              <input
                aria-label="上传历史剧本参考"
                disabled={locked || loading || hasText}
                type="file"
                accept=".md,.txt,.docx,.pdf"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  setReferenceFileName(file?.name ?? "");
                  if (file) {
                    onReferenceFileSelected(file);
                    setExpanded(false);
                  }
                }}
              />
            </label>
            {referenceFileName ? <div className="figma-file-name">{referenceFileName}</div> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

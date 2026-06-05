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
  selected: StyleSource | null;
  onChange: (source: StyleSource | null) => void;
};

export function StyleSourceSelector({ locked, selected, onChange }: Props) {
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
            disabled={locked}
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
          disabled={locked || hasReference}
          rows={3}
          placeholder="例如：对白短促，节奏紧张，保留现实质感。"
          onChange={(event) => {
            const value = event.target.value;
            setCustomText(value);
            onChange(value.trim() ? { kind: "custom_text", style_text: value } : null);
          }}
        />
        <label className="file-control">
          <span>历史剧本参考</span>
          <input
            aria-label="上传历史剧本参考"
            disabled={locked || hasText}
            type="file"
            accept=".md,.txt,.docx,.pdf"
            onChange={(event) => {
              const file = event.target.files?.[0];
              setReferenceFileName(file?.name ?? "");
              if (file) {
                onChange({ kind: "reference_scripts", reference_file_ids: ["pending_upload"] });
              }
            }}
          />
        </label>
        {referenceFileName ? <div className="file-name">{referenceFileName}</div> : null}
      </div>
    </section>
  );
}

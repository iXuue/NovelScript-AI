import { useEffect, useMemo, useState } from "react";

import type { StyleSource } from "../types";

type Props = {
  locked: boolean;
  loading: boolean;
  selected: StyleSource | null;
  onChange: (source: StyleSource | null) => void;
  onReferenceFileSelected: (file: File) => void;
};

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
  const [modalOpen, setModalOpen] = useState(false);
  const selectedBuiltin = selected?.kind === "builtin" ? styleChoices.find((style) => style.key === selected.builtin_style) : null;
  const referenceFileSummary = useMemo(() => {
    if (referenceFileName) return referenceFileName;
    if (selected?.kind === "reference_scripts") {
      return selected.reference_file_ids.join("、");
    }
    return "";
  }, [referenceFileName, selected]);
  const hasText = customText.trim().length > 0;
  const hasReference = Boolean(referenceFileSummary);
  const selectedLabel =
    selectedBuiltin?.label ??
    (selected?.kind === "custom_text"
      ? "自定义风格描述"
      : selected?.kind === "reference_scripts"
        ? referenceFileSummary || "已上传参考剧本"
        : "设计生成风格");

  useEffect(() => {
    if (selected?.kind === "custom_text") {
      setCustomText(selected.style_text);
      setReferenceFileName("");
      return;
    }
    if (selected?.kind === "reference_scripts") {
      setCustomText("");
    }
  }, [selected]);

  function handleBuiltinSelect(style: Extract<StyleSource, { kind: "builtin" }>["builtin_style"]) {
    if (locked) return;
    setCustomText("");
    setReferenceFileName("");
    onChange({ kind: "builtin", builtin_style: style });
  }

  function handleCustomDone() {
    if (locked) {
      setModalOpen(false);
      return;
    }
    const trimmedText = customText.trim();
    if (trimmedText || selected?.kind === "custom_text") {
      onChange(trimmedText ? { kind: "custom_text", style_text: customText } : null);
    }
    setModalOpen(false);
  }

  function handleReferenceSelected(file: File) {
    if (locked) return;
    setReferenceFileName(file.name);
    setCustomText("");
    onReferenceFileSelected(file);
  }

  return (
    <section className="figma-style-source" aria-label="风格设计">
      <button className="figma-style-trigger figma-composer-control-button" type="button" disabled={loading} onClick={() => setModalOpen(true)}>
        <div className="figma-style-summary">
          <h2>{selectedLabel}</h2>
        </div>
      </button>

      {modalOpen ? (
        <div className="figma-style-modal-scrim" role="presentation">
          <section className="figma-style-modal" role="dialog" aria-modal="true" aria-labelledby="style-design-title">
            <header className="figma-style-modal-header">
              <div>
                <h2 id="style-design-title">设计生成风格</h2>
              </div>
              <button className="figma-style-close" type="button" aria-label="关闭风格设计" onClick={() => setModalOpen(false)}>
                x
              </button>
            </header>

            <div className="figma-style-modal-section">
              <h3>内置风格</h3>
              <p>{locked ? "当前风格已用于后续生成，可查看已选择的内容。" : "选择一个基础方向，也可以用自定义描述或参考剧本补充。"}</p>
            </div>
            <div className="figma-style-options">
              {styleChoices.map((style) => (
                <button
                  key={style.key}
                  className={selected?.kind === "builtin" && selected.builtin_style === style.key ? "figma-style-pill active" : "figma-style-pill"}
                  disabled={locked || loading}
                  type="button"
                  onClick={() => handleBuiltinSelect(style.key)}
                >
                  {style.label}
                </button>
              ))}
            </div>

            <div className="figma-style-custom">
              <label htmlFor="custom-style-text">
                <span>自定义风格描述</span>
                <textarea
                  aria-label="自定义风格描述"
                  id="custom-style-text"
                  value={customText}
                  disabled={locked || loading || hasReference}
                  rows={3}
                  placeholder="例如：对白短促，节奏紧张，保留现实质感。"
                  onChange={(event) => {
                    setCustomText(event.target.value);
                    if (referenceFileName) {
                      setReferenceFileName("");
                    }
                  }}
                />
                <small>适合描述节奏、对白、影像质感和改编边界。</small>
              </label>

              <label className={locked || loading || hasText ? "figma-reference-upload disabled" : "figma-reference-upload"}>
                <span className="figma-reference-label">历史剧本参考</span>
                <span className="figma-reference-control">
                  <span className="figma-reference-icon" aria-hidden="true">
                    #
                  </span>
                  <span className="figma-reference-copy">
                    <strong>{referenceFileSummary || "上传参考剧本文件"}</strong>
                    <small>{referenceFileSummary ? "已保存的参考剧本。" : customText.trim() ? "已填写自定义描述，暂不能上传参考文件。" : "支持 md、txt、docx、pdf。"}</small>
                  </span>
                </span>
                <input
                  aria-label="上传历史剧本参考"
                  disabled={locked || loading || hasText}
                  type="file"
                  accept=".md,.txt,.doc,.docx,.pdf"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      handleReferenceSelected(file);
                    }
                  }}
                />
              </label>
              {referenceFileSummary ? <div className="figma-file-name">{referenceFileSummary}</div> : null}
            </div>

            <footer className="figma-style-modal-footer">
              <button className="figma-secondary" type="button" onClick={handleCustomDone}>
                完成
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}

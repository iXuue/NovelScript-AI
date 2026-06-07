import { type MouseEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { getEvidenceByContentBlock } from "../api/client";
import type { EvidenceLookupResult } from "../types";

type Props = {
  projectId: string;
  contentBlockId: string;
  fallback?: EvidenceLookupResult;
  onClose: () => void;
};

type EvidenceItem = EvidenceLookupResult["evidence"][number];

function paragraphLabel(item: EvidenceItem): string {
  const ids = item.paragraph_ids?.length
    ? item.paragraph_ids
    : [item.source_paragraph_id ?? item.paragraph_id].filter((value): value is string => Boolean(value));
  return ids.length > 0 ? ids.join(", ") : item.chapter_id;
}

export function EvidenceModal({ projectId, contentBlockId, fallback, onClose }: Props) {
  const [result, setResult] = useState<EvidenceLookupResult | null>(fallback ?? null);
  const [error, setError] = useState<string | null>(null);

  function handleClose(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    onClose();
  }

  function handleScrimClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  useEffect(() => {
    let mounted = true;
    getEvidenceByContentBlock(projectId, contentBlockId)
      .then((payload) => {
        if (mounted) {
          setResult(payload);
        }
      })
      .catch((err: Error) => {
        if (!mounted) return;
        if (fallback) {
          setResult(fallback);
        } else {
          setError(err.message);
        }
      });
    return () => {
      mounted = false;
    };
  }, [contentBlockId, fallback, projectId]);

  return createPortal(
    <div className="modal-scrim" role="presentation" onClick={handleScrimClick}>
      <section
        className="evidence-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="evidence-title">来源段落</h2>
          <button aria-label="关闭来源段落弹窗" className="icon-button" type="button" onClick={handleClose}>
            ×
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        {!result && !error ? <p className="muted-text">正在读取来源段落</p> : null}
        {result?.evidence.map((item) => (
          <article className="evidence-item" key={item.source_paragraph_id ?? item.source_evidence_id ?? `${item.chapter_id}-${item.paragraph_id}`}>
            <p className="evidence-paragraph-line">
              <strong>{paragraphLabel(item)}</strong>
              <span> : {item.text}</span>
            </p>
          </article>
        ))}
        {result && result.evidence.length === 0 ? <p className="muted-text">暂无可展示来源段落。</p> : null}
      </section>
    </div>,
    document.body
  );
}
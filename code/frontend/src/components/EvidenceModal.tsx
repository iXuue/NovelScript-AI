import { useEffect, useState } from "react";

import { getEvidenceByContentBlock } from "../api/client";
import type { EvidenceLookupResult } from "../types";

type Props = {
  projectId: string;
  contentBlockId: string;
  fallback?: EvidenceLookupResult;
  onClose: () => void;
};

export function EvidenceModal({ projectId, contentBlockId, fallback, onClose }: Props) {
  const [result, setResult] = useState<EvidenceLookupResult | null>(fallback ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getEvidenceByContentBlock(projectId, contentBlockId)
      .then((payload) => {
        if (mounted) {
          setResult(payload);
        }
      })
      .catch((err: Error) => {
        if (mounted) {
          if (fallback) {
            setResult(fallback);
          } else {
            setError(err.message);
          }
        }
      });
    return () => {
      mounted = false;
    };
  }, [contentBlockId, projectId]);

  return (
    <div className="modal-scrim" role="presentation">
      <section className="evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title">
        <div className="modal-header">
          <h2 id="evidence-title">来源证据</h2>
          <button aria-label="关闭来源证据弹窗" className="icon-button" type="button" onClick={onClose}>
            X
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        {!result && !error ? <p className="muted-text">正在读取来源证据</p> : null}
        {result?.evidence.map((item) => (
          <article className="evidence-item" key={item.source_evidence_id}>
            <div className="evidence-meta">
              {item.chapter_id} / {item.paragraph_id}
            </div>
            <p>{item.text}</p>
          </article>
        ))}
        {result && result.evidence.length === 0 ? <p className="muted-text">暂无可展示证据。</p> : null}
      </section>
    </div>
  );
}

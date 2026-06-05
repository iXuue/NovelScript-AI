import type { ChapterDraft } from "../types";

type Props = {
  chapters: ChapterDraft[];
  confirmed: boolean;
  loading: boolean;
  onConfirm: () => void;
};

function LegacyChapterConfirmation({ chapters, confirmed, loading, onConfirm }: Props) {
  if (chapters.length === 0) {
    return null;
  }

  return (
    <section className="chapter-confirmation" aria-label="章节确认">
      <div className="panel-title-row">
        <div>
          <h2>章节确认</h2>
          <p>确认后系统会使用稳定段落编号继续生成下游产物。</p>
        </div>
        <button className="primary-button" disabled={confirmed || loading} type="button" onClick={onConfirm}>
          {confirmed ? "已确认" : loading ? "确认中" : "确认章节"}
        </button>
      </div>
      <div className="chapter-table" role="table" aria-label="检测到的章节">
        <div className="table-row table-head" role="row">
          <span role="columnheader">序号</span>
          <span role="columnheader">章节</span>
          <span role="columnheader">段落数</span>
        </div>
        {chapters.map((chapter) => (
          <div className="table-row" role="row" key={chapter.chapter_id}>
            <span role="cell">{chapter.order}</span>
            <span role="cell">{chapter.title}</span>
            <span role="cell">{chapter.paragraph_count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ChapterConfirmation({ chapters, confirmed, loading, onConfirm }: Props) {
  if (chapters.length === 0) {
    return null;
  }

  return (
    <section className="figma-chapter-confirmation" aria-label="章节确认">
      <div className="figma-result-title-row">
        <div>
          <h2>章节确认</h2>
          <p>确认后系统会使用稳定段落编号继续生成下游产物。</p>
        </div>
        <button className="figma-primary" disabled={confirmed || loading} type="button" onClick={onConfirm}>
          {confirmed ? "已确认" : loading ? "确认中" : "确认章节"}
        </button>
      </div>
      <div className="figma-chapter-table" role="table" aria-label="检测到的章节">
        <div className="figma-table-row head" role="row">
          <span role="columnheader">序号</span>
          <span role="columnheader">章节</span>
          <span role="columnheader">段落数</span>
        </div>
        {chapters.map((chapter) => (
          <div className="figma-table-row" role="row" key={chapter.chapter_id}>
            <span role="cell">{chapter.order}</span>
            <span role="cell">{chapter.title}</span>
            <span role="cell">{chapter.paragraph_count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

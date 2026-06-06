import type { ExportFormat, ExportResult } from "../types";

type Props = {
  disabled: boolean;
  loading: boolean;
  latestExport: ExportResult | null;
  onExport: (format: ExportFormat) => void;
};

const formats: Array<{ value: ExportFormat; label: string }> = [
  { value: "yaml", label: "YAML" },
  { value: "markdown", label: "Markdown" },
  { value: "docx", label: "DOCX" },
  { value: "pdf", label: "PDF" },
  { value: "txt", label: "TXT" },
  { value: "clean_json", label: "Clean JSON" },
];

export function ExportMenu({ disabled, loading, latestExport, onExport }: Props) {
  return (
    <div className="export-menu">
      <select aria-label="导出格式" disabled={disabled || loading} id="export-format" defaultValue="yaml">
        {formats.map((format) => (
          <option key={format.value} value={format.value}>
            {format.label}
          </option>
        ))}
      </select>
      <button
        className="ghost-button"
        disabled={disabled || loading}
        type="button"
        onClick={() => {
          const select = document.getElementById("export-format") as HTMLSelectElement | null;
          onExport((select?.value ?? "yaml") as ExportFormat);
        }}
      >
        {loading ? "导出中" : "导出"}
      </button>
      {latestExport ? <span className="export-result">已生成：{latestExport.format}</span> : null}
    </div>
  );
}

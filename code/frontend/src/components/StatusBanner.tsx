type Props = {
  mode: "live" | "demo";
  message: string | null;
  error: string | null;
};

export function StatusBanner({ mode, message, error }: Props) {
  if (!message && !error && mode === "live") {
    return null;
  }

  return (
    <div className={error ? "status-banner error" : "status-banner"} role={error ? "alert" : "status"}>
      <span className="status-dot" aria-hidden="true" />
      <span>
        {error ? error : message}
        {!error && mode === "demo" ? "后端未连接时，界面会使用本地演示数据保持可操作。" : null}
      </span>
    </div>
  );
}


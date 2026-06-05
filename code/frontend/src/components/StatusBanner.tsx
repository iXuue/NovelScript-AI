type Props = {
  mode: "live" | "demo";
  message: string | null;
  error: string | null;
};

export function StatusBanner({ message, error }: Props) {
  if (!message && !error) {
    return null;
  }

  return (
    <div className={error ? "status-banner error" : "status-banner"} role={error ? "alert" : "status"}>
      <span className="status-dot" aria-hidden="true" />
      <span>
        {error ? error : message}
      </span>
    </div>
  );
}

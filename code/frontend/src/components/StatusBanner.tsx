type Props = {
  mode: "live" | "demo";
  message: string | null;
  error: string | null;
};

export function StatusBanner({ error }: Props) {
  if (!error) {
    return null;
  }

  return (
    <div className="status-banner error" role="alert">
      <span className="status-dot" aria-hidden="true" />
      <span>{error}</span>
    </div>
  );
}

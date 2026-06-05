type Props = {
  yaml: string;
};

export function YamlPreview({ yaml }: Props) {
  return (
    <pre className="yaml-preview" aria-label="YAML 只读预览">
      <code>{yaml}</code>
    </pre>
  );
}


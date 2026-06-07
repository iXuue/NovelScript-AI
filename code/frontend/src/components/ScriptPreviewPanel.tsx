import type { ScriptContentBlock, ScriptCurrentForUi } from "../types";

type Props = {
  script: ScriptCurrentForUi;
  onEvidenceClick: (contentBlockId: string) => void;
};

const blockTypeLabels: Record<string, string> = {
  action: "动作",
  character: "角色",
  description: "描述",
  dialogue: "对白",
  narration: "旁白",
  note: "注释",
  parenthetical: "表演提示",
  shot: "镜头",
  sound: "声音",
  transition: "转场",
  voiceover: "画外音"
};

function blockLabel(block: ScriptContentBlock): string {
  return blockTypeLabels[block.block_type] ?? block.block_type;
}

function hasEvidence(block: ScriptContentBlock): boolean {
  return (block.source_evidence_ids?.length ?? 0) > 0 || (block.source_paragraph_ids?.length ?? 0) > 0;
}

function yamlScalar(value: string | null | undefined): string {
  if (!value?.trim()) {
    return "待定";
  }
  return value.replace(/\r?\n/g, "\n    ");
}

function yamlList(values: string[] | null | undefined, indent: string): string {
  if (!values?.length) {
    return `${indent}- 待定`;
  }
  return values.map((value) => `${indent}- ${yamlScalar(value)}`).join("\n");
}

function blockYaml(block: ScriptContentBlock): string {
  const lines = [
    `    - 类型: ${blockLabel(block)}`,
    `      标识: ${block.content_block_id}`,
    `      标签: ${yamlScalar(block.display_label)}`,
    `      说话人: ${yamlScalar(block.speaker)}`,
    `      表演指示: ${yamlScalar(block.parenthetical)}`,
    `      文本: ${yamlScalar(block.text)}`
  ];
  return lines.join("\n");
}

export function ScriptPreviewPanel({ script, onEvidenceClick }: Props) {
  const scenes = script.scenes ?? [];
  const contentBlocks = script.content_blocks ?? [];
  const generatedAt = script.generated_at ? new Date(script.generated_at).toLocaleString() : "生成时间待定";
  const blocksByScene = contentBlocks.reduce<Record<string, ScriptContentBlock[]>>((groups, block) => {
    groups[block.scene_id] = [...(groups[block.scene_id] ?? []), block];
    return groups;
  }, {});

  return (
    <div className="figma-script-preview">
      <div className="figma-script-meta" aria-label="剧本状态">
        <span>{script.status === "current" ? "当前版本" : script.status}</span>
        <span>{generatedAt}</span>
      </div>

      <div className="figma-script-scenes">
        {scenes.map((scene) => {
          const blocks = blocksByScene[scene.scene_id] ?? [];
          const sceneYamlText = [
            `场景编号: ${scene.scene_id}`,
            `标题: ${yamlScalar(scene.title)}`,
            "来源章节:",
            yamlList(scene.source_chapter_ids, "  "),
            `场景信息: ${yamlScalar(scene.scene_info)}`,
            "出场人物:",
            yamlList(scene.characters, "  "),
            `场景目的: ${yamlScalar(scene.scene_purpose)}`,
            `核心冲突: ${yamlScalar(scene.core_conflict)}`,
            "内容块:"
          ].join("\n");

          return (
            <article className="figma-script-scene" key={scene.scene_id}>
              <header className="figma-script-scene-header">
                <span>{scene.scene_id}</span>
                <div>
                  <h4>{scene.title}</h4>
                  <p>{scene.scene_info}</p>
                </div>
              </header>

              <pre className="figma-script-yaml">{sceneYamlText}</pre>

              <div className="figma-script-yaml-blocks">
                {blocks.length > 0 ? (
                  blocks.map((block) => (
                    <section className="figma-script-yaml-block" key={block.content_block_id}>
                      <pre className="figma-script-yaml figma-script-yaml-content-block">{blockYaml(block)}</pre>
                      {hasEvidence(block) ? (
                        <button className="figma-evidence-link" type="button" onClick={() => onEvidenceClick(block.content_block_id)}>
                          来源段落
                        </button>
                      ) : null}
                    </section>
                  ))
                ) : (
                  <pre className="figma-script-yaml figma-script-yaml-content-block">  - 暂无内容块</pre>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

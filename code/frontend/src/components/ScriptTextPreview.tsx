import type { ScriptContentBlock, ScriptCurrentForUi } from "../types";

type Props = {
  script: ScriptCurrentForUi | null;
};

const BLOCK_TYPE_LABELS: Record<string, string> = {
  action: "动作",
  narration: "旁白",
  transition: "转场",
  note: "备注",
  parenthetical: "表演提示",
  voiceover: "画外音",
  description: "描述",
  sound: "声音",
  character: "人物",
  shot: "镜头"
};

export function ScriptTextPreview({ script }: Props) {
  if (!script || script.content_blocks.length === 0) {
    return (
      <div className="script-text-preview script-text-preview-empty" aria-label="剧本文本预览">
        暂无可读剧本文本。
      </div>
    );
  }

  const blocksByScene = script.content_blocks.reduce<Record<string, ScriptContentBlock[]>>((groups, block) => {
    groups[block.scene_id] = [...(groups[block.scene_id] ?? []), block];
    return groups;
  }, {});

  return (
    <div className="script-text-preview" aria-label="剧本文本预览">
      {script.scenes.map((scene) => (
        <article className="script-text-scene" key={scene.scene_id}>
          <header className="script-text-scene-header">
            <h4>
              {scene.scene_id} {scene.title}
            </h4>
            <p>{scene.scene_info}</p>
            <dl>
              <div>
                <dt>人物</dt>
                <dd>{scene.characters.join("、") || "待定"}</dd>
              </div>
              <div>
                <dt>冲突</dt>
                <dd>{scene.core_conflict}</dd>
              </div>
            </dl>
          </header>
          <div className="script-text-blocks">
            {(blocksByScene[scene.scene_id] ?? []).map((block) => (
              <ScriptBlockView block={block} key={block.content_block_id} />
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function ScriptBlockView({ block }: { block: ScriptContentBlock }) {
  const text = block.text?.trim();
  if (!text) return null;

  if (block.block_type === "dialogue") {
    return (
      <div className="script-text-block script-text-dialogue">
        <strong>{block.speaker || "未指定角色"}</strong>
        <p>{text}</p>
      </div>
    );
  }

  const label = BLOCK_TYPE_LABELS[block.block_type] ?? block.block_type;
  return (
    <div className="script-text-block">
      <span>{label}</span>
      <p>{text}</p>
    </div>
  );
}

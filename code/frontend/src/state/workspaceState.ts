import type {
  ChapterDraft,
  ConversationMessage,
  EvidenceLookupResult,
  ProjectSummary,
  ScenePlan,
  ScriptCurrentForUi,
  ScriptPreview
} from "../types";

export function nowIso(): string {
  return new Date().toISOString();
}

export function createDemoProject(name = "新项目"): ProjectSummary {
  return {
    project_id: `proj_demo_${Date.now()}`,
    name,
    stage: "empty",
    primary_conversation_id: `conv_demo_${Date.now()}`,
    active_session_id: `sess_demo_${Date.now()}`,
    created_at: nowIso(),
    updated_at: nowIso()
  };
}

export function detectDemoChapters(text: string): ChapterDraft[] {
  const matches = [...text.matchAll(/(?:^|\n)#?\s*((?:第[一二三四五六七八九十百千万0-9]+章|Chapter\s+\d+)[^\n]*)/gi)];
  const titles = matches.map((match) => match[1].trim()).filter(Boolean);
  const normalized = titles.length >= 1 ? titles : ["第一章", "第二章", "第三章"];
  return normalized.slice(0, 5).map((title, index) => ({
    chapter_id: `CH${String(index + 1).padStart(3, "0")}`,
    title,
    order: index + 1,
    paragraph_count: index === 0 ? 3 : 2
  }));
}

export function createDemoScenePlan(chapters: ChapterDraft[]): ScenePlan {
  const source = chapters.length > 0 ? chapters : detectDemoChapters("");
  return {
    scene_plan_id: `sp_demo_${Date.now()}`,
    status: "current",
    confirmed: false,
    scenes: source.map((chapter, index) => ({
      scene_id: `S${String(index + 1).padStart(3, "0")}`,
      order: index + 1,
      title: chapter.title.replace(/^第.+?章\s*/, "") || chapter.title,
      source_chapter_ids: [chapter.chapter_id],
      source_evidence_ids: [],
      source_paragraph_ids: [`${chapter.chapter_id}_P001`],
      interior_exterior: "内景",
      location: "待定地点",
      time: "待定时间",
      characters: index === 0 ? ["主要角色"] : ["主要角色", "关联角色"],
      must_cover_plot: [],
      must_keep_dialogue: [],
      must_keep_visual_elements: [],
      must_keep_foreshadowing: [],
      scene_function: index === 0 ? "建立开场信息与人物动机" : "推进人物关系与核心冲突",
      core_conflict: index === 0 ? "主要角色是否采取行动" : "角色之间的目标是否发生冲突",
      adaptation_note: "保留原文章节核心信息，压缩为可拍摄场景。"
    }))
  };
}

export function createDemoScript(projectName: string, scenePlan: ScenePlan): {
  preview: ScriptPreview;
  scriptForUi: ScriptCurrentForUi;
  evidence: Record<string, EvidenceLookupResult>;
} {
  const scenes = scenePlan.scenes.map((scene) => ({
    scene_id: scene.scene_id,
    title: scene.title,
    source_chapter_ids: scene.source_chapter_ids,
    scene_info: `${scene.interior_exterior} / ${scene.location} / ${scene.time}`,
    characters: scene.characters,
    scene_purpose: scene.scene_function,
    core_conflict: scene.core_conflict,
  }));

  const contentBlocks = scenePlan.scenes.flatMap((scene, sceneIndex) => {
    const blockBase = sceneIndex * 3;
    const sourceParagraphIds = scene.source_paragraph_ids;
    return [
      {
        content_block_id: `CB${String(blockBase + 1).padStart(3, "0")}`,
        scene_id: scene.scene_id,
        block_type: "action" as const,
        display_label: `${scene.scene_id} 动作 1`,
        text: `${scene.location}里，${scene.characters[0] ?? "主要角色"}停下脚步，周围的目光压过来。`,
        speaker: null,
        source_evidence_ids: [],
        source_paragraph_ids: sourceParagraphIds,
      },
      {
        content_block_id: `CB${String(blockBase + 2).padStart(3, "0")}`,
        scene_id: scene.scene_id,
        block_type: "dialogue" as const,
        display_label: `${scene.scene_id} 对白 1`,
        text: "这件事不会就这样结束。",
        speaker: scene.characters[0] ?? "主要角色",
        source_evidence_ids: [],
        source_paragraph_ids: sourceParagraphIds,
      },
      {
        content_block_id: `CB${String(blockBase + 3).padStart(3, "0")}`,
        scene_id: scene.scene_id,
        block_type: "transition" as const,
        display_label: `${scene.scene_id} 转场 1`,
        text: "切至下一处关键地点。",
        speaker: null,
        source_evidence_ids: [],
        source_paragraph_ids: sourceParagraphIds,
      },
    ];
  });

  const yamlScenes = scenePlan.scenes
    .map(
      (scene) => `  - scene_id: ${scene.scene_id}
    title: ${scene.title}
    scene_info: ${scene.interior_exterior} / ${scene.location ?? "待定"} / ${scene.time ?? "待定"}
    characters: [${scene.characters.join(", ")}]
    scene_purpose: ${scene.scene_function}
    core_conflict: ${scene.core_conflict}
    content_blocks:
      - type: action
        text: ${scene.location}里，${scene.characters[0] ?? "主要角色"}停下脚步，周围的目光压过来。
      - type: dialogue
        speaker: ${scene.characters[0] ?? "主要角色"}
        text: 这件事不会就这样结束。
      - type: transition
        text: 切至下一处关键地点。`
    )
    .join("\n");

  const yaml = `title: ${projectName}
characters:
  - name: 主要角色
    role: 主角
scenes:
${yamlScenes}
`;

  const evidence = Object.fromEntries(
    contentBlocks.map((block, index) => {
      const scene = scenePlan.scenes[Math.floor(index / 3)];
      const fallbackParagraphId = `${scene.source_chapter_ids[0]}_P001`;
      return [
        block.content_block_id,
        {
          content_block_id: block.content_block_id,
          evidence: [
            {
              source_evidence_id: null,
              source_paragraph_id: block.source_paragraph_ids[0],
              chapter_id: scene.source_chapter_ids[0],
              paragraph_id: block.source_paragraph_ids[0] ?? fallbackParagraphId,
              paragraph_ids: [block.source_paragraph_ids[0] ?? fallbackParagraphId],
              text: block.text ?? "剧本内容来自场景计划。"
            }
          ]
        }
      ] as const;
    })
  );

  return {
    preview: {
      script_version_id: `script_demo_${Date.now()}`,
      yaml,
      status: "current",
      generated_at: nowIso()
    },
    scriptForUi: {
      script_version_id: `script_demo_${Date.now()}`,
      status: "current",
      generated_at: nowIso(),
      scenes,
      content_blocks: contentBlocks
    },
    evidence
  };
}

export function createLocalMessage(
  project: ProjectSummary,
  content: string,
  role: "user" | "assistant" = "user"
): ConversationMessage {
  return {
    message_id: `msg_demo_${Date.now()}`,
    conversation_id: project.primary_conversation_id,
    role,
    content,
    created_at: nowIso()
  };
}

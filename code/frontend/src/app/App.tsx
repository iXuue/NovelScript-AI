import { useMemo, useState } from "react";

import { ConversationPane } from "../components/ConversationPane";
import { ProjectSidebar } from "../components/ProjectSidebar";
import { ResultPane } from "../components/ResultPane";
import { demoProject } from "../state/projectStore";
import type { ConversationMessage, ScenePlan, ScriptCurrentForUi, StyleSource } from "../types";

type ViewMode = "conversation" | "scene-plan" | "script";

type AppProps = {
  initialYaml?: string;
};

export default function App({ initialYaml }: AppProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>(initialYaml ? "script" : "conversation");
  const [styleSource, setStyleSource] = useState<StyleSource | null>(null);
  const [hasNovelUpload, setHasNovelUpload] = useState(false);

  const scenePlan: ScenePlan = useMemo(
    () => ({
      scene_plan_id: "sp_demo",
      status: "current",
      confirmed: false,
      scenes: [
        {
          scene_id: "S001",
          order: 1,
          title: "雨夜归来",
          source_chapter_ids: ["CH001"],
          source_evidence_ids: ["EV001"],
          location: "旧宅门口",
          time: "夜",
          characters: ["林雨"],
          scene_function: "建立人物回归",
          core_conflict: "林雨是否进入旧宅",
          adaptation_note: "保留雨夜视觉元素"
        }
      ]
    }),
    []
  );

  const scriptForUi: ScriptCurrentForUi | null = initialYaml
    ? {
        script_version_id: "script_demo",
        status: "current",
        generated_at: new Date("2026-06-05T13:20:00+08:00").toISOString(),
        content_blocks: [
          {
            content_block_id: "CB001",
            scene_id: "S001",
            block_type: "action",
            display_label: "S001 动作 1",
            source_evidence_ids: ["EV001"]
          }
        ]
      }
    : null;

  const messages: ConversationMessage[] = [];
  const statusText = hasNovelUpload ? "正在等待生成场景" : "正在等待用户上传";

  return (
    <div className="workspace">
      <header className="topbar">
        <div>
          <div className="product-name">NovelScript AI</div>
          <div className="project-name">当前项目：{demoProject.name}</div>
        </div>
        <button className="ghost-button" type="button">
          导出
        </button>
      </header>
      <div className="workspace-grid">
        <ProjectSidebar
          collapsed={sidebarCollapsed}
          currentProject={demoProject}
          projects={[demoProject]}
          scenePlan={scenePlan}
          viewMode={viewMode}
          onNewProject={() => undefined}
          onSelectView={setViewMode}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        />
        <ConversationPane
          hasNovelUpload={hasNovelUpload}
          messages={messages}
          progress={null}
          selectedStyle={styleSource}
          styleLocked={scenePlan.confirmed}
          onNovelSelected={() => setHasNovelUpload(true)}
          onStyleChange={setStyleSource}
        />
        <ResultPane
          projectId={demoProject.project_id}
          scenePlan={scenePlan}
          scriptForUi={scriptForUi}
          statusText={statusText}
          viewMode={viewMode}
          yaml={initialYaml ?? null}
        />
      </div>
    </div>
  );
}


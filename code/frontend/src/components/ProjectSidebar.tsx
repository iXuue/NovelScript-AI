import type { ProjectSummary, ScenePlan, UiMode } from "../types";

type ViewMode = "conversation" | "scene-plan" | "script";

type Props = {
  collapsed: boolean;
  projects: ProjectSummary[];
  currentProject: ProjectSummary;
  error: string | null;
  loading: boolean;
  mode: UiMode;
  newProjectName: string;
  scenePlan: ScenePlan | null;
  statusMessage: string | null;
  viewMode: ViewMode;
  onToggleCollapsed: () => void;
  onNewProjectNameChange: (name: string) => void;
  onSelectView: (view: ViewMode) => void;
  onSelectProject: (projectId: string) => void;
  onNewProject: () => void;
};

function LegacyProjectSidebar({
  collapsed,
  currentProject,
  projects,
  scenePlan,
  viewMode,
  onNewProject,
  onSelectProject,
  onSelectView,
  onToggleCollapsed
}: Props) {
  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"} aria-label="项目导航">
      <button className="ghost-button" type="button" onClick={onToggleCollapsed}>
        {collapsed ? "展开" : "收起"}
      </button>
      {!collapsed ? (
        <>
          <button className="primary-button full" type="button" onClick={onNewProject}>
            新建项目
          </button>
          <div className="section-label">项目</div>
          <div className="current-project-name">{currentProject.name}</div>
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.project_id}
                className={project.project_id === currentProject.project_id ? "nav-item active" : "nav-item"}
                type="button"
                onClick={() => onSelectProject(project.project_id)}
              >
                {project.name}
              </button>
            ))}
          </div>
          <nav className="project-nav" aria-label="当前项目产物">
            <button
              className={viewMode === "conversation" ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => onSelectView("conversation")}
            >
              对话记录
            </button>
            <button
              className={viewMode === "scene-plan" ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => onSelectView("scene-plan")}
            >
              Scene Plan
            </button>
            <div className="scene-list">
              {scenePlan?.scenes.map((scene) => (
                <button className="scene-link" key={scene.scene_id} type="button" onClick={() => onSelectView("scene-plan")}>
                  {scene.scene_id} {scene.title}
                </button>
              ))}
            </div>
            <button
              className={viewMode === "script" ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => onSelectView("script")}
            >
              生成剧本
            </button>
          </nav>
        </>
      ) : null}
    </aside>
  );
}

const stageLabels: Record<ProjectSummary["stage"], string> = {
  empty: "未开始",
  uploaded: "已上传",
  chapters_pending: "待确认章节",
  chapters_confirmed: "章节已确认",
  style_selected: "风格已选择",
  scene_plan_draft: "Scene Plan 草稿",
  scene_plan_confirmed: "Scene Plan 已确认",
  script_generating: "剧本生成中",
  script_ready: "剧本已生成",
  failed: "失败"
};

export function ProjectSidebar({
  collapsed,
  currentProject,
  error,
  loading,
  mode,
  newProjectName,
  projects,
  scenePlan,
  statusMessage,
  viewMode,
  onNewProject,
  onNewProjectNameChange,
  onSelectProject,
  onSelectView,
  onToggleCollapsed
}: Props) {
  const statusText = error ?? statusMessage ?? (mode === "demo" ? "演示模式" : "后端已连接");

  return (
    <aside className={collapsed ? "figma-sidebar collapsed" : "figma-sidebar"} aria-label="项目导航">
      <div className="figma-brand-row">
        {!collapsed ? (
          <div>
            <div className="figma-brand-title">NovelScript AI</div>
            <div className="figma-brand-subtitle">小说转剧本工作台</div>
          </div>
        ) : null}
        <button className="figma-icon-button" type="button" onClick={onToggleCollapsed}>
          {collapsed ? "展开" : "收起"}
        </button>
      </div>

      {!collapsed ? (
        <>
          <section className="figma-new-project" aria-label="新建项目">
            <label>
              <span>项目名</span>
              <input
                aria-label="新项目名称"
                value={newProjectName}
                onChange={(event) => onNewProjectNameChange(event.target.value)}
              />
            </label>
            <button className="figma-primary full" disabled={loading} type="button" onClick={onNewProject}>
              新建项目
            </button>
          </section>

          <section className={error ? "figma-status error" : "figma-status"} role={error ? "alert" : "status"}>
            <span className="figma-status-dot" aria-hidden="true" />
            <span>{statusText}</span>
          </section>

          <section className="figma-sidebar-section">
            <div className="figma-section-label">项目</div>
            <button className="figma-current-project" type="button" onClick={() => onSelectProject(currentProject.project_id)}>
              <span>{currentProject.name}</span>
              <small>{stageLabels[currentProject.stage]}</small>
            </button>
            <div className="figma-project-list">
              {projects.map((project) => (
                <button
                  key={project.project_id}
                  className={project.project_id === currentProject.project_id ? "figma-nav-item active" : "figma-nav-item"}
                  type="button"
                  onClick={() => onSelectProject(project.project_id)}
                >
                  <span>{project.name}</span>
                  <small>{stageLabels[project.stage]}</small>
                </button>
              ))}
            </div>
          </section>

          <nav className="figma-sidebar-section" aria-label="当前项目产物">
            <div className="figma-section-label">工作区</div>
            <button
              className={viewMode === "conversation" ? "figma-nav-item active" : "figma-nav-item"}
              type="button"
              onClick={() => onSelectView("conversation")}
            >
              对话记录
            </button>
            <button
              className={viewMode === "scene-plan" ? "figma-nav-item active" : "figma-nav-item"}
              type="button"
              onClick={() => onSelectView("scene-plan")}
            >
              Scene Plan
            </button>
            <div className="figma-scene-list">
              {scenePlan?.scenes.map((scene) => (
                <button className="figma-scene-link" key={scene.scene_id} type="button" onClick={() => onSelectView("scene-plan")}>
                  <span>{scene.scene_id}</span>
                  <span>{scene.title}</span>
                </button>
              ))}
            </div>
            <button
              className={viewMode === "script" ? "figma-nav-item active" : "figma-nav-item"}
              type="button"
              onClick={() => onSelectView("script")}
            >
              生成剧本
            </button>
          </nav>
        </>
      ) : null}
    </aside>
  );
}

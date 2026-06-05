import type { ProjectSummary, ScenePlan } from "../types";

type ViewMode = "conversation" | "scene-plan" | "script";

type Props = {
  collapsed: boolean;
  projects: ProjectSummary[];
  currentProject: ProjectSummary;
  scenePlan: ScenePlan | null;
  viewMode: ViewMode;
  onToggleCollapsed: () => void;
  onSelectView: (view: ViewMode) => void;
  onNewProject: () => void;
};

export function ProjectSidebar({
  collapsed,
  currentProject,
  projects,
  scenePlan,
  viewMode,
  onNewProject,
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
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.project_id}
                className={project.project_id === currentProject.project_id ? "nav-item active" : "nav-item"}
                type="button"
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


import { useState, type FormEvent } from "react";

import type { AuthUser, ProjectSummary, ScenePlan, UiMode } from "../types";

type ViewMode = "conversation" | "scene-plan" | "script";

type Props = {
  collapsed: boolean;
  projects: ProjectSummary[];
  currentProject: ProjectSummary | null;
  authUser: AuthUser | null;
  error: string | null;
  loading: boolean;
  canCreateProject: boolean;
  mode: UiMode;
  newProjectName: string;
  scenePlan: ScenePlan | null;
  selectedSceneId: string | null;
  statusMessage: string | null;
  viewMode: ViewMode;
  onToggleCollapsed: () => void;
  onNewProjectNameChange: (name: string) => void;
  onSelectScene: (sceneId: string) => void;
  onSelectView: (view: ViewMode) => void;
  onSelectProject: (projectId: string) => void;
  onNewProject: () => void;
  onLogout: () => void;
};

function DisclosureChevron({ open }: { open: boolean }) {
  return <span className={open ? "figma-disclosure-chevron open" : "figma-disclosure-chevron"} aria-hidden="true" />;
}

function LegacyProjectSidebar({
  collapsed,
  authUser,
  canCreateProject,
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
          {currentProject ? <div className="current-project-name">{currentProject.name}</div> : null}
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.project_id}
                className={project.project_id === currentProject?.project_id ? "nav-item active" : "nav-item"}
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
              场景计划
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

export function ProjectSidebar({
  collapsed,
  authUser,
  canCreateProject,
  currentProject,
  error,
  loading,
  mode,
  newProjectName,
  projects,
  scenePlan,
  selectedSceneId,
  statusMessage,
  viewMode,
  onNewProject,
  onNewProjectNameChange,
  onLogout,
  onSelectProject,
  onSelectScene,
  onSelectView,
  onToggleCollapsed
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [expandedProjectId, setExpandedProjectId] = useState<string | null>(null);
  const [scenePlanOpen, setScenePlanOpen] = useState(false);
  const hasScenePlanScenes = Boolean(scenePlan?.scenes.length);

  function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreateProject || loading) return;
    onNewProject();
    setCreateOpen(false);
  }

  function handleCreateCancel() {
    setCreateOpen(false);
    onNewProjectNameChange("");
  }

  return (
    <aside className={collapsed ? "figma-sidebar collapsed" : "figma-sidebar"} aria-label="项目导航">
      <div className="figma-brand-row">
        {!collapsed ? (
          <div>
            <div className="figma-brand-title">NovelScript AI</div>
          </div>
        ) : null}
        <button className="figma-icon-button" type="button" onClick={onToggleCollapsed}>
          {collapsed ? "展开" : "收起"}
        </button>
      </div>

      {!collapsed ? (
        <>
          {error ? (
            <section className="figma-status error" role="alert">
              <span className="figma-status-dot" aria-hidden="true" />
              <span>{error}</span>
            </section>
          ) : null}

          <section className="figma-sidebar-section">
            <div className="figma-section-row">
              <div className="figma-section-label">项目</div>
              <button
                aria-label="新建项目"
                className="figma-add-project-button"
                disabled={loading}
                type="button"
                onClick={() => setCreateOpen(true)}
              >
                +
              </button>
            </div>
            <div className="figma-project-list">
              {projects.length > 0 ? (
                projects.map((project) => (
                  <div className="figma-project-item" key={project.project_id}>
                    <button
                      className={project.project_id === currentProject?.project_id ? "figma-nav-item active" : "figma-nav-item"}
                      type="button"
                      onClick={() => {
                        onSelectProject(project.project_id);
                        setExpandedProjectId((value) => (value === project.project_id ? null : project.project_id));
                      }}
                    >
                      <span>{project.name}</span>
                      <DisclosureChevron open={expandedProjectId === project.project_id} />
                    </button>
                    {expandedProjectId === project.project_id ? (
                      <div className="figma-project-thread-preview">暂无对话</div>
                    ) : null}
                  </div>
                ))
              ) : null}
            </div>
          </section>

          {createOpen ? (
            <div className="figma-project-modal-scrim" role="presentation">
              <form
                aria-labelledby="project-create-title"
                aria-modal="true"
                className="figma-project-modal"
                role="dialog"
                onSubmit={handleCreateSubmit}
              >
                <header className="figma-project-modal-header">
                  <h2 id="project-create-title">为项目命名</h2>
                  <button aria-label="取消新建项目" className="figma-style-close" type="button" onClick={handleCreateCancel}>
                    ×
                  </button>
                </header>
                <label className="figma-project-name-field">
                  <span>项目名</span>
                  <input
                    autoFocus
                    aria-label="新项目名称"
                    placeholder="输入项目名"
                    value={newProjectName}
                    onChange={(event) => onNewProjectNameChange(event.target.value)}
                  />
                </label>
                <footer className="figma-project-modal-actions">
                  <button className="figma-secondary" type="button" onClick={handleCreateCancel}>
                    取消
                  </button>
                  <button className="figma-primary" disabled={loading || !canCreateProject} type="submit">
                    保存
                  </button>
                </footer>
              </form>
            </div>
          ) : null}

          <nav className="figma-sidebar-section" aria-label="当前项目产物">
            <div className="figma-section-label">工作区</div>
            <button
              aria-expanded={scenePlanOpen}
              className={viewMode === "scene-plan" && !selectedSceneId ? "figma-nav-item active disclosure" : "figma-nav-item disclosure"}
              type="button"
              onClick={() => {
                onSelectView("scene-plan");
                setScenePlanOpen((value) => !value);
              }}
            >
              <span>场景计划</span>
              <DisclosureChevron open={scenePlanOpen} />
            </button>
            {scenePlanOpen && hasScenePlanScenes ? (
              <div className="figma-scene-list">
                {scenePlan?.scenes.map((scene) => (
                  <button
                    className={selectedSceneId === scene.scene_id ? "figma-scene-link active" : "figma-scene-link"}
                    key={scene.scene_id}
                    type="button"
                    onClick={() => onSelectScene(scene.scene_id)}
                  >
                    <span>{scene.scene_id}</span>
                    <span>{scene.title}</span>
                  </button>
                ))}
              </div>
            ) : null}
            <button
              className={viewMode === "script" ? "figma-nav-item active" : "figma-nav-item"}
              type="button"
              onClick={() => onSelectView("script")}
            >
              生成剧本
            </button>
          </nav>

          {authUser ? (
            <section className="figma-workspace-account-panel" aria-label="用户登录信息">
              <div className="figma-workspace-account-copy">
                <span>当前账号</span>
                <strong>{authUser.login_id}</strong>
              </div>
              <div className="figma-workspace-account-actions">
                <button type="button" onClick={onLogout}>
                  退出登录
                </button>
                <button type="button" onClick={onLogout}>
                  切换账号
                </button>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </aside>
  );
}

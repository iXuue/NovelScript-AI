import { useCallback, useEffect, useMemo, useState } from "react";

import {
  confirmChapters,
  confirmScenePlan,
  createExport,
  createProject,
  generateScenePlan,
  generateScript,
  getActiveRun,
  getCurrentScriptForUi,
  getPrimaryMessages,
  getScenePlan,
  getStyleSource,
  getYamlPreview,
  listProjects,
  sendMessage,
  setStyleSource,
  uploadNovel,
  uploadStyleReferenceScript
} from "../api/client";
import { ConversationPane } from "../components/ConversationPane";
import { ExportMenu } from "../components/ExportMenu";
import { ProjectSidebar } from "../components/ProjectSidebar";
import { ResultPane } from "../components/ResultPane";
import { StatusBanner } from "../components/StatusBanner";
import {
  createDemoProject,
  createDemoScenePlan,
  createDemoScript,
  createLocalMessage,
  detectDemoChapters,
  nowIso
} from "../state/workspaceState";
import type {
  AgentProgress,
  ChapterDraft,
  ConversationMessage,
  EvidenceLookupResult,
  ExportFormat,
  ExportResult,
  ProjectSummary,
  ScenePlan,
  ScriptCurrentForUi,
  ScriptPreview,
  StyleSource,
  UiMode,
  WorkspaceView
} from "../types";

type AppProps = {
  initialYaml?: string;
};

const initialProject = createDemoProject();

function updateProject(project: ProjectSummary, patch: Partial<ProjectSummary>): ProjectSummary {
  return { ...project, ...patch, updated_at: nowIso() };
}

export default function App({ initialYaml }: AppProps) {
  const [mode, setMode] = useState<UiMode>("demo");
  const [projects, setProjects] = useState<ProjectSummary[]>([initialProject]);
  const [activeProjectId, setActiveProjectId] = useState(initialProject.project_id);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<WorkspaceView>(initialYaml ? "script" : "conversation");
  const [chapters, setChapters] = useState<ChapterDraft[]>([]);
  const [chaptersConfirmed, setChaptersConfirmed] = useState(false);
  const [styleSourceValue, setStyleSourceValue] = useState<StyleSource | null>(null);
  const [styleLocked, setStyleLocked] = useState(false);
  const [scenePlan, setScenePlan] = useState<ScenePlan | null>(null);
  const [scenePlanConfirmed, setScenePlanConfirmed] = useState(false);
  const [scriptPreview, setScriptPreview] = useState<ScriptPreview | null>(
    initialYaml
      ? {
          script_version_id: "script_initial",
          yaml: initialYaml,
          status: "current",
          generated_at: nowIso()
        }
      : null
  );
  const [scriptForUi, setScriptForUi] = useState<ScriptCurrentForUi | null>(null);
  const [fallbackEvidence, setFallbackEvidence] = useState<Record<string, EvidenceLookupResult>>({});
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [progress, setProgress] = useState<AgentProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>("正在连接后端服务。");
  const [error, setError] = useState<string | null>(null);
  const [failedStage, setFailedStage] = useState<string | null>(null);
  const [latestExport, setLatestExport] = useState<ExportResult | null>(null);
  const [uploadedNovelName, setUploadedNovelName] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("新项目");

  const activeProject = useMemo(
    () => projects.find((project) => project.project_id === activeProjectId) ?? projects[0],
    [activeProjectId, projects]
  );

  const setActiveProjectPatch = useCallback(
    (patch: Partial<ProjectSummary>) => {
      if (!activeProject) return;
      setProjects((items) =>
        items.map((project) => (project.project_id === activeProject.project_id ? updateProject(project, patch) : project))
      );
    },
    [activeProject]
  );

  useEffect(() => {
    let mounted = true;
    listProjects()
      .then((items) => {
        if (!mounted) return;
        if (items.length > 0) {
          setMode("live");
          setProjects(items);
          setActiveProjectId(items[0].project_id);
          setStatusMessage("已连接后端服务。");
        } else {
          setMode("live");
          setStatusMessage("后端已连接。可以新建项目开始。");
        }
      })
      .catch(() => {
        if (!mounted) return;
        setMode("demo");
        setStatusMessage("后端未连接。");
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!activeProject || mode !== "live") return;
    let mounted = true;
    getPrimaryMessages(activeProject.project_id)
      .then((payload) => {
        if (mounted) setMessages(payload.messages);
      })
      .catch(() => undefined);
    getStyleSource(activeProject.project_id)
      .then((payload) => {
        if (!mounted) return;
        setStyleSourceValue(payload.style_source);
        setStyleLocked(payload.style_locked);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, [activeProject, mode]);

  useEffect(() => {
    if (!activeProject || mode !== "live") return;
    const timer = window.setInterval(() => {
      getActiveRun(activeProject.project_id)
        .then(setProgress)
        .catch(() => undefined);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [activeProject, mode]);

  function resetArtifactsForProject() {
    setChapters([]);
    setChaptersConfirmed(false);
    setStyleSourceValue(null);
    setStyleLocked(false);
    setScenePlan(null);
    setScenePlanConfirmed(false);
    setScriptPreview(null);
    setScriptForUi(null);
    setFallbackEvidence({});
    setMessages([]);
    setLatestExport(null);
    setUploadedNovelName(null);
    setFailedStage(null);
    setError(null);
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setLoading(true);
    setLoadingLabel(label);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
      setLoadingLabel(null);
    }
  }

  function createLocalProject(name: string) {
    const project = createDemoProject(name);
    setProjects((items) => [project, ...items]);
    setActiveProjectId(project.project_id);
    resetArtifactsForProject();
    setStatusMessage("后端未连接。");
  }

  function handleNewProject() {
    const trimmedName = newProjectName.trim();
    const name = trimmedName && trimmedName !== "新项目" ? trimmedName : `新项目 ${projects.length + 1}`;
    void runAction("正在新建项目", async () => {
      if (mode === "live") {
        try {
          const project = await createProject(name);
          setProjects((items) => [project, ...items]);
          setActiveProjectId(project.project_id);
          resetArtifactsForProject();
          return;
        } catch {
          setMode("demo");
        }
      }
      createLocalProject(name);
    });
  }

  function handleStyleSourceChange(source: StyleSource | null) {
    if (!activeProject || !source) {
      setStyleSourceValue(source);
      return;
    }
    setStyleSourceValue(source);
    void runAction("正在保存风格设计", async () => {
      if (mode === "live") {
        try {
          const response = await setStyleSource(activeProject.project_id, source);
          setStyleSourceValue(response.style_source);
          setActiveProjectPatch({ stage: response.stage });
          return;
        } catch {
          setMode("demo");
        }
      }
      setActiveProjectPatch({ stage: "style_selected" });
    });
  }

  function handleStyleReferenceSelected(file: File) {
    if (!activeProject) return;
    void runAction("正在上传风格参考", async () => {
      if (mode === "live") {
        try {
          const uploaded = await uploadStyleReferenceScript(activeProject.project_id, file);
          const source: StyleSource = { kind: "reference_scripts", reference_file_ids: [uploaded.file_id] };
          const response = await setStyleSource(activeProject.project_id, source);
          setStyleSourceValue(response.style_source);
          setActiveProjectPatch({ stage: response.stage });
          return;
        } catch {
          setMode("demo");
        }
      }
      const source: StyleSource = { kind: "reference_scripts", reference_file_ids: [`demo_${file.name}`] };
      setStyleSourceValue(source);
      setActiveProjectPatch({ stage: "style_selected" });
    });
  }

  function handleNovelSelected(file: File) {
    if (!activeProject) return;
    setUploadedNovelName(file.name);
    void runAction("正在解析上传文件", async () => {
      if (mode === "live") {
        try {
          const response = await uploadNovel(activeProject.project_id, file);
          setChapters(response.detected_chapters);
          setChaptersConfirmed(false);
          setActiveProjectPatch({ stage: response.stage });
          setViewMode("conversation");
          return;
        } catch {
          setMode("demo");
        }
      }
      const text = await file.text().catch(() => "");
      const detected = detectDemoChapters(text);
      setChapters(detected);
      setChaptersConfirmed(false);
      setActiveProjectPatch({ stage: "chapters_pending" });
    });
  }

  function handleConfirmChapters() {
    if (!activeProject) return;
    void runAction("正在确认章节", async () => {
      const chapterIds = chapters.map((chapter) => chapter.chapter_id);
      if (mode === "live") {
        try {
          const response = await confirmChapters(activeProject.project_id, chapterIds);
          setChaptersConfirmed(true);
          setActiveProjectPatch({ stage: response.stage });
          return;
        } catch {
          setMode("demo");
        }
      }
      setChaptersConfirmed(true);
      setActiveProjectPatch({ stage: "chapters_confirmed" });
    });
  }

  function handleGenerateScenePlan() {
    if (!activeProject) return;
    void runAction("正在生成 Scene Plan", async () => {
      if (mode === "live") {
        try {
          await generateScenePlan(activeProject.project_id);
          const current = await getScenePlan(activeProject.project_id);
          setScenePlan(current);
          setScenePlanConfirmed(current.confirmed);
          setActiveProjectPatch({ stage: "scene_plan_draft" });
          setViewMode("scene-plan");
          return;
        } catch {
          setMode("demo");
        }
      }
      const current = createDemoScenePlan(chapters);
      setScenePlan(current);
      setScenePlanConfirmed(false);
      setActiveProjectPatch({ stage: "scene_plan_draft" });
      setViewMode("scene-plan");
    });
  }

  function handleConfirmScenePlan() {
    if (!activeProject || !scenePlan) return;
    void runAction("正在确认 Scene Plan", async () => {
      if (mode === "live") {
        try {
          const response = await confirmScenePlan(activeProject.project_id, "button");
          setStyleLocked(response.style_locked);
          setScenePlan({ ...scenePlan, confirmed: true });
          setScenePlanConfirmed(true);
          setActiveProjectPatch({ stage: "scene_plan_confirmed" });
          return;
        } catch {
          setMode("demo");
        }
      }
      setStyleLocked(true);
      setScenePlan({ ...scenePlan, confirmed: true });
      setScenePlanConfirmed(true);
      setActiveProjectPatch({ stage: "scene_plan_confirmed" });
    });
  }

  function handleGenerateScript() {
    if (!activeProject || !scenePlan) return;
    void runAction("正在逐场生成剧本", async () => {
      if (mode === "live") {
        try {
          await generateScript(activeProject.project_id);
          const preview = await getYamlPreview(activeProject.project_id);
          const ui = await getCurrentScriptForUi(activeProject.project_id);
          setScriptPreview(preview);
          setScriptForUi(ui);
          setActiveProjectPatch({ stage: "script_ready" });
          setViewMode("script");
          return;
        } catch {
          setMode("demo");
        }
      }
      const generated = createDemoScript(activeProject.name, scenePlan);
      setScriptPreview(generated.preview);
      setScriptForUi(generated.scriptForUi);
      setFallbackEvidence(generated.evidence);
      setActiveProjectPatch({ stage: "script_ready" });
      setViewMode("script");
    });
  }

  function handleSubmitMessage(content: string) {
    if (!activeProject) return;
    const local = createLocalMessage(activeProject, content);
    setMessages((items) => [...items, local]);
    void sendMessage(activeProject.project_id, content).catch(() => undefined);
  }

  function handleExport(format: ExportFormat) {
    if (!activeProject || !scriptPreview) return;
    void runAction("正在导出", async () => {
      if (mode === "live") {
        try {
          const exported = await createExport(activeProject.project_id, format);
          setLatestExport(exported);
          return;
        } catch {
          setMode("demo");
        }
      }
      setLatestExport({
        export_id: `exp_demo_${Date.now()}`,
        format,
        status: "succeeded",
        download_url: "#"
      });
    });
  }

  const hasNovelUpload = chapters.length > 0 || Boolean(uploadedNovelName);
  const statusText = useMemo(() => {
    if (!hasNovelUpload) return "正在等待用户上传";
    if (!scenePlan) return "正在等待生成场景";
    if (!scenePlanConfirmed) return "正在等待用户确认 Scene Plan";
    if (!scriptPreview) return "正在等待生成剧本";
    return "剧本已生成";
  }, [hasNovelUpload, scenePlan, scenePlanConfirmed, scriptPreview]);

  if (!activeProject) {
    return (
      <div className="workspace">
        <div className="empty-start">
          <h1>NovelScript AI</h1>
          <p>请新建项目开始。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="figma-workspace">
      <header className="topbar">
        <div className="brand-block">
          <div className="product-name">NovelScript AI</div>
          <div className="project-name">当前项目：{activeProject.name}</div>
        </div>
        <div className="topbar-actions">
          <label className="new-project-control">
            <span>项目名</span>
            <input
              aria-label="新项目名称"
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
            />
          </label>
          <button className="primary-button" disabled={loading} type="button" onClick={handleNewProject}>
            新建项目
          </button>
          <ExportMenu disabled={!scriptPreview} latestExport={latestExport} loading={loading} onExport={handleExport} />
        </div>
      </header>
      <StatusBanner error={error} message={statusMessage} mode={mode} />
      <div className="workspace-grid">
        <ProjectSidebar
          collapsed={sidebarCollapsed}
          currentProject={activeProject}
          error={error}
          loading={loading}
          mode={mode}
          newProjectName={newProjectName}
          projects={projects}
          scenePlan={scenePlan}
          statusMessage={statusMessage}
          viewMode={viewMode}
          onNewProject={handleNewProject}
          onNewProjectNameChange={setNewProjectName}
          onSelectProject={(projectId) => {
            setActiveProjectId(projectId);
            resetArtifactsForProject();
          }}
          onSelectView={setViewMode}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        />
        <ConversationPane
          activeLabel={loadingLabel}
          chapters={chapters}
          chaptersConfirmed={chaptersConfirmed}
          error={error}
          hasNovelUpload={hasNovelUpload}
          loading={loading}
          messages={messages}
          mode={mode}
          progress={progress}
          projectName={activeProject.name}
          selectedStyle={styleSourceValue}
          statusMessage={statusMessage}
          styleLocked={styleLocked}
          uploadedNovelName={uploadedNovelName}
          onConfirmChapters={handleConfirmChapters}
          onNovelSelected={handleNovelSelected}
          onStyleChange={handleStyleSourceChange}
          onStyleReferenceSelected={handleStyleReferenceSelected}
          onSubmitMessage={handleSubmitMessage}
        />
        <ResultPane
          failedStage={failedStage}
          fallbackEvidence={fallbackEvidence}
          latestExport={latestExport}
          loading={loading}
          projectId={activeProject.project_id}
          scenePlan={scenePlan}
          scenePlanConfirmed={scenePlanConfirmed}
          scriptForUi={scriptForUi}
          statusText={statusText}
          viewMode={viewMode}
          yaml={scriptPreview?.yaml ?? null}
          onConfirmScenePlan={handleConfirmScenePlan}
          onExport={handleExport}
          onGenerateScenePlan={handleGenerateScenePlan}
          onGenerateScript={handleGenerateScript}
        />
      </div>
    </div>
  );
}

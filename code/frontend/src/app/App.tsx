import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties, MouseEvent as ReactMouseEvent } from "react";

import {
  ApiRequestError,
  confirmChapters,
  confirmFeedbackPlan,
  confirmScenePlan,
  createFeedbackPlan,
  createExport,
  createProject,
  downloadExportFile,
  deleteProject,
  generateScenePlan,
  generateScript,
  getActiveRun,
  getCurrentUser,
  getProjectProgress,
  getCurrentScriptForUi,
  getPendingChapters,
  getPrimaryMessages,
  getScenePlan,
  getStyleSource,
  getYamlPreview,
  listProjects,
  loginUser,
  logoutUser,
  repairScenePlan,
  repairScriptScene,
  registerUser,
  sendMessage,
  setAuthToken,
  setStyleSource,
  uploadNovel,
  uploadStyleReferenceScript
} from "../api/client";
import { AuthPane } from "../components/AuthPane";
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
  AuthSession,
  AuthUser,
  ChapterDraft,
  ConversationMessage,
  EvidenceLookupResult,
  ExportFormat,
  ExportResult,
  FeedbackPlan,
  FeedbackTarget,
  ProjectStage,
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

type FeedbackChapterOption = {
  chapterId: string;
  label: string;
};

type FeedbackTargetMode = "script" | "chapters";

const AUTH_TOKEN_STORAGE_KEY = "novelscript_auth_token";
const TEST_MODE_STORAGE_KEY = "novelscript_test_mode";
const TEST_MODE_USER: AuthUser = {
  user_id: "user_local_test",
  login_id: "local-test",
  created_at: "2026-06-06T00:00:00.000Z"
};
const RESULT_PANEL_DEFAULT_WIDTH = 420;
const RESULT_PANEL_MIN_WIDTH = 320;
const RESULT_PANEL_MAX_WIDTH = 720;
const WORKSPACE_RESIZER_WIDTH = 10;
const WORKSPACE_MIN_CONVERSATION_WIDTH = 360;
const WORKSPACE_SIDEBAR_WIDTH = 248;
const WORKSPACE_COLLAPSED_SIDEBAR_WIDTH = 72;

function clampResultPanelWidth(width: number, sidebarCollapsed: boolean): number {
  if (typeof window === "undefined") {
    return Math.min(RESULT_PANEL_MAX_WIDTH, Math.max(RESULT_PANEL_MIN_WIDTH, width));
  }

  const sidebarWidth = sidebarCollapsed ? WORKSPACE_COLLAPSED_SIDEBAR_WIDTH : WORKSPACE_SIDEBAR_WIDTH;
  const availableMax = window.innerWidth - sidebarWidth - WORKSPACE_MIN_CONVERSATION_WIDTH - WORKSPACE_RESIZER_WIDTH;
  const maxWidth = Math.max(RESULT_PANEL_MIN_WIDTH, Math.min(RESULT_PANEL_MAX_WIDTH, availableMax));
  return Math.min(maxWidth, Math.max(RESULT_PANEL_MIN_WIDTH, width));
}

function readStoredAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

function readLocalTestMode(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  const paramValue = params.get("testMode");
  if (paramValue === "1") {
    window.localStorage.setItem(TEST_MODE_STORAGE_KEY, "1");
    return true;
  }
  if (paramValue === "0") {
    window.localStorage.removeItem(TEST_MODE_STORAGE_KEY);
    return false;
  }
  return window.localStorage.getItem(TEST_MODE_STORAGE_KEY) === "1";
}

function updateProject(project: ProjectSummary, patch: Partial<ProjectSummary>): ProjectSummary {
  return { ...project, ...patch, updated_at: nowIso() };
}

function mergeConversationMessages(current: ConversationMessage[], incoming: Array<ConversationMessage | null | undefined>): ConversationMessage[] {
  const next = [...current];
  for (const message of incoming) {
    if (!message) continue;
    const index = next.findIndex((item) => item.message_id === message.message_id);
    if (index >= 0) {
      next[index] = message;
    } else {
      next.push(message);
    }
  }
  return next;
}

const HAS_UPLOAD_STAGES = new Set<ProjectStage>([
  "chapters_pending",
  "chapters_confirmed",
  "style_selected",
  "scene_plan_draft",
  "scene_plan_confirmed",
  "script_generating",
  "script_ready",
  "failed"
]);

const CHAPTER_CONFIRMED_STAGES = new Set<ProjectStage>([
  "chapters_confirmed",
  "style_selected",
  "scene_plan_draft",
  "scene_plan_confirmed",
  "script_generating",
  "script_ready"
]);

function isNotFound(err: unknown): boolean {
  return err instanceof ApiRequestError && err.status === 404;
}

function displayError(err: unknown): string {
  if (err instanceof ApiRequestError) {
    if (err.code === "invalid_credentials") {
      return "账号或密码错误；新用户请切换到注册。";
    }
    if (err.code === "login_id_exists") {
      return "账号已存在；请直接登录或换一个账号。";
    }
    if (err.code === "invalid_login_id") {
      return "账号需为 2-32 位字母、数字或下划线，不能包含中文、空格或其他符号。";
    }
    if (err.code === "invalid_password") {
      return "密码需为 6-128 位。";
    }
    return err.code ? `${err.message} (${err.code})` : err.message;
  }
  return err instanceof Error ? err.message : "操作失败";
}

async function optionalResource<T>(loader: () => Promise<T>): Promise<T | null> {
  try {
    return await loader();
  } catch (err) {
    if (isNotFound(err)) return null;
    throw err;
  }
}

function isApiErrorCode(error: unknown, code: string): boolean {
  return error instanceof ApiRequestError && error.code === code;
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
}

export default function App({ initialYaml }: AppProps) {
  const localTestMode = useMemo(() => readLocalTestMode(), []);
  const initialWorkspaceProject = useMemo(
    () => (initialYaml || localTestMode ? createDemoProject(localTestMode ? "本地测试项目" : undefined) : null),
    [initialYaml, localTestMode]
  );
  const initialProjects = initialWorkspaceProject ? [initialWorkspaceProject] : [];
  const [mode, setMode] = useState<UiMode>("demo");
  const [authUser, setAuthUser] = useState<AuthUser | null>(localTestMode ? TEST_MODE_USER : null);
  const [authTokenValue, setAuthTokenValue] = useState<string | null>(() => readStoredAuthToken());
  const [authChecking, setAuthChecking] = useState(!initialYaml && !localTestMode);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>(initialProjects);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(initialWorkspaceProject?.project_id ?? null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<WorkspaceView>(initialYaml ? "script" : "conversation");
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
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
  const [pendingFeedbackPlan, setPendingFeedbackPlan] = useState<FeedbackPlan | null>(null);
  const [feedbackTargetMode, setFeedbackTargetMode] = useState<FeedbackTargetMode>("script");
  const [selectedFeedbackChapterIds, setSelectedFeedbackChapterIds] = useState<string[]>([]);
  const [progress, setProgress] = useState<AgentProgress | null>(null);
  const [projectSteps, setProjectSteps] = useState<Array<{ step_type: string; status: string; summary: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>("正在连接后端服务。");
  const [error, setError] = useState<string | null>(null);
  const [failedStage, setFailedStage] = useState<string | null>(null);
  const [latestExport, setLatestExport] = useState<ExportResult | null>(null);
  const [uploadedNovelName, setUploadedNovelName] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [resultPanelWidth, setResultPanelWidth] = useState(RESULT_PANEL_DEFAULT_WIDTH);

  const activeProject = useMemo(
    () => (activeProjectId ? projects.find((project) => project.project_id === activeProjectId) ?? null : null),
    [activeProjectId, projects]
  );
  const canCreateProject = newProjectName.trim().length > 0;
  const workspaceStyle = {
    "--figma-result-panel-width": `${resultPanelWidth}px`
  } as CSSProperties;

  const handleResultPanelResizeStart = useCallback(
    (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      if (!Number.isFinite(event.clientX)) return;

      const startX = event.clientX;
      const startWidth = resultPanelWidth;
      document.body.classList.add("figma-resizing-result-panel");

      function handleMouseMove(moveEvent: MouseEvent) {
        if (!Number.isFinite(moveEvent.clientX)) return;
        const nextWidth = startWidth + startX - moveEvent.clientX;
        setResultPanelWidth(clampResultPanelWidth(nextWidth, sidebarCollapsed));
      }

      function handleMouseUp() {
        document.body.classList.remove("figma-resizing-result-panel");
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      }

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp, { once: true });
    },
    [resultPanelWidth, sidebarCollapsed]
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
    if (localTestMode) {
      setStatusMessage("本地测试模式：已绕过登录。");
    }
  }, [localTestMode]);

  useEffect(() => {
    if (initialYaml || localTestMode) return;
    if (!authTokenValue) {
      setAuthToken(null);
      setAuthChecking(false);
      return;
    }

    let mounted = true;
    setAuthToken(authTokenValue);
    setAuthChecking(true);
    getCurrentUser()
      .then((user) => {
        if (!mounted) return;
        setAuthUser(user);
        setAuthError(null);
        setAuthChecking(false);
      })
      .catch(() => {
        if (!mounted) return;
        setAuthToken(null);
        window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        setAuthTokenValue(null);
        setAuthUser(null);
        setAuthError("登录已过期，请重新登录。");
        setAuthChecking(false);
      });

    return () => {
      mounted = false;
    };
  }, [authTokenValue, initialYaml, localTestMode]);

  useEffect(() => {
    if (initialYaml || localTestMode || !authUser) return;
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
          setProjects([]);
          setActiveProjectId(null);
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
  }, [authUser, initialYaml, localTestMode]);

  useEffect(() => {
    if (!activeProject || mode !== "live") return;
    let mounted = true;
    loadProjectWorkspace(activeProject, () => mounted).catch((err) => {
      if (mounted) setError(displayError(err));
    });
    return () => {
      mounted = false;
    };
  }, [activeProjectId, mode]);

  useEffect(() => {
    if (!activeProject || mode !== "live") return;
    const timer = window.setInterval(() => {
      getActiveRun(activeProject.project_id)
        .then(setProgress)
        .catch(() => undefined);
      getProjectProgress(activeProject.project_id)
        .then((payload) => setProjectSteps(payload.steps))
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
    setSelectedSceneId(null);
    setScriptPreview(null);
    setScriptForUi(null);
    setFallbackEvidence({});
    setMessages([]);
    setPendingFeedbackPlan(null);
    setFeedbackTargetMode("script");
    setSelectedFeedbackChapterIds([]);
    setLatestExport(null);
    setUploadedNovelName(null);
    setFailedStage(null);
    setError(null);
  }

  function handleSelectView(view: WorkspaceView) {
    setViewMode(view);
    if (view !== "scene-plan" || selectedSceneId) {
      setSelectedSceneId(null);
    }
  }

  function handleSelectScene(sceneId: string) {
    setSelectedSceneId(sceneId);
    setViewMode("scene-plan");
  }

  function persistAuthSession(session: AuthSession) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, session.token);
    setAuthToken(session.token);
    setAuthUser(session.user);
    setAuthError(null);
    setStatusMessage("已登录。正在加载项目。");
  }

  function handleAuthSubmit(authMode: "login" | "register", loginId: string, password: string) {
    setAuthLoading(true);
    setAuthError(null);
    void (authMode === "login" ? loginUser(loginId, password) : registerUser(loginId, password))
      .then(persistAuthSession)
      .catch((err) => setAuthError(displayError(err)))
      .finally(() => setAuthLoading(false));
  }

  function handleLogout() {
    if (localTestMode) {
      window.localStorage.removeItem(TEST_MODE_STORAGE_KEY);
      window.location.href = window.location.pathname;
      return;
    }
    void logoutUser().catch(() => undefined);
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setAuthToken(null);
    setAuthTokenValue(null);
    setAuthUser(null);
    setMode("demo");
    setProjects([]);
    setActiveProjectId(null);
    resetArtifactsForProject();
    setStatusMessage("请登录后继续。");
  }

  async function loadProjectWorkspace(project: ProjectSummary, isCurrent: () => boolean = () => true) {
    resetArtifactsForProject();
    setChaptersConfirmed(CHAPTER_CONFIRMED_STAGES.has(project.stage));

    const [messagePayload, stylePayload, pendingPayload, currentScenePlan, currentYaml, currentScriptUi] =
      await Promise.all([
        optionalResource(() => getPrimaryMessages(project.project_id)),
        optionalResource(() => getStyleSource(project.project_id)),
        optionalResource(() => getPendingChapters(project.project_id)),
        optionalResource(() => getScenePlan(project.project_id)),
        optionalResource(() => getYamlPreview(project.project_id)),
        optionalResource(() => getCurrentScriptForUi(project.project_id))
      ]);

    if (!isCurrent()) return;

    setMessages(messagePayload?.messages ?? []);
    setStyleSourceValue(stylePayload?.style_source ?? null);
    setStyleLocked(stylePayload?.style_locked ?? false);
    setChapters(pendingPayload?.chapters ?? []);
    setChaptersConfirmed(CHAPTER_CONFIRMED_STAGES.has(project.stage) || Boolean(currentScenePlan?.confirmed));
    setScenePlan(currentScenePlan);
    setScenePlanConfirmed(Boolean(currentScenePlan?.confirmed));
    setScriptPreview(currentYaml);
    setScriptForUi(currentScriptUi);

    if (currentYaml) {
      setViewMode("script");
    } else if (currentScenePlan) {
      setViewMode("scene-plan");
    } else {
      setViewMode("conversation");
    }
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setLoading(true);
    setLoadingLabel(label);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(displayError(err));
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

  function handleDeleteProjects(projectIds: string[]) {
    void runAction("正在删除项目", async () => {
      for (const projectId of projectIds) {
        if (mode === "live") {
          await deleteProject(projectId).catch(() => undefined);
        }
      }
      const idSet = new Set(projectIds);
      setProjects((items) => items.filter((p) => !idSet.has(p.project_id)));
      if (activeProjectId && idSet.has(activeProjectId)) {
        setActiveProjectId(null);
        resetArtifactsForProject();
      }
    });
  }

  function handleNewProject() {
    const trimmedName = newProjectName.trim();
    if (!trimmedName) return;
    void runAction("正在新建项目", async () => {
      if (mode === "live") {
        const project = await createProject(trimmedName);
        setProjects((items) => [project, ...items]);
        setActiveProjectId(project.project_id);
        resetArtifactsForProject();
        setNewProjectName("");
        return;
      }
      createLocalProject(trimmedName);
      setNewProjectName("");
    });
  }

  function handleStyleSourceChange(source: StyleSource | null) {
    if (!activeProject || !source) {
      setStyleSourceValue(source);
      return;
    }
    if (mode !== "live") {
      setStyleSourceValue(source);
    }
    void runAction("正在保存风格设计", async () => {
      if (mode === "live") {
        const response = await setStyleSource(activeProject.project_id, source);
        setStyleSourceValue(response.style_source);
        setStyleLocked(response.style_locked);
        setActiveProjectPatch({ stage: response.stage });
        return;
      }
      setActiveProjectPatch({ stage: "style_selected" });
    });
  }

  function handleStyleReferenceSelected(file: File) {
    if (!activeProject) return;
    void runAction("正在上传风格参考", async () => {
      if (mode === "live") {
        const uploaded = await uploadStyleReferenceScript(activeProject.project_id, file);
        const source: StyleSource = { kind: "reference_scripts", reference_file_ids: [uploaded.file_id] };
        const response = await setStyleSource(activeProject.project_id, source);
        setStyleSourceValue(response.style_source);
        setStyleLocked(response.style_locked);
        setActiveProjectPatch({ stage: response.stage });
        return;
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
        const response = await uploadNovel(activeProject.project_id, file);
        setChapters(response.detected_chapters);
        setChaptersConfirmed(false);
        setActiveProjectPatch({ stage: response.stage });
        setViewMode("conversation");
        return;
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
        const response = await confirmChapters(activeProject.project_id, chapterIds);
        setChaptersConfirmed(true);
        setActiveProjectPatch({ stage: response.stage });
        return;
      }
      setChaptersConfirmed(true);
      setActiveProjectPatch({ stage: "chapters_confirmed" });
    });
  }

  function handleGenerateScenePlan() {
    if (!activeProject) return;
    void runAction("正在生成场景规划", async () => {
      if (mode === "live") {
        await generateScenePlan(activeProject.project_id);
        const current = await getScenePlan(activeProject.project_id);
        setScenePlan(current);
        setScenePlanConfirmed(current.confirmed);
        setActiveProjectPatch({ stage: "scene_plan_draft" });
        setViewMode("scene-plan");
        return;
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
    void runAction("正在确认场景规划", async () => {
      if (mode === "live") {
        try {
          const response = await confirmScenePlan(activeProject.project_id, "button");
          setStyleLocked(response.style_locked);
          setScenePlan({ ...scenePlan, confirmed: true });
          setScenePlanConfirmed(true);
          setActiveProjectPatch({ stage: "scene_plan_confirmed" });
          return;
        } catch (err) {
          if (isApiErrorCode(err, "scene_plan_validation_failed")) {
            const current = await getScenePlan(activeProject.project_id).catch(() => scenePlan);
            setScenePlan(current);
            setScenePlanConfirmed(false);
            setError("场景规划校验未通过，请先修复后再确认。");
            return;
          }
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
        } catch (err) {
          if (isApiErrorCode(err, "script_scene_validation_failed")) {
            const ui = await getCurrentScriptForUi(activeProject.project_id).catch(() => null);
            const preview = await getYamlPreview(activeProject.project_id).catch(() => null);
            if (ui) setScriptForUi(ui);
            if (preview) setScriptPreview(preview);
            setActiveProjectPatch({ stage: "script_generating" });
            setViewMode("script");
            setError("剧本场景校验未通过，请修复失败场景后继续。");
            return;
          }
          throw err;
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

  const feedbackChapterOptions = useMemo<FeedbackChapterOption[]>(() => {
    if (!scriptForUi) return [];
    const chapterIds = new Set<string>();
    for (const scene of scriptForUi.scenes) {
      for (const chapterId of scene.source_chapter_ids) {
        chapterIds.add(chapterId);
      }
    }
    return Array.from(chapterIds)
      .sort()
      .map((chapterId) => {
        const chapter = chapters.find((item) => item.chapter_id === chapterId);
        return {
          chapterId,
          label: chapter ? `剧本章节：第 ${chapter.order} 章 ${chapter.title}` : `剧本章节：${chapterId}`
        };
      });
  }, [chapters, scriptForUi]);

  useEffect(() => {
    if (!scriptForUi) {
      if (feedbackTargetMode !== "script") setFeedbackTargetMode("script");
      if (selectedFeedbackChapterIds.length > 0) setSelectedFeedbackChapterIds([]);
      return;
    }
    const availableChapterIds = new Set(feedbackChapterOptions.map((option) => option.chapterId));
    const filteredChapterIds = selectedFeedbackChapterIds.filter((chapterId) => availableChapterIds.has(chapterId));
    if (filteredChapterIds.length !== selectedFeedbackChapterIds.length) {
      setSelectedFeedbackChapterIds(filteredChapterIds);
    }
    if (feedbackTargetMode === "chapters" && filteredChapterIds.length === 0) {
      setFeedbackTargetMode("script");
    }
  }, [feedbackChapterOptions, feedbackTargetMode, scriptForUi, selectedFeedbackChapterIds]);

  function buildFeedbackTarget(): FeedbackTarget | null {
    if (scriptForUi) {
      if (feedbackTargetMode === "chapters" && selectedFeedbackChapterIds.length > 0) {
        return { type: "chapters", chapter_ids: selectedFeedbackChapterIds };
      }
      return { type: "script" };
    }
    if (scenePlan && !scenePlanConfirmed) {
      return { type: "scene_plan" };
    }
    return null;
  }

  function handleFeedbackTargetModeChange(mode: FeedbackTargetMode) {
    setFeedbackTargetMode(mode);
    if (mode === "script") {
      setSelectedFeedbackChapterIds([]);
    }
  }

  function handleFeedbackChapterToggle(chapterId: string, selected: boolean) {
    setSelectedFeedbackChapterIds((current) => {
      const next = selected
        ? Array.from(new Set([...current, chapterId]))
        : current.filter((item) => item !== chapterId);
      setFeedbackTargetMode(next.length > 0 ? "chapters" : "script");
      return next;
    });
  }

  function handleSubmitMessage(content: string) {
    if (!activeProject) return;
    const local = createLocalMessage(activeProject, content);
    setMessages((items) => [...items, local]);
    if (mode !== "live") return;
    void runAction("正在生成修改计划", async () => {
      const target = buildFeedbackTarget();
      if (target) {
        const plan = await createFeedbackPlan(activeProject.project_id, content, target);
        setPendingFeedbackPlan(plan);
        setMessages((items) => {
          const withPersistedUser = plan.message
            ? items.map((item) => (item.message_id === local.message_id ? plan.message! : item))
            : items;
          return mergeConversationMessages(withPersistedUser, [plan.assistant_message]);
        });
        return;
      }
      const saved = await sendMessage(activeProject.project_id, content);
      setMessages((items) => items.map((item) => (item.message_id === local.message_id ? saved : item)));
    });
  }

  function handleCancelFeedbackPlan() {
    setPendingFeedbackPlan(null);
  }

  function handleConfirmFeedbackPlan() {
    if (!activeProject || !pendingFeedbackPlan) return;
    const plan = pendingFeedbackPlan;
    void runAction("正在执行修改计划", async () => {
      const result = await confirmFeedbackPlan(activeProject.project_id, plan.feedback_plan_id);
      setPendingFeedbackPlan(null);
      if (result.assistant_message) {
        setMessages((items) => mergeConversationMessages(items, [result.assistant_message]));
      }
      const latestMessages = await getPrimaryMessages(activeProject.project_id).catch(() => null);
      if (latestMessages) setMessages(latestMessages.messages);
      if (plan.stage === "scene_plan") {
        const current = await getScenePlan(activeProject.project_id);
        setScenePlan(current);
        setScenePlanConfirmed(current.confirmed);
        setScriptPreview(null);
        setScriptForUi(null);
        setActiveProjectPatch({ stage: "scene_plan_draft" });
        setViewMode("scene-plan");
        return;
      }
      const preview = await getYamlPreview(activeProject.project_id);
      const ui = await getCurrentScriptForUi(activeProject.project_id);
      setScriptPreview(preview);
      setScriptForUi(ui);
      setActiveProjectPatch({ stage: "script_ready" });
      setViewMode("script");
    });
  }
  function handleExport(format: ExportFormat) {
    if (!activeProject || !scriptPreview) return;
    void runAction("正在导出", async () => {
      if (mode === "live") {
        const exported = await createExport(activeProject.project_id, format);
        const blob = await downloadExportFile(exported.download_url);
        setLatestExport(exported);
        triggerBrowserDownload(blob, exported.filename ?? `script.${format}`);
        return;
      }
      setLatestExport({
        export_id: `exp_demo_${Date.now()}`,
        format,
        status: "succeeded",
        download_url: "#"
      });
    });
  }

  function handleRepairScenePlan() {
    if (!activeProject) return;
    void runAction("正在修复场景规划", async () => {
      if (mode === "live") {
        try {
          const repaired = await repairScenePlan(activeProject.project_id);
          setScenePlan(repaired);
          setScenePlanConfirmed(repaired.confirmed);
          setActiveProjectPatch({ stage: "scene_plan_draft" });
          setViewMode("scene-plan");
          return;
        } catch (err) {
          if (isApiErrorCode(err, "repair_attempts_exceeded")) {
            setError("修复次数已达到上限，请人工调整需求后重新生成。");
            return;
          }
          if (isApiErrorCode(err, "scene_plan_repair_not_required")) {
            setError("当前场景规划不需要修复。");
            return;
          }
          setMode("demo");
        }
      }
    });
  }

  function handleRepairScriptScene(sceneId: string) {
    if (!activeProject) return;
    void runAction("正在修复剧本场景", async () => {
      if (mode === "live") {
        try {
          await repairScriptScene(activeProject.project_id, sceneId);
          const ui = await getCurrentScriptForUi(activeProject.project_id);
          const preview = await getYamlPreview(activeProject.project_id);
          setScriptForUi(ui);
          setScriptPreview(preview);
          setActiveProjectPatch({ stage: ui.status === "current" ? "script_ready" : "script_generating" });
          setViewMode("script");
          return;
        } catch (err) {
          if (isApiErrorCode(err, "repair_attempts_exceeded")) {
            setError("该场修复次数已达到上限，请人工调整后重新生成。");
            return;
          }
          if (isApiErrorCode(err, "script_scene_repair_not_required")) {
            setError("当前场景不需要修复。");
            return;
          }
          setMode("demo");
        }
      }
    });
  }

  const hasNovelUpload =
    Boolean(activeProject) &&
    (chapters.length > 0 || Boolean(uploadedNovelName) || Boolean(activeProject && HAS_UPLOAD_STAGES.has(activeProject.stage)));
  const canGenerateScenePlan = chaptersConfirmed && Boolean(styleSourceValue) && !scenePlan;
  const canGenerateScript = Boolean(scenePlan && scenePlanConfirmed && !scriptPreview);
  useEffect(() => {
    if (!selectedSceneId) return;
    if (!scenePlan?.scenes.some((scene) => scene.scene_id === selectedSceneId)) {
      setSelectedSceneId(null);
    }
  }, [scenePlan, selectedSceneId]);

  const statusText = useMemo(() => {
    if (!activeProject) return "等待项目创建";
    if (!hasNovelUpload) return "正在等待用户上传";
    if (!scenePlan) return "正在等待生成场景";
    if (!scenePlanConfirmed) return "正在等待用户确认场景规划";
    if (!scriptPreview) return "正在等待生成剧本";
    return "剧本已生成";
  }, [activeProject, hasNovelUpload, scenePlan, scenePlanConfirmed, scriptPreview]);

  if (!initialYaml && (authChecking || !authUser)) {
    return (
      <div className="figma-workspace figma-auth-workspace">
        <AuthPane
          error={authError}
          loading={authLoading || authChecking}
          onModeChange={() => setAuthError(null)}
          onSubmit={handleAuthSubmit}
        />
      </div>
    );
  }

  return (
    <div className="figma-workspace" style={workspaceStyle}>
      <header className="topbar">
        <div className="brand-block">
          <div className="product-name">NovelScript AI</div>
          {activeProject ? <div className="project-name">当前项目：{activeProject.name}</div> : null}
        </div>
        <div className="topbar-actions">
          <label className="new-project-control">
            <span>项目名</span>
            <input
              aria-label="新项目名称"
              placeholder="输入项目名"
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
            />
          </label>
          <button className="primary-button" disabled={loading || !canCreateProject} type="button" onClick={handleNewProject}>
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
          authUser={authUser}
          loading={loading}
          canCreateProject={canCreateProject}
          mode={mode}
          newProjectName={newProjectName}
          projects={projects}
          scenePlan={scenePlan}
          selectedSceneId={selectedSceneId}
          statusMessage={statusMessage}
          viewMode={viewMode}
          onNewProject={handleNewProject}
          onNewProjectNameChange={setNewProjectName}
          onLogout={handleLogout}
          onSelectProject={(projectId) => {
            setActiveProjectId(projectId);
            resetArtifactsForProject();
          }}
          onDeleteProjects={handleDeleteProjects}
          onSelectScene={handleSelectScene}
          onSelectView={handleSelectView}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        />
        {activeProject ? (
          <ConversationPane
            canGenerateScenePlan={canGenerateScenePlan}
            canGenerateScript={canGenerateScript}
            chapters={chapters}
            chaptersConfirmed={chaptersConfirmed}
            error={error}
            hasNovelUpload={hasNovelUpload}
            loading={loading}
            activeLabel={loadingLabel}
            progress={progress}
            projectSteps={projectSteps}
            messages={messages}
            pendingFeedbackPlan={pendingFeedbackPlan}
            feedbackChapterOptions={feedbackChapterOptions}
            feedbackTargetMode={feedbackTargetMode}
            selectedFeedbackChapterIds={selectedFeedbackChapterIds}
            mode={mode}
            projectName={activeProject.name}
            selectedStyle={styleSourceValue}
            statusMessage={statusMessage}
            styleLocked={styleLocked}
            uploadedNovelName={uploadedNovelName}
            onConfirmChapters={handleConfirmChapters}
            onGenerateScenePlan={handleGenerateScenePlan}
            onGenerateScript={handleGenerateScript}
            onConfirmFeedbackPlan={handleConfirmFeedbackPlan}
            onCancelFeedbackPlan={handleCancelFeedbackPlan}
            onFeedbackTargetModeChange={handleFeedbackTargetModeChange}
            onFeedbackChapterToggle={handleFeedbackChapterToggle}
            onNovelSelected={handleNovelSelected}
            onStyleChange={handleStyleSourceChange}
            onStyleReferenceSelected={handleStyleReferenceSelected}
            onSubmitMessage={handleSubmitMessage}
          />
        ) : (
          <main className="figma-conversation" aria-label="对话区">
            <div className="figma-conversation-body figma-empty-workspace-body">
              <section className="figma-empty-prompt">
                <p>请先新建项目，然后上传小说并完成风格设计。</p>
              </section>
            </div>
          </main>
        )}
        <button
          aria-label="拖动调整剧本预览宽度"
          className="figma-result-resizer"
          type="button"
          onMouseDown={handleResultPanelResizeStart}
        />
        <ResultPane
          failedStage={failedStage}
          fallbackEvidence={fallbackEvidence}
          latestExport={latestExport}
          loading={loading}
          projectId={activeProject?.project_id ?? ""}
          scenePlan={scenePlan}
          scenePlanConfirmed={scenePlanConfirmed}
          selectedSceneId={selectedSceneId}
          scriptForUi={scriptForUi}
          statusText={statusText}
          viewMode={viewMode}
          yaml={scriptPreview?.yaml ?? null}
          onConfirmScenePlan={handleConfirmScenePlan}
          onExport={handleExport}
          onGenerateScenePlan={handleGenerateScenePlan}
          onGenerateScript={handleGenerateScript}
          onRepairScenePlan={handleRepairScenePlan}
          onRepairScriptScene={handleRepairScriptScene}
        />
      </div>
    </div>
  );
}

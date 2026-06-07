import type {
  AgentProgress,
  AuthSession,
  AuthUser,
  ChapterDraft,
  ConversationMessage,
  FeedbackPlan,
  FeedbackTarget,
  EvidenceLookupResult,
  ExportFormat,
  ExportResult,
  ProjectStage,
  ProjectSummary,
  RunStatus,
  ScenePlan,
  ScriptCurrentForUi,
  ScriptPreview,
  StyleSource
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
let authToken: string | null = null;

type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export function setAuthToken(token: string | null) {
  authToken = token;
}

export class ApiRequestError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(message: string, code: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export class ApiError extends ApiRequestError {
  constructor(status: number, body: ApiErrorBody = {}) {
    const error = body.error;
    super(error?.message ?? `Request failed: ${status}`, error?.code ?? "http_error", status, error?.details ?? {});
    this.name = "ApiError";
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...init?.headers
    }
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(response.status, payload);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function registerUser(loginId: string, password: string): Promise<AuthSession> {
  return requestJson<AuthSession>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ login_id: loginId, password })
  });
}

export async function loginUser(loginId: string, password: string): Promise<AuthSession> {
  return requestJson<AuthSession>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login_id: loginId, password })
  });
}

export async function getCurrentUser(): Promise<AuthUser> {
  return requestJson<AuthUser>("/auth/me");
}

export async function logoutUser(): Promise<void> {
  await requestJson<void>("/auth/logout", { method: "POST" });
}

export async function createProject(name: string): Promise<ProjectSummary> {
  return requestJson<ProjectSummary>("/projects", { method: "POST", body: JSON.stringify({ name }) });
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return requestJson<ProjectSummary[]>("/projects");
}

export async function getProject(projectId: string): Promise<ProjectSummary> {
  return requestJson<ProjectSummary>(`/projects/${projectId}`);
}

export async function getPendingChapters(projectId: string): Promise<{ chapters: ChapterDraft[] }> {
  return requestJson<{ chapters: ChapterDraft[] }>(`/projects/${projectId}/chapters/pending`);
}

export async function uploadNovel(
  projectId: string,
  file: File
): Promise<{ file_id: string; stage: ProjectStage; detected_chapters: ChapterDraft[] }> {
  const form = new FormData();
  form.append("file", file);
  return requestJson(`/projects/${projectId}/uploads`, { method: "POST", body: form });
}

export async function uploadStyleReferenceScript(
  projectId: string,
  file: File
): Promise<{ file_id: string; purpose: "style_reference"; filename: string; stage: ProjectStage }> {
  const form = new FormData();
  form.append("file", file);
  return requestJson(`/projects/${projectId}/style-reference-uploads`, { method: "POST", body: form });
}

export async function confirmChapters(
  projectId: string,
  chapterIds: string[]
): Promise<{ checkpoint_id: string; stage: ProjectStage }> {
  return requestJson(`/projects/${projectId}/chapters/confirm`, {
    method: "POST",
    body: JSON.stringify({ chapter_ids: chapterIds })
  });
}

export async function setStyleSource(
  projectId: string,
  styleSource: StyleSource
): Promise<{ style_source: StyleSource; style_locked: boolean; stage: ProjectStage }> {
  return requestJson(`/projects/${projectId}/style-source`, { method: "POST", body: JSON.stringify(styleSource) });
}

export async function clearStyleSource(projectId: string): Promise<void> {
  await requestJson<void>(`/projects/${projectId}/style-source`, { method: "DELETE" });
}

export async function getStyleSource(
  projectId: string
): Promise<{ project_id: string; style_source: StyleSource | null; style_locked: boolean }> {
  return requestJson(`/projects/${projectId}/style-source`);
}

export async function getRun(projectId: string, runId: string): Promise<AgentProgress> {
  return requestJson<AgentProgress>(`/projects/${projectId}/runs/${runId}`);
}

export async function generateScenePlan(
  projectId: string
): Promise<{ run_id: string; scene_plan_id: string; status: RunStatus }> {
  return requestJson(`/projects/${projectId}/scene-plan/generate`, { method: "POST" });
}

export async function getScenePlan(projectId: string): Promise<ScenePlan> {
  return requestJson<ScenePlan>(`/projects/${projectId}/scene-plan`);
}

export async function confirmScenePlan(
  projectId: string,
  source: "button" | "conversation",
  messageId?: string
): Promise<{ checkpoint_id: string; style_locked: boolean }> {
  return requestJson(`/projects/${projectId}/scene-plan/confirm`, {
    method: "POST",
    body: JSON.stringify({ confirmation_source: source, message_id: messageId ?? null })
  });
}

export async function repairScenePlan(projectId: string): Promise<ScenePlan> {
  return requestJson<ScenePlan>(`/projects/${projectId}/scene-plan/repair`, { method: "POST" });
}

export async function generateScript(projectId: string): Promise<{ run_id: string; status: RunStatus; stage: string }> {
  return requestJson(`/projects/${projectId}/scripts/generate`, { method: "POST" });
}

export async function getCurrentScriptForUi(projectId: string): Promise<ScriptCurrentForUi> {
  return requestJson<ScriptCurrentForUi>(`/projects/${projectId}/scripts/current`);
}

export async function getYamlPreview(projectId: string): Promise<ScriptPreview> {
  return requestJson<ScriptPreview>(`/projects/${projectId}/scripts/current/yaml-preview`);
}

export async function repairScriptScene(
  projectId: string,
  sceneId: string
): Promise<{ script_version_id: string; scene_id: string; validation: NonNullable<ScriptCurrentForUi["scenes"][number]["validation"]> }> {
  return requestJson(`/projects/${projectId}/scripts/scenes/${sceneId}/repair`, { method: "POST" });
}

export async function getPrimaryMessages(projectId: string): Promise<{
  conversation_id: string;
  messages: ConversationMessage[];
}> {
  return requestJson(`/projects/${projectId}/conversations/primary/messages`);
}

export async function sendMessage(
  projectId: string,
  content: string
): Promise<{ message_id: string; role: "user" | "assistant"; content: string; created_at: string }> {
  return requestJson(`/projects/${projectId}/conversations/primary/messages`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export async function modifyScript(
  projectId: string,
  message: string,
  target: { type: "scene" | "chapter" | "script"; scene_id?: string; chapter_id?: string }
): Promise<FeedbackPlan> {
  return requestJson(`/projects/${projectId}/conversations/primary/modify-script`, {
    method: "POST",
    body: JSON.stringify({ message, target })
  });
}

export async function createFeedbackPlan(projectId: string, message: string, target: FeedbackTarget): Promise<FeedbackPlan> {
  return requestJson(`/projects/${projectId}/conversations/primary/feedback-plan`, {
    method: "POST",
    body: JSON.stringify({ message, target })
  });
}

export async function confirmFeedbackPlan(
  projectId: string,
  feedbackPlanId: string
): Promise<{ run_id: string; status: RunStatus; stage: string; scene_plan_id?: string; script_version_id?: string }> {
  return requestJson(`/projects/${projectId}/conversations/primary/feedback-plan/${feedbackPlanId}/confirm`, {
    method: "POST"
  });
}

export async function getEvidenceByContentBlock(
  projectId: string,
  contentBlockId: string
): Promise<EvidenceLookupResult> {
  return requestJson<EvidenceLookupResult>(`/projects/${projectId}/evidence/by-content-block/${contentBlockId}`);
}

export async function createExport(
  projectId: string,
  format: ExportFormat
): Promise<ExportResult> {
  return requestJson(`/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ format }) });
}

export function getExportDownloadUrl(downloadUrl: string): string {
  if (downloadUrl.startsWith("http://") || downloadUrl.startsWith("https://")) {
    return downloadUrl;
  }
  return `${API_BASE_URL}${downloadUrl}`;
}

export async function getActiveRun(projectId: string): Promise<AgentProgress | null> {
  return requestJson<AgentProgress | null>(`/projects/${projectId}/runs/active`);
}

import type {
  AgentProgress,
  ChapterDraft,
  EvidenceLookupResult,
  ProjectStage,
  ProjectSummary,
  RunStatus,
  ScenePlan,
  ScriptCurrentForUi,
  ScriptPreview,
  StyleSource
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers
    }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload?.error?.message ?? `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function createProject(name: string): Promise<ProjectSummary> {
  return requestJson<ProjectSummary>("/projects", { method: "POST", body: JSON.stringify({ name }) });
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return requestJson<ProjectSummary[]>("/projects");
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

export async function generateScript(projectId: string): Promise<{ run_id: string; status: RunStatus; stage: string }> {
  return requestJson(`/projects/${projectId}/scripts/generate`, { method: "POST" });
}

export async function getCurrentScriptForUi(projectId: string): Promise<ScriptCurrentForUi> {
  return requestJson<ScriptCurrentForUi>(`/projects/${projectId}/scripts/current`);
}

export async function getYamlPreview(projectId: string): Promise<ScriptPreview> {
  return requestJson<ScriptPreview>(`/projects/${projectId}/scripts/current/yaml-preview`);
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
): Promise<{ run_id: string; status: RunStatus; stage: string }> {
  return requestJson(`/projects/${projectId}/conversations/primary/modify-script`, {
    method: "POST",
    body: JSON.stringify({ message, target })
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
  format: "yaml" | "markdown" | "docx" | "pdf" | "txt" | "clean_json"
): Promise<{ export_id: string; format: string; status: string; download_url: string }> {
  return requestJson(`/projects/${projectId}/exports`, { method: "POST", body: JSON.stringify({ format }) });
}

export async function getActiveRun(projectId: string): Promise<AgentProgress | null> {
  return requestJson<AgentProgress | null>(`/projects/${projectId}/runs/active`);
}


export type ArtifactStatus = "current" | "stale" | "historical" | "failed";
export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "budget_exceeded";
export type ProjectStage =
  | "empty"
  | "uploaded"
  | "chapters_pending"
  | "chapters_confirmed"
  | "style_selected"
  | "scene_plan_draft"
  | "scene_plan_confirmed"
  | "script_generating"
  | "script_ready"
  | "failed";

export type ProjectSummary = {
  project_id: string;
  name: string;
  stage: ProjectStage;
  primary_conversation_id: string;
  active_session_id: string;
  created_at: string;
  updated_at: string;
};

export type ChapterDraft = {
  chapter_id: string;
  title: string;
  order: number;
  paragraph_count: number;
};

export type StyleSource =
  | { kind: "builtin"; builtin_style: "realism" | "suspense" | "romance" | "comedy" | "short_drama" }
  | { kind: "custom_text"; style_text: string }
  | { kind: "reference_scripts"; reference_file_ids: string[] };

export type AgentProgress = {
  run_id: string;
  status: RunStatus;
  stage: string;
  current_step: string | null;
  steps: Array<{
    run_step_id: string;
    step_type: string;
    status: RunStatus;
    summary: string;
  }>;
  failure_message?: string | null;
};

export type ScenePlan = {
  scene_plan_id: string;
  status: ArtifactStatus;
  confirmed: boolean;
  scenes: Array<{
    scene_id: string;
    order: number;
    title: string;
    source_chapter_ids: string[];
    source_evidence_ids: string[];
    location?: string;
    time?: string;
    characters: string[];
    scene_function: string;
    core_conflict: string;
    adaptation_note: string;
  }>;
};

export type ScriptPreview = {
  script_version_id: string;
  yaml: string;
  status: ArtifactStatus;
  generated_at: string;
};

export type ScriptCurrentForUi = {
  script_version_id: string;
  status: ArtifactStatus;
  generated_at: string;
  content_blocks: Array<{
    content_block_id: string;
    scene_id: string;
    block_type: string;
    display_label: string;
    source_evidence_ids: string[];
  }>;
};

export type EvidenceLookupResult = {
  content_block_id: string;
  evidence: Array<{
    source_evidence_id: string;
    chapter_id: string;
    paragraph_id: string;
    text: string;
  }>;
};

export type ConversationMessage = {
  message_id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ExportFormat = "yaml" | "markdown" | "docx" | "pdf" | "txt" | "clean_json";

export type ExportResult = {
  export_id: string;
  format: string;
  status: string;
  download_url: string;
};

export type WorkspaceView = "conversation" | "scene-plan" | "script";

export type UiMode = "live" | "demo";

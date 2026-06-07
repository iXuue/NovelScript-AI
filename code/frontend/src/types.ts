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
  user_id?: string | null;
  name: string;
  stage: ProjectStage;
  primary_conversation_id: string;
  active_session_id: string;
  created_at: string;
  updated_at: string;
};

export type AuthUser = {
  user_id: string;
  login_id: string;
  created_at: string;
};

export type AuthSession = {
  token: string;
  user: AuthUser;
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
  validation?: ScenePlanValidation | null;
  scenes: Array<ScenePlanScene>;
};

export type ScenePlanValidation = {
  passed: boolean;
  issues: Array<{ code?: string; message: string }>;
  suggestions: string[];
  coverage: Record<string, string[]>;
  source: string;
  created_at: string;
};

export type ScenePlanScene = {
  scene_id: string;
  order: number;
  title: string;
  source_chapter_ids: string[];
  source_evidence_ids: string[];
  source_paragraph_ids: string[];
  interior_exterior: string;
  location: string;
  time: string;
  characters: string[];
  must_cover_plot: string[];
  must_keep_dialogue: string[];
  must_keep_visual_elements: string[];
  must_keep_foreshadowing: string[];
  scene_function: string;
  core_conflict: string;
  adaptation_note: string;
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
  scenes: Array<{
    scene_id: string;
    title: string;
    source_chapter_ids: string[];
    scene_info: string;
    characters: string[];
    scene_purpose: string;
    core_conflict: string;
    validation?: ScriptSceneValidation | null;
  }>;
  content_blocks: Array<ScriptContentBlock>;
};

export type ScriptSceneValidation = {
  passed: boolean;
  issues: Array<{ code?: string; message: string }>;
  suggestions: string[];
  coverage: Record<string, string[]>;
  source: string;
  created_at: string;
};

export type ScriptContentBlock = {
  content_block_id: string;
  scene_id: string;
  block_type: string;
  display_label: string;
  text?: string;
  speaker?: string | null;
  source_evidence_ids: string[];
  source_paragraph_ids: string[];
};

export type EvidenceLookupResult = {
  content_block_id: string;
  evidence: Array<{
    source_evidence_id?: string | null;
    source_paragraph_id?: string | null;
    chapter_id: string;
    paragraph_ids: string[];
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

export type FeedbackTarget =
  | { type: "scene_plan" }
  | { type: "script" }
  | { type: "chapter"; chapter_id: string }
  | { type: "scene"; scene_id: string };

export type FeedbackSourceRequest = {
  paragraph_ids: string[];
  scene_ids: string[];
  chapter_ids: string[];
  reason: string;
};

export type FeedbackModificationPlan = {
  intent: "regenerate_scene_plan" | "regenerate_script" | "modify_chapter" | "modify_scene";
  affected_scope: {
    chapter_ids: string[];
    scene_ids: string[];
  };
  modification_plan: string[];
  needs_source_text: boolean;
  source_requests: FeedbackSourceRequest[];
  user_confirmation_required: boolean;
};

export type FeedbackPlan = {
  feedback_plan_id: string;
  message_id?: string | null;
  run_id?: string | null;
  message?: ConversationMessage;
  stage: "scene_plan" | "script";
  target: FeedbackTarget;
  target_type: FeedbackTarget["type"];
  scope_id: string;
  artifact_fingerprint: string;
  user_feedback: string;
  modification_plan: FeedbackModificationPlan;
  source_requests: FeedbackSourceRequest[];
  cache_hit: boolean;
  created_at: string;
  updated_at: string;
};

export type ExportFormat = "yaml" | "markdown" | "docx" | "pdf" | "txt" | "clean_json";

export type ExportResult = {
  export_id: string;
  format: string;
  status: string;
  filename?: string;
  download_url: string;
};

export type WorkspaceView = "conversation" | "scene-plan" | "script";

export type UiMode = "live" | "demo";

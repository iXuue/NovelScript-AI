import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiError, listProjects, setAuthToken } from "../api/client";
import App from "../app/App";

const AUTH_TOKEN_STORAGE_KEY = "novelscript_auth_token";

const project = {
  project_id: "proj_001",
  name: "Interface project",
  stage: "style_selected",
  primary_conversation_id: "conv_001",
  active_session_id: "sess_001",
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z"
};

const scenePlan = {
  scene_plan_id: "sp_001",
  status: "current",
  confirmed: false,
  scenes: [
    {
      scene_id: "S001",
      order: 1,
      title: "Opening",
      source_chapter_ids: ["CH001"],
      source_evidence_ids: [],
      source_paragraph_ids: ["CH001_P001"],
      location: "Door",
      time: "Night",
      characters: ["Lin"],
      scene_function: "Open the story",
      core_conflict: "Whether to enter",
      adaptation_note: "Keep it concise"
    },
    {
      scene_id: "S002",
      order: 2,
      title: "Decision",
      source_chapter_ids: ["CH001"],
      source_evidence_ids: [],
      source_paragraph_ids: ["CH001_P002"],
      location: "Hall",
      time: "Night",
      characters: ["Lin", "Mo"],
      scene_function: "Force the choice",
      core_conflict: "Whether to trust Mo",
      adaptation_note: "Keep the reveal visual"
    }
  ]
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(body === null ? "null" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
  setAuthToken(null);
});

test("ApiError preserves backend status, code, and details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: "style_source_locked",
            message: "Style source is locked",
            details: { stage: "scene_plan_confirmed" }
          }
        },
        409
      )
    )
  );

  try {
    await listProjects();
    throw new Error("Expected listProjects to fail");
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 409,
      code: "style_source_locked",
      message: "Style source is locked",
      details: { stage: "scene_plan_confirmed" }
    });
  }
});

test("App triggers scene plan generation, confirmation, script generation, and evidence lookup", async () => {
  let scenePlanGenerated = false;
  let scenePlanConfirmed = false;
  let scriptGenerated = false;
  let feedbackPlanRequestBody: { message: string; target: unknown } | null = null;

  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "interface-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const path = url.pathname;

      if (method === "GET" && path === "/auth/me") {
        return jsonResponse({ user_id: "user_interface", login_id: "interface", created_at: "2026-06-06T00:00:00Z" });
      }
      if (method === "GET" && path === "/projects") return jsonResponse([project]);
      if (method === "GET" && path === "/projects/proj_001/conversations/primary/messages") {
        return jsonResponse({ conversation_id: "conv_001", messages: [] });
      }
      if (method === "GET" && path === "/projects/proj_001/style-source") {
        return jsonResponse({
          project_id: "proj_001",
          style_source: { kind: "builtin", builtin_style: "suspense" },
          style_locked: scenePlanConfirmed
        });
      }
      if (method === "GET" && path === "/projects/proj_001/chapters/pending") {
        return jsonResponse({ chapters: [] });
      }
      if (method === "GET" && path === "/projects/proj_001/scene-plan") {
        return scenePlanGenerated
          ? jsonResponse({ ...scenePlan, confirmed: scenePlanConfirmed })
          : jsonResponse({ error: { code: "scene_plan_not_found", message: "Scene Plan not found", details: {} } }, 404);
      }
      if (method === "POST" && path === "/projects/proj_001/scene-plan/generate") {
        scenePlanGenerated = true;
        return jsonResponse({ run_id: "run_scene", scene_plan_id: "sp_001", status: "running" });
      }
      if (method === "POST" && path === "/projects/proj_001/scene-plan/confirm") {
        scenePlanConfirmed = true;
        return jsonResponse({
          project_id: "proj_001",
          scene_plan_id: "sp_001",
          confirmed: true,
          style_locked: true,
          checkpoint_id: "chk_001"
        });
      }
      if (method === "POST" && path === "/projects/proj_001/scripts/generate") {
        scriptGenerated = true;
        return jsonResponse({ run_id: "run_script", status: "running", stage: "script_generating" });
      }
      if (method === "GET" && path === "/projects/proj_001/scripts/current/yaml-preview") {
        return scriptGenerated
          ? jsonResponse({
              script_version_id: "script_v001",
              status: "current",
              yaml: "title: Interface project\nscenes: []\n",
              generated_at: "2026-06-05T00:01:00Z"
            })
          : jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path === "/projects/proj_001/scripts/current") {
        return scriptGenerated
          ? jsonResponse({
              script_version_id: "script_v001",
              status: "current",
              generated_at: "2026-06-05T00:01:00Z",
              scenes: [
                {
                  scene_id: "S001",
                  title: "Opening",
                  source_chapter_ids: ["CH001"],
                  scene_info: "EXT / Door / Night",
                  characters: ["Lin"],
                  scene_purpose: "Open the story",
                  core_conflict: "Whether to enter",
                  validation: null
                }
              ],
              content_blocks: [
                {
                  content_block_id: "CB001",
                  scene_id: "S001",
                  block_type: "action",
                  display_label: "CB001 action",
                  text: "Lin stands at the door.",
                  speaker: null,
                  source_evidence_ids: [],
                  source_paragraph_ids: ["CH001_P001"]
                }
              ]
            })
          : jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path === "/projects/proj_001/evidence/by-content-block/CB001") {
        return jsonResponse({
          content_block_id: "CB001",
          evidence: [
            {
              source_evidence_id: null,
              source_paragraph_id: "CH001_P001",
              chapter_id: "CH001",
              paragraph_ids: ["CH001_P001"],
              text: "original evidence line"
            }
          ]
        });
      }
      if (method === "POST" && path === "/projects/proj_001/conversations/primary/feedback-plan") {
        feedbackPlanRequestBody = JSON.parse(String(init?.body ?? "{}"));
        return jsonResponse({
          feedback_plan_id: "fbp_001",
          message_id: "msg_feedback",
          run_id: "run_feedback",
          message: {
            message_id: "msg_feedback",
            conversation_id: "conv_001",
            role: "user",
            content: feedbackPlanRequestBody?.message ?? "",
            created_at: "2026-06-05T00:02:00Z"
          },
          stage: "script",
          target: feedbackPlanRequestBody?.target,
          target_type: "chapters",
          scope_id: "CH001",
          artifact_fingerprint: "script:test",
          user_feedback: feedbackPlanRequestBody?.message ?? "",
          modification_plan: {
            intent: "modify_chapter",
            affected_scope: { chapter_ids: ["CH001"], scene_ids: [] },
            modification_plan: ["Revise selected chapter."],
            needs_source_text: false,
            source_requests: [],
            user_confirmation_required: true
          },
          source_requests: [],
          cache_hit: false,
          created_at: "2026-06-05T00:02:00Z",
          updated_at: "2026-06-05T00:02:00Z"
        });
      }
      if (method === "GET" && path === "/projects/proj_001/runs/active") return jsonResponse(null);

      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  render(<App />);
  await screen.findByText("Interface project");
  await screen.findByText("悬疑/惊悚");
  expect(within(screen.getByLabelText("对话区")).getAllByRole("button", { name: "开始生成" }).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: "场景计划" }));
  fireEvent.click(await screen.findByRole("button", { name: "生成场景计划" }));
  const sidebar = screen.getByLabelText("项目导航");
  const resultPane = screen.getByLabelText("成果区");
  await within(resultPane).findByText("全部场景计划");
  expect(within(resultPane).getByText("Opening")).toBeInTheDocument();
  expect(within(resultPane).getByText("Decision")).toBeInTheDocument();

  fireEvent.click(within(sidebar).getByRole("button", { name: "S002 Decision" }));
  expect(within(resultPane).getByText("S002 Decision")).toBeInTheDocument();
  expect(within(resultPane).queryByText("Opening")).not.toBeInTheDocument();

  fireEvent.click(within(sidebar).getByRole("button", { name: "场景计划" }));
  expect(within(resultPane).getByText("全部场景计划")).toBeInTheDocument();
  expect(within(resultPane).getByText("Opening")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "确认场景计划" }));
  await waitFor(() => expect(scenePlanConfirmed).toBe(true));

  fireEvent.click(within(screen.getByLabelText("成果区")).getByRole("button", { name: "生成剧本" }));
  await screen.findByText(/title: Interface project/);
  await screen.findByText("Lin stands at the door.");
  await screen.findByText(/scenes:\s\[\]/);
  expect(screen.getByLabelText("全部章节")).toBeChecked();
  fireEvent.click(screen.getByLabelText("剧本章节：CH001"));
  fireEvent.change(screen.getByLabelText("对话输入"), { target: { value: "让第一章更克制" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() =>
    expect(feedbackPlanRequestBody).toMatchObject({
      message: "让第一章更克制",
      target: { type: "chapters", chapter_ids: ["CH001"] }
    })
  );
  await screen.findByText("修改计划待确认");

  fireEvent.click(screen.getByRole("button", { name: "CB001 action 来源证据" }));
  await screen.findByText("original evidence line");
});

test("script generation failure does not show demo script", async () => {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "interface-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const path = url.pathname;

      if (method === "GET" && path === "/auth/me") {
        return jsonResponse({ user_id: "user_interface", login_id: "interface", created_at: "2026-06-06T00:00:00Z" });
      }
      if (method === "GET" && path === "/projects") return jsonResponse([{ ...project, stage: "scene_plan_confirmed" }]);
      if (method === "GET" && path === "/projects/proj_001/conversations/primary/messages") {
        return jsonResponse({ conversation_id: "conv_001", messages: [] });
      }
      if (method === "GET" && path === "/projects/proj_001/style-source") {
        return jsonResponse({
          project_id: "proj_001",
          style_source: { kind: "builtin", builtin_style: "suspense" },
          style_locked: true
        });
      }
      if (method === "GET" && path === "/projects/proj_001/chapters/pending") {
        return jsonResponse({ chapters: [] });
      }
      if (method === "GET" && path === "/projects/proj_001/scene-plan") {
        return jsonResponse({ ...scenePlan, confirmed: true });
      }
      if (method === "GET" && path === "/projects/proj_001/scripts/current/yaml-preview") {
        return jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path === "/projects/proj_001/scripts/current") {
        return jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "POST" && path === "/projects/proj_001/scripts/generate") {
        return jsonResponse(
          {
            error: {
              code: "script_generation_failed",
              message: "Script generation failed",
              details: { reason: "script_generation references unknown paragraphs: ['CH001_P11']" }
            }
          },
          502
        );
      }
      if (method === "GET" && path === "/projects/proj_001/runs/active") return jsonResponse(null);

      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  render(<App />);
  await screen.findByLabelText("成果区");
  fireEvent.click(within(screen.getByLabelText("成果区")).getByRole("button", { name: "生成剧本" }));

  expect((await screen.findAllByText(/Script generation failed/)).length).toBeGreaterThan(0);
  expect(screen.queryByText(/主要角色停在关键地点/)).not.toBeInTheDocument();
});

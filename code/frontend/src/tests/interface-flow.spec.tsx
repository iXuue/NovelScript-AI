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
      source_evidence_ids: ["EV001"],
      location: "Door",
      time: "Night",
      characters: ["Lin"],
      scene_function: "Open the story",
      core_conflict: "Whether to enter",
      adaptation_note: "Keep it concise"
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
              content_blocks: [
                {
                  content_block_id: "CB001",
                  scene_id: "S001",
                  block_type: "action",
                  display_label: "CB001 action",
                  source_evidence_ids: ["EV001"]
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
              source_evidence_id: "EV001",
              chapter_id: "CH001",
              paragraph_ids: ["CH001_P001"],
              text: "original evidence line"
            }
          ]
        });
      }
      if (method === "GET" && path === "/projects/proj_001/runs/active") return jsonResponse(null);

      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  render(<App />);
  await screen.findByText("Interface project");
  await screen.findByText("悬疑/惊悚");

  fireEvent.click(screen.getByRole("button", { name: "场景计划" }));
  fireEvent.click(await screen.findByRole("button", { name: "生成场景计划" }));
  expect((await screen.findAllByText("Opening")).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: "确认场景计划" }));
  await waitFor(() => expect(scenePlanConfirmed).toBe(true));

  fireEvent.click(within(screen.getByLabelText("成果区")).getByRole("button", { name: "生成剧本" }));
  await screen.findByText(/title: Interface project/);
  await screen.findByText(/scenes:\s\[\]/);

  fireEvent.click(screen.getByRole("button", { name: "CB001 action 来源证据" }));
  await screen.findByText("original evidence line");
});

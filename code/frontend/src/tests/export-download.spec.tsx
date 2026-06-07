import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { downloadExportFile, setAuthToken } from "../api/client";
import App from "../app/App";
import { ExportMenu } from "../components/ExportMenu";

const AUTH_TOKEN_STORAGE_KEY = "novelscript_auth_token";

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

test("ExportMenu exposes DOC and PDF formats", () => {
  render(<ExportMenu disabled={false} latestExport={null} loading={false} onExport={() => undefined} />);

  expect(screen.getByRole("option", { name: "DOC" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "PDF" })).toBeInTheDocument();
});

test("downloadExportFile sends the bearer token", async () => {
  setAuthToken("download-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer download-token");
      return new Response("title: Script\n", { status: 200, headers: { "Content-Type": "application/x-yaml" } });
    })
  );

  const blob = await downloadExportFile("/projects/proj_001/exports/exp_001");

  expect(blob.size).toBeGreaterThan(0);
});

test("App downloads exports through authenticated fetch", async () => {
  const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:export")
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn()
  });

  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "workspace-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const path = url.pathname;

      if (method === "GET" && path === "/auth/me") {
        return jsonResponse({ user_id: "user_workspace", login_id: "workspace", created_at: "2026-06-06T00:00:00Z" });
      }
      if (method === "GET" && path === "/projects") {
        return jsonResponse([
          {
            project_id: "proj_ready",
            user_id: "user_workspace",
            name: "Ready project",
            stage: "script_ready",
            primary_conversation_id: "conv_ready",
            active_session_id: "sess_ready",
            created_at: "2026-06-06T00:00:00Z",
            updated_at: "2026-06-06T00:00:00Z"
          }
        ]);
      }
      if (method === "GET" && path === "/projects/proj_ready/conversations/primary/messages") {
        return jsonResponse({ conversation_id: "conv_ready", messages: [] });
      }
      if (method === "GET" && path === "/projects/proj_ready/style-source") {
        return jsonResponse({
          project_id: "proj_ready",
          style_source: { kind: "builtin", builtin_style: "suspense" },
          style_locked: true
        });
      }
      if (method === "GET" && path === "/projects/proj_ready/chapters/pending") {
        return jsonResponse({ chapters: [] });
      }
      if (method === "GET" && path === "/projects/proj_ready/scene-plan") {
        return jsonResponse({ error: { code: "scene_plan_not_found", message: "Scene Plan not found", details: {} } }, 404);
      }
      if (method === "GET" && path === "/projects/proj_ready/scripts/current/yaml-preview") {
        return jsonResponse({
          script_version_id: "script_v001",
          status: "current",
          yaml: "title: Ready project\nscenes: []\n",
          generated_at: "2026-06-06T00:00:00Z"
        });
      }
      if (method === "GET" && path === "/projects/proj_ready/scripts/current") {
        return jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path === "/projects/proj_ready/runs/active") return jsonResponse(null);
      if (method === "POST" && path === "/projects/proj_ready/exports") {
        expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer workspace-token");
        return jsonResponse({
          export_id: "exp_001",
          format: "yaml",
          status: "succeeded",
          filename: "script.yaml",
          download_url: "/projects/proj_ready/exports/exp_001"
        });
      }
      if (method === "GET" && path === "/projects/proj_ready/exports/exp_001") {
        expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer workspace-token");
        return new Response("title: Ready project\n", { status: 200, headers: { "Content-Type": "application/x-yaml" } });
      }
      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  const { container } = render(<App />);
  await screen.findByText(/title: Ready project/);
  const exportButton = container.querySelector(".export-menu button") as HTMLButtonElement | null;
  expect(exportButton).not.toBeNull();
  await waitFor(() => expect(exportButton).not.toBeDisabled());
  fireEvent.click(exportButton!);

  await waitFor(() => expect(clickSpy).toHaveBeenCalled());
});

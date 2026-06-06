import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { setAuthToken } from "../api/client";
import App from "../app/App";

const AUTH_TOKEN_STORAGE_KEY = "novelscript_auth_token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(body === null ? "null" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function mockWorkspaceFetch(initialProjects: unknown[] = []) {
  let projects = [...initialProjects] as Array<Record<string, unknown>>;

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
      if (method === "GET" && path === "/projects") return jsonResponse(projects);
      if (method === "POST" && path === "/projects") {
        const body = JSON.parse(String(init?.body ?? "{}")) as { name?: string };
        const project = {
          project_id: `proj_${projects.length + 1}`,
          user_id: "user_workspace",
          name: body.name ?? "未命名项目",
          stage: "empty",
          primary_conversation_id: `conv_${projects.length + 1}`,
          active_session_id: `sess_${projects.length + 1}`,
          created_at: "2026-06-06T00:00:00Z",
          updated_at: "2026-06-06T00:00:00Z"
        };
        projects = [project, ...projects];
        return jsonResponse(project);
      }
      if (method === "GET" && path.endsWith("/conversations/primary/messages")) {
        return jsonResponse({ conversation_id: "conv_001", messages: [] });
      }
      if (method === "GET" && path.endsWith("/style-source")) {
        return jsonResponse({ project_id: "proj_001", style_source: null, style_locked: false });
      }
      if (method === "POST" && path.endsWith("/style-source")) {
        const body = JSON.parse(String(init?.body ?? "null"));
        return jsonResponse({ style_source: body, style_locked: false, stage: "style_selected" });
      }
      if (method === "GET" && path.endsWith("/chapters/pending")) return jsonResponse({ chapters: [] });
      if (method === "GET" && path.endsWith("/scene-plan")) {
        return jsonResponse({ error: { code: "scene_plan_not_found", message: "Scene Plan not found", details: {} } }, 404);
      }
      if (method === "GET" && path.endsWith("/scripts/current/yaml-preview")) {
        return jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path.endsWith("/scripts/current")) {
        return jsonResponse({ error: { code: "script_not_found", message: "Script not found", details: {} } }, 404);
      }
      if (method === "GET" && path.endsWith("/runs/active")) return jsonResponse(null);

      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
  setAuthToken(null);
});

test("starts with an empty project workspace", async () => {
  mockWorkspaceFetch();
  render(<App />);
  await screen.findByLabelText("项目导航");
  expect(screen.queryByText("暂无项目")).not.toBeInTheDocument();
  expect(screen.queryByText("当前项目：新项目")).not.toBeInTheDocument();
  expect(screen.queryByText("请上传小说并完成风格设计")).not.toBeInTheDocument();
  expect(screen.queryByText("工作台 MVP（中文版）")).not.toBeInTheDocument();
  expect(screen.queryByText("对话记录")).not.toBeInTheDocument();
  expect(screen.getByText("场景计划")).toBeInTheDocument();
  expect(within(screen.getByLabelText("项目导航")).getByRole("button", { name: "新建项目" })).toBeEnabled();
});

test("creates a project with the typed name only", async () => {
  mockWorkspaceFetch();
  render(<App />);
  await screen.findByLabelText("项目导航");
  fireEvent.click(within(screen.getByLabelText("项目导航")).getByRole("button", { name: "新建项目" }));
  const dialog = screen.getByRole("dialog", { name: "为项目命名" });
  fireEvent.change(within(dialog).getByLabelText("新项目名称"), {
    target: { value: "短剧改编项目" }
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));
  await screen.findByText("请上传小说并完成风格设计");
  expect(screen.getAllByText("短剧改编项目").length).toBeGreaterThan(0);
  expect(screen.queryByText("新项目 1")).not.toBeInTheDocument();
});

test("yaml preview is read only", () => {
  render(<App initialYaml={"title: 测试剧本"} />);
  expect(screen.getByText("title: 测试剧本")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /yaml/i })).not.toBeInTheDocument();
});

test("custom style text disables reference script upload", async () => {
  mockWorkspaceFetch();
  render(<App />);
  await screen.findByLabelText("项目导航");
  fireEvent.click(within(screen.getByLabelText("项目导航")).getByRole("button", { name: "新建项目" }));
  const dialog = screen.getByRole("dialog", { name: "为项目命名" });
  fireEvent.change(within(dialog).getByLabelText("新项目名称"), {
    target: { value: "风格测试项目" }
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "保存" }));
  await screen.findByText("请上传小说并完成风格设计");
  fireEvent.click(screen.getByRole("button", { name: "点击设计生成风格" }));
  fireEvent.change(screen.getByLabelText(/自定义风格描述/), {
    target: { value: "对白短促，节奏紧张" }
  });
  expect(screen.getByLabelText("上传历史剧本参考")).toBeDisabled();
});

test("login stores token and opens workspace", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const path = url.pathname;

      if (method === "POST" && path === "/auth/login") {
        return jsonResponse({
          token: "login-token",
          user: { user_id: "user_login", login_id: "author", created_at: "2026-06-06T00:00:00Z" }
        });
      }
      if (method === "GET" && path === "/projects") {
        expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer login-token");
        return jsonResponse([]);
      }
      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  render(<App />);
  fireEvent.click(screen.getByRole("tab", { name: "登录" }));
  fireEvent.change(screen.getByLabelText("账号"), { target: { value: "author" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
  const submit = screen.getByRole("button", { name: "登录" });
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.click(submit);

  await screen.findByLabelText("项目导航");
  expect(screen.getByLabelText("用户登录信息")).toHaveTextContent("author");
  expect(screen.getByRole("button", { name: "退出登录" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "切换账号" })).toBeInTheDocument();
  expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("login-token");
});

test("register is the default auth action and opens workspace", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const path = url.pathname;

      if (method === "POST" && path === "/auth/register") {
        return jsonResponse({
          token: "register-token",
          user: { user_id: "user_register", login_id: "newauthor", created_at: "2026-06-06T00:00:00Z" }
        });
      }
      if (method === "GET" && path === "/projects") {
        expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer register-token");
        return jsonResponse([]);
      }
      return jsonResponse({ error: { code: "not_mocked", message: `${method} ${path}`, details: {} } }, 500);
    })
  );

  render(<App />);
  expect(screen.getByRole("tab", { name: "注册" })).toHaveAttribute("aria-selected", "true");
  fireEvent.change(screen.getByLabelText("账号"), { target: { value: "newauthor" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
  const submit = screen.getByRole("button", { name: "注册并进入" });
  await waitFor(() => expect(submit).toBeEnabled());
  fireEvent.click(submit);

  await screen.findByLabelText("项目导航");
  expect(screen.getByLabelText("用户登录信息")).toHaveTextContent("newauthor");
  expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("register-token");
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { setAuthToken } from "../api/client";
import App from "../app/App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  setAuthToken(null);
});

test("bypasses the login screen in local test mode", async () => {
  window.history.replaceState(null, "", "/?testMode=1");

  render(<App />);

  expect(screen.queryByLabelText("登录注册")).not.toBeInTheDocument();
  expect(await screen.findByLabelText("项目导航")).toBeInTheDocument();
  expect(screen.getByText("本地测试项目")).toBeInTheDocument();
  expect(screen.getByText("local-test")).toBeInTheDocument();
});

test("resizes the right result panel from the workspace divider", async () => {
  window.history.replaceState(null, "", "/?testMode=1");

  render(<App />);

  const resizer = await screen.findByLabelText("拖动调整剧本预览宽度");
  const workspace = resizer.closest(".figma-workspace") as HTMLElement;

  expect(workspace.style.getPropertyValue("--figma-result-panel-width")).toBe("420px");

  fireEvent.mouseDown(resizer, { clientX: 900 });
  fireEvent.mouseMove(window, { clientX: 960 });
  fireEvent.mouseUp(window);

  await waitFor(() => {
    expect(workspace.style.getPropertyValue("--figma-result-panel-width")).toBe("360px");
  });
});

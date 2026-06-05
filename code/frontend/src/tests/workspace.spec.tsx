import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import App from "../app/App";

afterEach(() => {
  cleanup();
});

test("starts with an empty project workspace", () => {
  render(<App />);
  expect(screen.getAllByText("暂无项目").length).toBeGreaterThan(0);
  expect(screen.queryByText("当前项目：新项目")).not.toBeInTheDocument();
  expect(screen.queryByText("请上传小说并完成风格设计")).not.toBeInTheDocument();
  expect(screen.queryByText("工作台 MVP（中文版）")).not.toBeInTheDocument();
  expect(screen.queryByText("对话记录")).not.toBeInTheDocument();
  expect(screen.getByText("场景计划")).toBeInTheDocument();
  expect(within(screen.getByLabelText("项目导航")).getByRole("button", { name: "新建项目" })).toBeEnabled();
});

test("creates a project with the typed name only", async () => {
  render(<App />);
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
  render(<App />);
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

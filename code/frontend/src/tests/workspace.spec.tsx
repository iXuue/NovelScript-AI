import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
  for (const button of screen.getAllByRole("button", { name: "新建项目" })) {
    expect(button).toBeDisabled();
  }
});

test("creates a project with the typed name only", async () => {
  render(<App />);
  fireEvent.change(screen.getAllByLabelText("新项目名称")[0], {
    target: { value: "短剧改编项目" }
  });
  fireEvent.click(screen.getAllByRole("button", { name: "新建项目" })[0]);
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
  fireEvent.change(screen.getAllByLabelText("新项目名称")[0], {
    target: { value: "风格测试项目" }
  });
  fireEvent.click(screen.getAllByRole("button", { name: "新建项目" })[0]);
  await screen.findByText("请上传小说并完成风格设计");
  fireEvent.click(screen.getByRole("button", { name: /风格设计/ }));
  fireEvent.change(screen.getByLabelText(/自定义风格描述/), {
    target: { value: "对白短促，节奏紧张" }
  });
  expect(screen.getByLabelText("上传历史剧本参考")).toBeDisabled();
});

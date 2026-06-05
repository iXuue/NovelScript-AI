import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import App from "../app/App";

afterEach(() => {
  cleanup();
});

test("shows upload and style prompt before generation", () => {
  render(<App />);
  expect(screen.getByText("请上传小说并选择风格来源")).toBeInTheDocument();
});

test("yaml preview is read only", () => {
  render(<App initialYaml={"title: 雨夜归来"} />);
  expect(screen.getByText("title: 雨夜归来")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /yaml/i })).not.toBeInTheDocument();
});

test("custom style text disables reference script upload", () => {
  render(<App />);
  fireEvent.change(screen.getByLabelText("自定义风格描述"), {
    target: { value: "对白短促，节奏紧张" }
  });
  expect(screen.getByLabelText("上传历史剧本参考")).toBeDisabled();
});

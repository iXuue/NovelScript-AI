import { render, screen } from "@testing-library/react";

import App from "../app/App";

test("shows upload and style prompt before generation", () => {
  render(<App />);
  expect(screen.getByText("请上传小说并选择风格来源")).toBeInTheDocument();
});

test("yaml preview is read only", () => {
  render(<App initialYaml={"title: 雨夜归来"} />);
  expect(screen.getByText("title: 雨夜归来")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /yaml/i })).not.toBeInTheDocument();
});


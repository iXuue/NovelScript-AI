import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ConversationPane } from "../components/ConversationPane";

afterEach(() => {
  cleanup();
});

function renderConversationPane(overrides: Partial<Parameters<typeof ConversationPane>[0]> = {}) {
  const props: Parameters<typeof ConversationPane>[0] = {
    canGenerateScenePlan: false,
    canGenerateScript: false,
    chapters: [],
    chaptersConfirmed: false,
    error: null,
    hasNovelUpload: false,
    loading: false,
    messages: [],
    mode: "demo",
    projectName: "测试项目",
    selectedStyle: null,
    statusMessage: null,
    styleLocked: false,
    uploadedNovelName: null,
    onConfirmChapters: vi.fn(),
    onGenerateScenePlan: vi.fn(),
    onGenerateScript: vi.fn(),
    onNovelSelected: vi.fn(),
    onStyleChange: vi.fn(),
    onStyleReferenceSelected: vi.fn(),
    onSubmitMessage: vi.fn(),
    ...overrides
  };

  render(<ConversationPane {...props} />);
  return props;
}

test("composer shows the setup placeholder and style trigger", () => {
  renderConversationPane();

  expect(screen.getByPlaceholderText("请先上传文档并选择风格；")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "设计生成风格" })).toBeInTheDocument();
});

test("style trigger opens the modal and custom text is saved on done", () => {
  const onStyleChange = vi.fn();
  renderConversationPane({ onStyleChange });

  fireEvent.click(screen.getByRole("button", { name: "设计生成风格" }));

  const dialog = screen.getByRole("dialog", { name: "设计生成风格" });
  fireEvent.change(within(dialog).getByLabelText("自定义风格描述"), {
    target: { value: "对白短促，节奏紧张。" }
  });

  expect(onStyleChange).not.toHaveBeenCalled();
  expect(within(dialog).getByLabelText("上传历史剧本参考")).toBeDisabled();

  fireEvent.click(within(dialog).getByRole("button", { name: "完成" }));

  expect(onStyleChange).toHaveBeenCalledTimes(1);
  expect(onStyleChange).toHaveBeenCalledWith({ kind: "custom_text", style_text: "对白短促，节奏紧张。" });
});

test("builtin style can be selected from the modal", () => {
  const onStyleChange = vi.fn();
  renderConversationPane({ onStyleChange });

  fireEvent.click(screen.getByRole("button", { name: "设计生成风格" }));
  fireEvent.click(screen.getByRole("button", { name: "悬疑/惊悚" }));

  expect(onStyleChange).toHaveBeenCalledWith({ kind: "builtin", builtin_style: "suspense" });
});

test("locked style can still be opened for readonly review", () => {
  const onStyleChange = vi.fn();
  renderConversationPane({
    onStyleChange,
    selectedStyle: { kind: "custom_text", style_text: "对白短促，节奏紧张。" },
    styleLocked: true
  });

  expect(screen.queryByText("已锁定")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "自定义风格描述" }));

  const dialog = screen.getByRole("dialog", { name: "设计生成风格" });
  expect(within(dialog).getByLabelText("自定义风格描述")).toHaveValue("对白短促，节奏紧张。");
  expect(within(dialog).getByLabelText("自定义风格描述")).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("button", { name: "完成" }));

  expect(onStyleChange).not.toHaveBeenCalled();
});

test("locked reference style shows saved reference file ids", () => {
  renderConversationPane({
    selectedStyle: { kind: "reference_scripts", reference_file_ids: ["file_style_001", "file_style_002"] },
    styleLocked: true
  });

  fireEvent.click(screen.getByRole("button", { name: "file_style_001、file_style_002" }));

  const dialog = screen.getByRole("dialog", { name: "设计生成风格" });
  expect(within(dialog).getAllByText("file_style_001、file_style_002").length).toBeGreaterThan(0);
  expect(within(dialog).getByLabelText("上传历史剧本参考")).toBeDisabled();
});

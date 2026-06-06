import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { StyleSourceSelector } from "../components/StyleSourceSelector";

test("custom style text is edited locally and saved on done", () => {
  const onChange = vi.fn();

  render(
    <StyleSourceSelector
      locked={false}
      loading={false}
      selected={null}
      onChange={onChange}
      onReferenceFileSelected={vi.fn()}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "点击设计生成风格" }));
  fireEvent.change(screen.getByLabelText(/自定义风格描述/), {
    target: { value: "对白短促，节奏紧张" }
  });

  expect(onChange).not.toHaveBeenCalled();
  expect(screen.getByLabelText("上传历史剧本参考")).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "完成" }));

  expect(onChange).toHaveBeenCalledTimes(1);
  expect(onChange).toHaveBeenCalledWith({ kind: "custom_text", style_text: "对白短促，节奏紧张" });
});

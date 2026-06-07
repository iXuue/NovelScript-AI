import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ScriptPreviewPanel } from "../components/ScriptPreviewPanel";
import type { ScriptCurrentForUi } from "../types";

const script: ScriptCurrentForUi = {
  script_version_id: "script_v001",
  status: "current",
  generated_at: "2026-06-07T00:00:00Z",
  scenes: [
    {
      scene_id: "S001",
      title: "陨落的天才",
      source_chapter_ids: ["CH001"],
      scene_info: "外景 / 测试广场 / 白天",
      characters: ["萧炎", "测试中年男子"],
      scene_purpose: "通过测试成绩对比，建立人物落差。",
      core_conflict: "萧炎承受众人嘲讽。"
    }
  ],
  content_blocks: [
    {
      content_block_id: "CB001",
      scene_id: "S001",
      block_type: "dialogue",
      display_label: "S001 对白 1",
      speaker: "测试中年男子",
      text: "萧炎，斗之力，三段！级别：低级！",
      source_evidence_ids: [],
      source_paragraph_ids: ["CH001_P001"]
    },
    {
      content_block_id: "CB002",
      scene_id: "S001",
      block_type: "action",
      display_label: "S001 动作 1",
      speaker: null,
      text: "萧炎握紧手掌，安静地回到队伍最后。",
      source_evidence_ids: [],
      source_paragraph_ids: []
    }
  ]
};

test("renders chinese yaml grouped by scene instead of raw backend yaml", () => {
  const onEvidenceClick = vi.fn();
  render(<ScriptPreviewPanel script={script} onEvidenceClick={onEvidenceClick} />);

  expect(screen.getByText("陨落的天才")).toBeInTheDocument();
  expect(screen.getByText(/场景编号: S001/)).toBeInTheDocument();
  expect(screen.getByText(/标题: 陨落的天才/)).toBeInTheDocument();
  expect(screen.getByText(/场景信息: 外景 \/ 测试广场 \/ 白天/)).toBeInTheDocument();
  expect(screen.getByText(/出场人物:\s+- 萧炎\s+- 测试中年男子/)).toBeInTheDocument();
  expect(screen.getByText(/场景目的: 通过测试成绩对比，建立人物落差。/)).toBeInTheDocument();
  expect(screen.getByText(/核心冲突: 萧炎承受众人嘲讽。/)).toBeInTheDocument();
  expect(screen.getByText(/类型: 对白/)).toBeInTheDocument();
  expect(screen.getByText(/说话人: 测试中年男子/)).toBeInTheDocument();
  expect(screen.getByText(/文本: 萧炎，斗之力，三段！级别：低级！/)).toBeInTheDocument();
  expect(screen.queryByText(/scene_id:/)).not.toBeInTheDocument();
  expect(screen.queryByText(/source_chapter_ids:/)).not.toBeInTheDocument();
  expect(screen.queryByText(/来源段落:\s+- CH001_P001/)).not.toBeInTheDocument();

  const block = screen.getByText(/文本: 萧炎，斗之力，三段！级别：低级！/).closest("section");
  expect(block).not.toBeNull();
  expect(within(block as HTMLElement).getByText(/类型: 对白/)).toBeInTheDocument();
  fireEvent.click(within(block as HTMLElement).getByRole("button", { name: "来源段落" }));

  expect(onEvidenceClick).toHaveBeenCalledWith("CB001");
});

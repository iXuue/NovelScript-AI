import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { EvidenceModal } from "../components/EvidenceModal";
import type { EvidenceLookupResult } from "../types";

test("renders source paragraphs even when API payload has only paragraph_id", () => {
  const onClose = vi.fn();
  const fallback = {
    content_block_id: "CB001",
    evidence: [
      {
        source_paragraph_id: "CH001_P003",
        source_evidence_id: null,
        chapter_id: "CH001",
        paragraph_id: "CH001_P003",
        text: "萧炎，斗之力，三段！级别：低级！"
      }
    ]
  } satisfies EvidenceLookupResult;

  render(<EvidenceModal projectId="proj_test" contentBlockId="CB001" fallback={fallback} onClose={onClose} />);

  expect(screen.getByRole("dialog", { name: "来源段落" })).toBeInTheDocument();
  expect(
    screen.getByText(
      (_, node) =>
        node?.tagName.toLowerCase() === "p" && node.textContent === "CH001_P003 : 萧炎，斗之力，三段！级别：低级！"
    )
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "关闭来源段落弹窗" }));

  expect(onClose).toHaveBeenCalled();
});

test("hides immediately when close is clicked even before parent unmounts", () => {
  const fallback = {
    content_block_id: "CB001",
    evidence: [
      {
        source_paragraph_id: "CH001_P003",
        source_evidence_id: null,
        chapter_id: "CH001",
        paragraph_id: "CH001_P003",
        text: "萧炎，斗之力，三段！级别：低级！"
      }
    ]
  } satisfies EvidenceLookupResult;

  render(<EvidenceModal projectId="proj_test" contentBlockId="CB001" fallback={fallback} onClose={vi.fn()} />);

  fireEvent.click(screen.getByRole("button", { name: "关闭来源段落弹窗" }));

  expect(screen.queryByRole("dialog", { name: "来源段落" })).not.toBeInTheDocument();
});

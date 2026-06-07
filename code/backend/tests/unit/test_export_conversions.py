from io import BytesIO

from docx import Document

from app.services.export_service import serialize_export


SCRIPT_WITH_LABELS = {
    "title": "陨落的天才",
    "scenes": [
        {
            "scene_id": "S001",
            "title": "陨落的天才",
            "scene_info": "外景 / 测试广场 / 白天",
            "characters": ["萧炎", "测试中年男子"],
            "scene_purpose": "通过测试成绩对比，建立人物落差。",
            "core_conflict": "萧炎承受众人嘲讽。",
            "content_blocks": [
                {
                    "content_block_id": "CB001",
                    "type": "dialogue",
                    "speaker": "测试中年男子",
                    "text": "萧炎，斗之力，三段！级别：低级！",
                },
                {
                    "content_block_id": "CB002",
                    "type": "action",
                    "speaker": None,
                    "text": "萧炎握紧手掌，安静地回到队伍最后。",
                },
            ],
        }
    ],
}


def _docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())


def test_docx_export_uses_readable_chinese_labels():
    exported = serialize_export(SCRIPT_WITH_LABELS, "docx")

    text = _docx_text(exported)

    assert "场景编号：S001" in text
    assert "标题：陨落的天才" in text
    assert "场景信息：外景 / 测试广场 / 白天" in text
    assert "出场人物：萧炎、测试中年男子" in text
    assert "场景目的：通过测试成绩对比，建立人物落差。" in text
    assert "核心冲突：萧炎承受众人嘲讽。" in text
    assert "测试中年男子：萧炎，斗之力，三段！级别：低级！" in text
    assert "动作：萧炎握紧手掌，安静地回到队伍最后。" in text


def test_doc_export_converts_generated_docx(monkeypatch):
    calls = []

    def fake_convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
        calls.append((content, source_suffix, target_suffix))
        return b"DOC_BYTES"

    monkeypatch.setattr("app.services.export_service.convert_document", fake_convert_document)

    exported = serialize_export(SCRIPT_WITH_LABELS, "doc")

    assert exported == b"DOC_BYTES"
    assert calls[0][0].startswith(b"PK")
    assert calls[0][1:] == (".docx", ".doc")
    source_text = _docx_text(calls[0][0])
    assert "测试中年男子：萧炎，斗之力，三段！级别：低级！" in source_text
    assert "动作：萧炎握紧手掌，安静地回到队伍最后。" in source_text


def test_pdf_export_converts_generated_docx(monkeypatch):
    calls = []

    def fake_convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
        calls.append((content, source_suffix, target_suffix))
        return b"%PDF-FAKE"

    monkeypatch.setattr("app.services.export_service.convert_document", fake_convert_document)

    exported = serialize_export(SCRIPT_WITH_LABELS, "pdf")

    assert exported == b"%PDF-FAKE"
    assert calls[0][0].startswith(b"PK")
    assert calls[0][1:] == (".docx", ".pdf")
    source_text = _docx_text(calls[0][0])
    assert "测试中年男子：萧炎，斗之力，三段！级别：低级！" in source_text
    assert "动作：萧炎握紧手掌，安静地回到队伍最后。" in source_text

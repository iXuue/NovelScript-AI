from app.services.chapter_service import assign_paragraph_ids, detect_chapters


def test_detect_chinese_chapters():
    markdown = "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信封泛黄。"
    chapters = detect_chapters(markdown)
    assert [chapter.title for chapter in chapters] == ["第一章 雨夜", "第二章 旧信"]


def test_assign_stable_paragraph_ids():
    chapters = detect_chapters("# 第一章 雨夜\n\n她回来了。\n\n门开了。")
    indexed = assign_paragraph_ids(chapters)
    assert indexed[0].paragraphs[0].paragraph_id == "CH001_P001"
    assert indexed[0].paragraphs[1].paragraph_id == "CH001_P002"


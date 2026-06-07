from app.services.chapter_service import UploadedMarkdownDocument, assign_paragraph_ids, detect_chapters, detect_documents_chapters


def test_detect_chinese_chapters():
    markdown = "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信封泛黄。"
    chapters = detect_chapters(markdown)
    assert [chapter.title for chapter in chapters] == ["第一章 雨夜", "第二章 旧信"]


def test_assign_stable_paragraph_ids():
    chapters = detect_chapters("# 第一章 雨夜\n\n她回来了。\n\n门开了。")
    indexed = assign_paragraph_ids(chapters)
    assert indexed[0].paragraphs[0].paragraph_id == "CH001_P001"
    assert indexed[0].paragraphs[1].paragraph_id == "CH001_P002"


def test_detect_common_chapter_heading_patterns():
    markdown = "\n\n".join(
        [
            "序章\n\n风来了。",
            "第1章 雨夜\n\n她回来了。",
            "CHAPTER 2 Old Letter\n\nA letter arrived.",
            "一、归来\n\n门开了。",
            "1. 对峙\n\n没人说话。",
            "番外 雪夜\n\n雪停了。",
        ]
    )

    chapters = detect_chapters(markdown)

    assert [chapter.title for chapter in chapters] == [
        "序章",
        "第1章 雨夜",
        "CHAPTER 2 Old Letter",
        "一、归来",
        "1. 对峙",
        "番外 雪夜",
    ]


def test_detect_documents_chapters_sorts_files_naturally_and_uses_filename_for_single_chapter_files():
    documents = [
        UploadedMarkdownDocument(filename="chapter10.txt", markdown="第十章 终局\n\n雨停了。"),
        UploadedMarkdownDocument(filename="chapter2.txt", markdown="她推开门。\n\n屋里没人。"),
        UploadedMarkdownDocument(filename="chapter1.txt", markdown="第一章 雨夜\n\n她回来了。"),
    ]

    chapters = detect_documents_chapters(documents)
    indexed = assign_paragraph_ids(chapters)

    assert [chapter.chapter_id for chapter in chapters] == ["CH001", "CH002", "CH003"]
    assert [chapter.title for chapter in chapters] == ["第一章 雨夜", "chapter2", "第十章 终局"]
    assert indexed[1].paragraphs[0].paragraph_id == "CH002_P001"
    assert indexed[1].paragraphs[1].paragraph_id == "CH002_P002"


def test_detect_documents_chapters_drops_repeated_table_of_contents_prefix():
    markdown = """目
录
第一章
婴儿
第二章
离奇的身世
第三章
家和亲人
版权信息
作者档案
故事梗概会在目录后出现，导致最后一个目录项正文变长。

第一章
婴儿
挂在墙壁上的圆形大钟显示着早上八点半。

丘子若坐在床边，凝望着床上正在沉睡的婴儿。
第二章
离奇的身世
萝铃在孤儿院里发现了自己的身世线索。

她开始意识到身边的一切并不普通。
第三章
家和亲人
新的亲人出现，带来陌生而复杂的家庭关系。
"""

    chapters = detect_documents_chapters([UploadedMarkdownDocument(filename="novel.pdf", markdown=markdown)])
    indexed = assign_paragraph_ids(chapters)

    assert [chapter.chapter_id for chapter in indexed] == ["CH001", "CH002", "CH003"]
    assert [chapter.title for chapter in indexed] == ["第一章", "第二章", "第三章"]
    assert indexed[0].raw_text.startswith("婴儿\n挂在墙壁上的圆形大钟")
    assert len(indexed[0].paragraphs) == 2


def test_detect_documents_chapters_keeps_short_chapters_without_repeated_body_sequence():
    markdown = """第一章
婴儿
第二章
离奇
第三章
归家
"""

    chapters = detect_documents_chapters([UploadedMarkdownDocument(filename="short.txt", markdown=markdown)])

    assert [chapter.chapter_id for chapter in chapters] == ["CH001", "CH002", "CH003"]
    assert [chapter.title for chapter in chapters] == ["第一章", "第二章", "第三章"]


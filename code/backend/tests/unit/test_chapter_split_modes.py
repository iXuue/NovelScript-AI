from app.services.chapter_service import (
    UploadedMarkdownDocument,
    assign_paragraph_ids,
    detect_chapters,
    detect_documents_chapters,
)

# ---------- 三章共享内容（! 占位） ----------

CHAPTER_1_BODY = "!!!!!\n\n!!!!!"
CHAPTER_2_BODY = "!!!!!\n\n!!!!!\n\n!!!!!"
CHAPTER_3_BODY = "!!!!!"


def test_single_file_three_chapters():
    """单文件包含三章，应检测出三个章节并正确编号。"""
    markdown = "\n\n".join(
        [
            f"第一章 开端\n\n{CHAPTER_1_BODY}",
            f"第二章 发展\n\n{CHAPTER_2_BODY}",
            f"第三章 结局\n\n{CHAPTER_3_BODY}",
        ]
    )

    chapters = detect_chapters(markdown)
    indexed = assign_paragraph_ids(chapters)

    # 章节标题
    assert [ch.title for ch in indexed] == ["第一章 开端", "第二章 发展", "第三章 结局"]

    # 章节 ID
    assert [ch.chapter_id for ch in indexed] == ["CH001", "CH002", "CH003"]

    # 段落数量
    assert [len(ch.paragraphs) for ch in indexed] == [2, 3, 1]

    # 段落 ID
    assert [p.paragraph_id for p in indexed[0].paragraphs] == ["CH001_P001", "CH001_P002"]
    assert [p.paragraph_id for p in indexed[1].paragraphs] == ["CH002_P001", "CH002_P002", "CH002_P003"]
    assert [p.paragraph_id for p in indexed[2].paragraphs] == ["CH003_P001"]


def test_multi_file_three_chapters():
    """三文件各含一章，应自然排序后统一编号，段落 ID 连续。"""
    documents = [
        UploadedMarkdownDocument(
            filename="chapter2.txt",
            markdown=f"第二章 发展\n\n{CHAPTER_2_BODY}",
        ),
        UploadedMarkdownDocument(
            filename="chapter1.txt",
            markdown=f"第一章 开端\n\n{CHAPTER_1_BODY}",
        ),
        UploadedMarkdownDocument(
            filename="chapter3.txt",
            markdown=f"第三章 结局\n\n{CHAPTER_3_BODY}",
        ),
    ]

    chapters = detect_documents_chapters(documents)
    indexed = assign_paragraph_ids(chapters)

    # 按文件名自然排序后标题顺序
    assert [ch.title for ch in indexed] == ["第一章 开端", "第二章 发展", "第三章 结局"]

    # 章节 ID 统一编号
    assert [ch.chapter_id for ch in indexed] == ["CH001", "CH002", "CH003"]

    # 段落数量与 ID
    assert [len(ch.paragraphs) for ch in indexed] == [2, 3, 1]
    assert [p.paragraph_id for p in indexed[0].paragraphs] == ["CH001_P001", "CH001_P002"]
    assert [p.paragraph_id for p in indexed[1].paragraphs] == ["CH002_P001", "CH002_P002", "CH002_P003"]
    assert [p.paragraph_id for p in indexed[2].paragraphs] == ["CH003_P001"]


def test_single_vs_multi_yield_same_result():
    """单文件拆分与多文件拆分结果应一致（段落 ID、标题）。"""
    markdown = "\n\n".join(
        [
            f"第一章 开端\n\n{CHAPTER_1_BODY}",
            f"第二章 发展\n\n{CHAPTER_2_BODY}",
            f"第三章 结局\n\n{CHAPTER_3_BODY}",
        ]
    )
    single_result = assign_paragraph_ids(detect_chapters(markdown))

    documents = [
        UploadedMarkdownDocument(filename="ch1.txt", markdown=f"第一章 开端\n\n{CHAPTER_1_BODY}"),
        UploadedMarkdownDocument(filename="ch2.txt", markdown=f"第二章 发展\n\n{CHAPTER_2_BODY}"),
        UploadedMarkdownDocument(filename="ch3.txt", markdown=f"第三章 结局\n\n{CHAPTER_3_BODY}"),
    ]
    multi_result = assign_paragraph_ids(detect_documents_chapters(documents))

    assert len(single_result) == len(multi_result) == 3

    for sc, mc in zip(single_result, multi_result):
        assert sc.title == mc.title
        assert sc.chapter_id == mc.chapter_id
        assert len(sc.paragraphs) == len(mc.paragraphs)
        for sp, mp in zip(sc.paragraphs, mc.paragraphs):
            assert sp.paragraph_id == mp.paragraph_id

"""全链路集成测试：从上传小说到导出剧本，验证每个环节的数据流转。"""
from app.core.database import get_db
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.checkpoint import Checkpoint
from app.models.export import ExportJob
from app.models.repair import RepairAttempt
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion
from app.models.story import StoryBible
from app.models.style import StyleProfile


# ---------- 三章小说（生成） ----------

NOVEL_CHAPTER_1 = """# 第一章 雨夜归来

她推开旧宅的木门，门轴发出一声尖锐的呻吟。雨水顺着门檐滴落，打在她湿透的肩头。

屋里一片漆黑。她伸手摸向墙壁，指尖触到了冰冷的开关。灯没有亮。

"妈妈？"她试探着喊了一声。

回答她的只有雨声和远处隐约的雷鸣。

她打开手机的手电筒，光束扫过客厅。墙上挂着褪色的全家福，柜子上落满了灰。餐桌上还摆着两副碗筷，仿佛有人刚刚离开。

她走近餐桌，发现碗里的面条已经干涸发硬。旁边的杯子里，茶水表面浮着一层灰白的霉斑。

"不是刚走。"她喃喃自语，心里涌起一股说不清的不安。

她转身往二楼走去。楼梯在脚下发出吱呀的声响。每走一步，那股不安就越强烈。

二楼走廊尽头，母亲房间的门虚掩着。门缝里透出一道微弱的光。

她屏住呼吸，缓缓推开门。"""

NOVEL_CHAPTER_2 = """# 第二章 旧信的秘密

房间里亮着一盏台灯，灯下放着一封已经泛黄的信。信纸边角卷起，字迹却依然清晰。

她拿起信，逐字读下去。瞳孔猛地收缩。

"五月十二日，你必须离开这里。那些人不只是在找你——他们在等一个时机。如果你还念着孩子，就把真相告诉她。"

落款是一个她从未听说过的名字：陈远山。

她掏出手机拍下信的内容，手指在屏幕上微微发抖。母亲从未提过这个人，也从未说过自己曾经被人追踪。

书桌的抽屉半开着。她拉开抽屉，里面是一叠剪报。每份剪报都标注着日期——最早的可以追溯到二十年前。

"失踪"、"事故"、"无人认领"……

她用手机灯光扫过剪报标题，心跳越来越快。这些剪报里的名字她全不认识，但每份都被人用红笔圈出了某个关键句子。

她翻到最底下，发现了一张黑白照片。照片上是母亲年轻时的模样，旁边站着一个陌生的男人，怀里抱着一个婴儿。

照片背面只有一行字："小念，这是你真正的名字。"""

NOVEL_CHAPTER_3 = """# 第三章 雨停了

凌晨四点，雨终于停了。天色从漆黑转为灰蓝。

她坐在母亲房间的地板上，身边散落着全部剪报和信件。手机屏幕亮着——她花了两个小时查遍了所有能搜到的名字。

陈远山，二十年前死于一场"意外"。当地报纸用了一个豆腐块大小的版面。没有讣告，没有追悼会。

母亲在那之后搬到了这座小镇，换了一个全新的身份，再未对任何人提起过往。

她看着照片上母亲年轻的笑容，第一次意识到那笑容里藏着的不是幸福，而是劫后余生的庆幸。

窗外传来第一声鸟鸣。她站起身，把所有材料整齐叠好，放进自己的包里。然后走到母亲的梳妆台前，看着镜子里的自己。

"我叫小念。"

她说出这句话的时候，声音很轻，却异常坚定。

楼下的灯突然亮了。一个苍老的声音从厨房传来：

"小念，你回来了。" """


def _full_pipeline(client, style_kind="builtin", style_value="suspense"):
    """跑完整条链路，返回 project_id 和各阶段关键数据。"""
    # ---- 1. 创建项目 ----
    project = client.post("/projects", json={"name": "雨夜归来"}).json()
    project_id = project["project_id"]
    assert project["stage"] == "empty"

    # ---- 2. 上传单文件三章小说 ----
    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={
            "file": (
                "novel.md",
                f"{NOVEL_CHAPTER_1}\n\n{NOVEL_CHAPTER_2}\n\n{NOVEL_CHAPTER_3}",
            )
        },
    )
    assert upload.status_code == 200
    assert [ch["chapter_id"] for ch in upload.json()["detected_chapters"]] == ["CH001", "CH002", "CH003"]

    # ---- 3. 获取待确认章节 ----
    pending = client.get(f"/projects/{project_id}/chapters/pending")
    assert pending.status_code == 200
    chapter_ids = [ch["chapter_id"] for ch in pending.json()["chapters"]]
    assert chapter_ids == ["CH001", "CH002", "CH003"]
    assert [ch["title"] for ch in pending.json()["chapters"]] == ["第一章 雨夜归来", "第二章 旧信的秘密", "第三章 雨停了"]

    # ---- 4. 确认章节 ----
    confirm = client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": chapter_ids})
    assert confirm.status_code == 200
    assert confirm.json()["stage"] == "chapters_confirmed"

    # ---- 5. 设置风格 ----
    if style_kind == "builtin":
        style = client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": style_value})
    else:
        style = client.post(f"/projects/{project_id}/style-source", json={"kind": "custom_text", "style_text": style_value})
    assert style.status_code == 200

    # ---- 6. 生成 Scene Plan ----
    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")
    assert scene_plan.status_code == 200
    plan = client.get(f"/projects/{project_id}/scene-plan")
    assert plan.status_code == 200
    assert plan.json()["validation"]["passed"] is True
    assert len(plan.json()["scenes"]) >= 1

    # ---- 7. 确认 Scene Plan ----
    confirm_plan = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})
    assert confirm_plan.status_code == 200
    assert confirm_plan.json()["confirmed"] is True

    # ---- 8. 生成剧本 ----
    script_run = client.post(f"/projects/{project_id}/scripts/generate")
    assert script_run.status_code == 200
    current = client.get(f"/projects/{project_id}/scripts/current")
    assert current.status_code == 200
    assert current.json()["status"] == "current"

    # ---- 9. 导出 ----
    exports = {}
    for fmt in ["yaml", "markdown", "txt", "docx", "clean_json"]:
        exp = client.post(f"/projects/{project_id}/exports", json={"format": fmt})
        assert exp.status_code == 200, f"export {fmt} failed"
        exports[fmt] = exp.json()
        # 验证文件可下载
        download = client.get(exp.json()["download_url"])
        assert download.status_code == 200, f"download {fmt} failed"
        # 无内部字段泄漏
        if fmt == "docx":
            assert download.content.startswith(b"PK")
        else:
            assert "content_block_id" not in download.text, f"{fmt} leaked content_block_id"
            assert "source_evidence_ids" not in download.text, f"{fmt} leaked source_evidence_ids"

    pdf = client.post(f"/projects/{project_id}/exports", json={"format": "pdf"})
    assert pdf.status_code == 400
    assert pdf.json()["error"]["code"] == "pdf_not_available"

    return project_id, exports


def test_full_pipeline_all_artifacts_persisted(client):
    """全链路：所有中间产物和数据均正确入库。"""
    project_id, exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        # 章节
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.order).all()
        assert len(chapters) == 3
        assert [ch.status for ch in chapters] == ["confirmed", "confirmed", "confirmed"]

        # 段落
        paragraphs = db.query(Paragraph).filter(Paragraph.project_id == project_id).all()
        assert len(paragraphs) >= 6  # 三章至少每章2段

        # 章节摘要
        summaries = db.query(ChapterSummary).filter(ChapterSummary.project_id == project_id).all()
        assert len(summaries) == 3

        # 证据
        evidence = db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).all()
        assert len(evidence) >= 3

        # Story Bible
        story_bible = db.query(StoryBible).filter(StoryBible.project_id == project_id).one()
        assert story_bible.title == "雨夜归来"

        # Style Profile
        style = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()
        assert style.source == "builtin:suspense"

        # Scene Plan + Validation
        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()
        assert plan.confirmed is True
        scenes = db.query(ScenePlanScene).filter(ScenePlanScene.scene_plan_id == plan.scene_plan_id).all()
        assert len(scenes) >= 1
        validation = db.query(ScenePlanValidation).filter(ScenePlanValidation.scene_plan_id == plan.scene_plan_id).one()
        assert validation.passed is True

        # 剧本 + Validation
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()
        assert version.status == "current"
        script_scenes = db.query(ScriptScene).filter(ScriptScene.script_version_id == version.script_version_id).all()
        assert len(script_scenes) == len(scenes)
        content_blocks = db.query(ScriptContentBlock).filter(ScriptContentBlock.script_version_id == version.script_version_id).all()
        assert len(content_blocks) >= 1
        script_validations = (
            db.query(ScriptSceneValidation)
            .filter(ScriptSceneValidation.script_version_id == version.script_version_id)
            .all()
        )
        assert len(script_validations) == len(scenes)
        assert all(v.passed for v in script_validations)

        # 导出
        export_records = db.query(ExportJob).filter(ExportJob.project_id == project_id).all()
        assert len(export_records) == 5

        # Checkpoint
        checkpoints = db.query(Checkpoint).filter(Checkpoint.project_id == project_id).all()
        assert len(checkpoints) >= 2  # chapters_confirmed + scene_plan_confirmed
    finally:
        db.close()


def test_full_pipeline_with_custom_text_style(client):
    """全链路：自定义文字风格路径可正常走通。"""
    project_id, exports = _full_pipeline(client, style_kind="custom_text", style_value="更悬疑，对白短促，节奏快。")

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        style = db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one()
        assert style.source == "fake-analysis"
        assert "悬疑" in style.profile_text
    finally:
        db.close()


def test_full_pipeline_no_repair_attempts_on_clean_run(client):
    """全链路：首次通过时不应有任何修复尝试记录。"""
    project_id, exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        repairs = db.query(RepairAttempt).filter(RepairAttempt.project_id == project_id).all()
        assert len(repairs) == 0
    finally:
        db.close()


def test_full_pipeline_scene_plan_scenes_reference_valid_chapters_and_evidence(client):
    """全链路：Scene Plan 的场景必须引用真实存在的章节和证据。"""
    project_id, exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        chapter_ids = {ch.chapter_id for ch in db.query(Chapter).filter(Chapter.project_id == project_id).all()}
        evidence_ids = {ev.evidence_id for ev in db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).all()}
        plan = db.query(ScenePlan).filter(ScenePlan.project_id == project_id).one()

        for scene in plan.scenes:
            assert set(scene.source_chapter_ids).issubset(chapter_ids), f"{scene.scene_id} refs unknown chapters"
            if scene.source_evidence_ids:
                assert set(scene.source_evidence_ids).issubset(evidence_ids), f"{scene.scene_id} refs unknown evidence"
    finally:
        db.close()


def test_full_pipeline_script_blocks_are_traceable_to_evidence(client):
    """全链路：剧本内容块必须可追溯到证据索引。"""
    project_id, exports = _full_pipeline(client)

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        evidence_ids = {ev.evidence_id for ev in db.query(EvidenceItem).filter(EvidenceItem.project_id == project_id).all()}
        version = db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id).one()

        for block in version.content_blocks:
            if block.source_evidence_ids:
                assert set(block.source_evidence_ids).issubset(evidence_ids), f"{block.content_block_id} refs unknown evidence"
    finally:
        db.close()

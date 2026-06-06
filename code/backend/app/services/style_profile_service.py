from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.style import StyleProfile, StyleReferenceFile, StyleSourceRecord
from app.services.context_budget_service import DEFAULT_MAX_STYLE_SOURCE_CHARS, generate_with_context_log, truncate_text
from app.services.llm_provider import LLMProvider
from app.services.store import now_utc


BUILTIN_STYLE_TEXTS = {
    "realism": (
        "采用平实克制的现实主义风格。对白自然生活化，避免夸张台词和戏剧化表达。"
        "场景长度适中，节奏跟随人物选择和现实压力推进，不依赖巧合或外力推动剧情。"
        "冲突来源于人物在具体处境中的真实选择，而非外部强加的对抗。"
        "旁白和动作描写服务于人物心理和氛围营造，不喧宾夺主。"
        "转场以生活场景的自然过渡为主，保持连贯的时空感。"
        "整体改编需保留现实细节和人物行为的逻辑自洽。"
    ),
    "suspense": (
        "采用冷峻克制的悬疑/惊悚风格。对白短促有力，多用潜台词和留白而非直白解释，"
        "人物说话带压迫感和防备感。场景较短，切换频繁，通过硬切和悬念转场保持紧张节奏。"
        "冲突通过信息差、线索分布和层层反转来制造，而非依赖外部暴力。"
        "旁白极少，动作描写服务于悬疑氛围的积累和释放。"
        "整体改编需保留原文中的伏笔、线索和关键反转点，不可提前暴露谜底。"
    ),
    "romance": (
        "采用细腻含蓄的爱情/情感风格。对白注重情绪变化和言外之意，"
        "避免甜腻直白的告白，用细节和行动传递感情。场景长度适中，"
        "节奏跟随人物关系的情感递进，给关键情感节点留足呼吸空间。"
        "冲突围绕关系误解、内心选择和情感拉扯展开，而非外部阻碍。"
        "旁白可用于补充人物内心，但不过度解释。转场以情绪衔接为主。"
        "整体改编需强化情感递进的层次感，保留关系转折的关键时刻。"
    ),
    "comedy": (
        "采用节奏明快的喜剧风格。对白口语化、高频，强调人物间的反差、"
        "误会和节奏错位来制造笑点。场景较短，快速推进，不拖泥带水。"
        "冲突通过错位、反转和夸张的情境设计来推动，而非沉重对抗。"
        "旁白极少，动作描写服务于喜剧节奏和视觉笑点。"
        "转场注重节奏感，常用反差或callback衔接。"
        "整体改编需保留原文中可喜剧化的冲突和人物反差。"
    ),
    "short_drama": (
        "采用快节奏的短剧/网剧风格。对白直接、强目标导向、强情绪表达，"
        "每句话都推动剧情或揭示人物。场景短小精悍，每场必须有明确的冲突推进或爽点释放。"
        "节奏快，不铺垫不拖沓，用高频冲突和钩子抓住观众。"
        "冲突设计强调即时对抗和明确胜负，人物目标一目了然。"
        "旁白极少，动作描写服务于强情节点。转场用钩子或强情节点衔接。"
        "整体改编需每场保留明确的爽点或悬念钩子。"
    ),
}


CUSTOM_TEXT_SYSTEM_PROMPT = (
    "你是 Style Profile Worker。请把用户对目标剧本风格的文字描述整理润色为一段完整、"
    "可直接注入生成 Prompt 的风格说明。\n"
    "规则：\n"
    "1. 只基于用户给出的描述，不编造用户没有表达的风格特征。\n"
    "2. 将零散的描述整合为连贯的一段话，覆盖对白风格、节奏、冲突设计、场景长度、旁白和动作比例、转场方式等方面。\n"
    "3. 用户没有提到的方面用中性的默认描述补充，但不要喧宾夺主。\n"
    "4. 只输出一段纯文本，不要 JSON、不要 Markdown、不要标题、不要解释。\n"
)


REFERENCE_SCRIPTS_SYSTEM_PROMPT = (
    "你是 Style Profile Worker。请从用户上传的历史剧本中提炼出一段完整的剧本风格描述。\n"
    "规则：\n"
    "1. 只基于给定剧本内容，不编造剧本中没有体现的风格特征。\n"
    "2. 从对白密度与风格、场景长度与节奏、冲突设计方式、旁白与动作描写比例、转场方式等维度进行分析。\n"
    "3. 用概括性的语言描述整体风格，不要逐条罗列，而是写成一段连贯的文字。\n"
    "4. 不确定的方面用中性的默认描述补充。\n"
    "5. 只输出一段纯文本，不要 JSON、不要 Markdown、不要标题、不要解释。\n"
)


def generate_style_profile(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None,
    run_id: str | None = None,
) -> StyleProfile | None:
    source = db.get(StyleSourceRecord, project_id)
    if source is None:
        return None
    if source.kind == "builtin":
        profile_text = BUILTIN_STYLE_TEXTS.get(
            source.builtin_style or "realism",
            BUILTIN_STYLE_TEXTS["realism"],
        )
        source_name = f"builtin:{source.builtin_style or 'realism'}"
    elif source.kind == "custom_text":
        if llm_provider is None:
            raise RuntimeError("LLM provider is required to generate Style Profile from custom text")
        response = generate_with_context_log(
            llm_provider,
            task_type="style_profile",
            prompt=_custom_text_prompt(source.style_text or ""),
            response_format="text",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="style_profile",
            source_item_count=1,
            included_item_count=1,
        )
        profile_text = response.text.strip()
        if not profile_text:
            raise RuntimeError("style_profile provider returned empty text")
        source_name = response.model_name
    elif source.kind == "reference_scripts":
        if llm_provider is None:
            raise RuntimeError("LLM provider is required to generate Style Profile from reference scripts")
        files = (
            db.query(StyleReferenceFile)
            .filter(
                StyleReferenceFile.project_id == source.project_id,
                StyleReferenceFile.file_id.in_(source.reference_file_ids),
            )
            .order_by(StyleReferenceFile.file_id)
            .all()
        )
        scripts_material = "\n\n".join(f"# {file.filename}\n{file.markdown}" for file in files)
        response = generate_with_context_log(
            llm_provider,
            task_type="style_profile",
            prompt=_reference_scripts_prompt(scripts_material),
            response_format="text",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="style_profile",
            source_item_count=len(files),
            included_item_count=len(files),
        )
        profile_text = response.text.strip()
        if not profile_text:
            raise RuntimeError("style_profile provider returned empty text")
        source_name = response.model_name
    else:
        return None

    return _replace_style_profile(db, project_id, profile_text, source_name)


def _replace_style_profile(db: Session, project_id: str, profile_text: str, source_name: str) -> StyleProfile:
    db.execute(delete(StyleProfile).where(StyleProfile.project_id == project_id))
    timestamp = now_utc()
    profile = StyleProfile(
        project_id=project_id,
        profile_text=profile_text,
        source=source_name,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(profile)
    db.commit()
    return profile


def _custom_text_prompt(style_text: str) -> str:
    return f"{CUSTOM_TEXT_SYSTEM_PROMPT}\n\n用户描述：\n{truncate_text(style_text, DEFAULT_MAX_STYLE_SOURCE_CHARS)}"


def _reference_scripts_prompt(scripts_material: str) -> str:
    return f"{REFERENCE_SCRIPTS_SYSTEM_PROMPT}\n\n参考剧本：\n{truncate_text(scripts_material, DEFAULT_MAX_STYLE_SOURCE_CHARS)}"

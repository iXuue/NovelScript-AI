from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="empty")
    primary_conversation_id: Mapped[str] = mapped_column(String(40), nullable=False)
    active_session_id: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="projects")
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    paragraphs = relationship("Paragraph", back_populates="project", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="project", cascade="all, delete-orphan")
    chapter_summaries = relationship("ChapterSummary", back_populates="project", cascade="all, delete-orphan")
    evidence_items = relationship("EvidenceItem", back_populates="project", cascade="all, delete-orphan")
    style_source = relationship("StyleSourceRecord", back_populates="project", cascade="all, delete-orphan", uselist=False)
    style_reference_files = relationship("StyleReferenceFile", back_populates="project", cascade="all, delete-orphan")
    style_profiles = relationship("StyleProfile", back_populates="project", cascade="all, delete-orphan")
    story_bibles = relationship("StoryBible", back_populates="project", cascade="all, delete-orphan")
    scene_plans = relationship("ScenePlan", back_populates="project", cascade="all, delete-orphan")
    script_versions = relationship("ScriptVersion", back_populates="project", cascade="all, delete-orphan")

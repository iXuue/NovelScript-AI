from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="empty")
    style_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_conversation_id: Mapped[str] = mapped_column(String(40), nullable=False)
    active_session_id: Mapped[str] = mapped_column(String(40), nullable=False)
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
    repair_attempts = relationship("RepairAttempt", back_populates="project", cascade="all, delete-orphan")
    export_jobs = relationship("ExportJob", back_populates="project", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan")
    agent_run_steps = relationship("AgentRunStep", back_populates="project", cascade="all, delete-orphan")
    conversation_messages = relationship("ConversationMessageRecord", back_populates="project", cascade="all, delete-orphan")
    source_files = relationship("SourceFileRecord", back_populates="project", cascade="all, delete-orphan")

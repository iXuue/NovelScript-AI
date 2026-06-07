from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_list_type = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))


class ChapterSummary(Base):
    __tablename__ = "chapter_summaries"
    __table_args__ = (UniqueConstraint("project_id", "chapter_id", name="uq_chapter_summaries_project_chapter_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    characters: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    locations: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    conflicts: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    foreshadowing: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    adaptation_suggestions: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    narrative_function: Mapped[str] = mapped_column(Text, nullable=False)
    dialogue_candidates: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    visual_elements: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    emotional_beats: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="chapter_summaries")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("project_id", "evidence_id", name="uq_evidence_items_project_evidence_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(40), nullable=False)
    chapter_id: Mapped[str] = mapped_column(String(40), nullable=False)
    paragraph_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    paragraph_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    related_characters: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    related_locations: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    related_plot_points: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    importance: Mapped[int] = mapped_column(Integer, nullable=False)
    must_keep: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="evidence_items")

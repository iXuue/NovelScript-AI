from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_list_type = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))


class StoryBible(Base):
    __tablename__ = "story_bibles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_story_bibles_project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    story_type: Mapped[str] = mapped_column(String(120), nullable=False)
    tone: Mapped[str] = mapped_column(String(200), nullable=False)
    logline: Mapped[str] = mapped_column(Text, nullable=False)
    theme: Mapped[str] = mapped_column(Text, nullable=False)
    main_characters: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    relationships: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    locations: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    timeline: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    central_conflict: Mapped[str] = mapped_column(Text, nullable=False)
    foreshadowing: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="story_bibles")

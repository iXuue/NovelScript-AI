from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_list_type = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))


class StyleSourceRecord(Base):
    __tablename__ = "style_sources"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    builtin_style: Mapped[str | None] = mapped_column(String(80), nullable=True)
    style_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_file_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="style_source")


class StyleReferenceFile(Base):
    __tablename__ = "style_reference_files"
    __table_args__ = (UniqueConstraint("project_id", "file_id", name="uq_style_reference_files_project_file_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(40), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="style_reference_files")


class StyleProfile(Base):
    __tablename__ = "style_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_style_profiles_project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    profile_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="style_profiles")

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_list_type = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("project_id", "status", name="uq_script_versions_project_status"),)

    script_version_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="script_versions")
    scenes = relationship("ScriptScene", back_populates="script_version", cascade="all, delete-orphan")
    content_blocks = relationship("ScriptContentBlock", back_populates="script_version", cascade="all, delete-orphan")


class ScriptScene(Base):
    __tablename__ = "script_scenes"
    __table_args__ = (UniqueConstraint("script_version_id", "scene_id", name="uq_script_scenes_version_scene_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    script_version_id: Mapped[str] = mapped_column(ForeignKey("script_versions.script_version_id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(40), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_chapter_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    scene_info: Mapped[str] = mapped_column(Text, nullable=False)
    characters: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    scene_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    core_conflict: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    script_version = relationship("ScriptVersion", back_populates="scenes")


class ScriptContentBlock(Base):
    __tablename__ = "script_content_blocks"
    __table_args__ = (UniqueConstraint("script_version_id", "content_block_id", name="uq_script_blocks_version_block_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    script_version_id: Mapped[str] = mapped_column(ForeignKey("script_versions.script_version_id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(40), nullable=False)
    content_block_id: Mapped[str] = mapped_column(String(60), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_evidence_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    script_version = relationship("ScriptVersion", back_populates="content_blocks")

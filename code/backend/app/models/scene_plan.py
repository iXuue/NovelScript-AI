from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_list_type = MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql"))
json_value_type = JSON().with_variant(JSONB, "postgresql")


class ScenePlan(Base):
    __tablename__ = "scene_plans"
    __table_args__ = (UniqueConstraint("project_id", "version_number", name="uq_scene_plans_project_version"),)

    scene_plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parent_scene_plan_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="scene_plans")
    scenes = relationship("ScenePlanScene", back_populates="scene_plan", cascade="all, delete-orphan")
    validations = relationship("ScenePlanValidation", back_populates="scene_plan", cascade="all, delete-orphan")


class ScenePlanScene(Base):
    __tablename__ = "scene_plan_scenes"
    __table_args__ = (UniqueConstraint("scene_plan_id", "scene_id", name="uq_scene_plan_scenes_plan_scene_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_plan_id: Mapped[str] = mapped_column(ForeignKey("scene_plans.scene_plan_id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(40), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_chapter_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    source_evidence_ids: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    interior_exterior: Mapped[str] = mapped_column(String(40), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    time: Mapped[str] = mapped_column(String(200), nullable=False)
    characters: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    must_cover_plot: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    must_keep_dialogue: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    must_keep_visual_elements: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    must_keep_foreshadowing: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    scene_function: Mapped[str] = mapped_column(Text, nullable=False)
    core_conflict: Mapped[str] = mapped_column(Text, nullable=False)
    adaptation_note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scene_plan = relationship("ScenePlan", back_populates="scenes")


class ScenePlanValidation(Base):
    __tablename__ = "scene_plan_validations"
    __table_args__ = (UniqueConstraint("scene_plan_id", name="uq_scene_plan_validations_scene_plan_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene_plan_id: Mapped[str] = mapped_column(ForeignKey("scene_plans.scene_plan_id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issues: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    suggestions: Mapped[list] = mapped_column(json_list_type, nullable=False, default=list)
    coverage: Mapped[dict] = mapped_column(json_value_type, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scene_plan = relationship("ScenePlan", back_populates="validations")

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_value_type = JSON().with_variant(JSONB, "postgresql")


class FeedbackPlanCacheEntry(Base):
    __tablename__ = "feedback_plan_cache_entries"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "stage",
            "target_type",
            "scope_id",
            "input_hash",
            "artifact_fingerprint",
            name="uq_feedback_plan_cache_context",
        ),
    )

    feedback_plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    scope_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_fingerprint: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    user_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[dict] = mapped_column(json_value_type, nullable=False, default=dict)
    modification_plan: Mapped[dict] = mapped_column(json_value_type, nullable=False, default=dict)
    source_requests: Mapped[list] = mapped_column(json_value_type, nullable=False, default=list)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="feedback_plan_cache_entries")

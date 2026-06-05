from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


json_value_type = JSON().with_variant(JSONB, "postgresql")


class RepairAttempt(Base):
    __tablename__ = "repair_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(60), nullable=False)
    result_artifact_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    scene_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    issues: Mapped[list] = mapped_column(json_value_type, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project = relationship("Project", back_populates="repair_attempts")

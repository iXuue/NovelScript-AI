import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def persistent_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class AppStore:
    counters: dict[str, int] = field(default_factory=dict)
    projects: dict[str, dict] = field(default_factory=dict)
    chapters_pending: dict[str, list[dict]] = field(default_factory=dict)
    chapter_paragraphs: dict[str, list[dict]] = field(default_factory=dict)
    style_sources: dict[str, dict] = field(default_factory=dict)
    style_locked: set[str] = field(default_factory=set)
    style_files: dict[str, dict] = field(default_factory=dict)
    scene_plans: dict[str, dict] = field(default_factory=dict)
    scripts: dict[str, dict] = field(default_factory=dict)
    script_ui: dict[str, dict] = field(default_factory=dict)
    yaml_previews: dict[str, dict] = field(default_factory=dict)
    evidence_by_content_block: dict[str, dict] = field(default_factory=dict)
    conversations: dict[str, list[dict]] = field(default_factory=dict)
    runs: dict[str, dict] = field(default_factory=dict)
    active_run_by_project: dict[str, str] = field(default_factory=dict)
    exports: dict[str, dict] = field(default_factory=dict)

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}_{self.counters[prefix]:03d}"

    def reset(self) -> None:
        self.counters.clear()
        self.projects.clear()
        self.chapters_pending.clear()
        self.chapter_paragraphs.clear()
        self.style_sources.clear()
        self.style_locked.clear()
        self.style_files.clear()
        self.scene_plans.clear()
        self.scripts.clear()
        self.script_ui.clear()
        self.yaml_previews.clear()
        self.evidence_by_content_block.clear()
        self.conversations.clear()
        self.runs.clear()
        self.active_run_by_project.clear()
        self.exports.clear()


STORE = AppStore()


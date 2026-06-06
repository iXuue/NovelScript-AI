import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def persistent_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


_ID_COUNTER_PATTERN = re.compile(r"^[a-z_]+_(\d{3,})$")


def _restore_counter(counters: dict[str, int], prefix: str, value: int) -> None:
    if value > counters.get(prefix, 0):
        counters[prefix] = value


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

    # ── 本地磁盘持久化 ──────────────────────────────────────────

    def save_to_disk(self, data_root: str) -> int:
        """将所有项目数据写入 data/ 目录。返回保存的项目数。"""
        from app.services.local_store import save_project, delete_project_dir

        data_path = Path(data_root)
        data_path.mkdir(parents=True, exist_ok=True)

        saved_ids: set[str] = set()
        count = 0
        for project_id, project in self.projects.items():
            name = project.get("name", project_id)
            save_project(
                data_root=str(data_path),
                project_name=name,
                project=project,
                chapters=self.chapters_pending.get(project_id),
                chapter_paragraphs=self.chapter_paragraphs.get(project_id),
                style_source=self.style_sources.get(project_id),
                scene_plan=self.scene_plans.get(project_id),
                script_internal=self.scripts.get(project_id),
                script_ui=self.script_ui.get(project_id),
                yaml_preview=self.yaml_previews.get(project_id),
                evidence_map=self.evidence_by_content_block if count == 0 else {},
                conversations=self.conversations.get(project_id, []),
                runs={
                    rid: r for rid, r in self.runs.items()
                    if r.get("project_id") == project_id
                },
                exports={
                    eid: e for eid, e in self.exports.items()
                    if e.get("project_id") == project_id
                },
            )
            saved_ids.add(project_id)
            count += 1

        # 清理磁盘上已不存在的项目目录
        for entry in data_path.iterdir():
            if entry.is_dir():
                # 提取目录名中的 project_id
                parts = entry.name.rsplit("_", 1)
                if len(parts) == 2:
                    potential_id = parts[1]
                    matching = [
                        pid for pid in self.projects
                        if pid.endswith(potential_id)
                    ]
                    if matching and matching[0] not in saved_ids:
                        # 项目已被删除，清理目录
                        import shutil
                        shutil.rmtree(entry, ignore_errors=True)

        return count

    def load_from_disk(self, data_root: str) -> int:
        """从 data/ 目录恢复所有项目数据到 STORE。返回加载的项目数。"""
        from app.services.local_store import load_project, discover_projects

        project_dirs = discover_projects(data_root)
        count = 0
        for project_dir in project_dirs:
            data = load_project(project_dir)
            project = data.get("project")
            if project is None:
                continue
            project_id = project.get("project_id")
            if project_id is None:
                continue

            self.projects[project_id] = project

            if data.get("chapters") is not None:
                self.chapters_pending[project_id] = data["chapters"]
            if data.get("paragraphs") is not None:
                self.chapter_paragraphs[project_id] = data["paragraphs"]
            if data.get("style_source") is not None:
                self.style_sources[project_id] = data["style_source"]
            if data.get("scene_plan") is not None:
                sp = data["scene_plan"]
                self.scene_plans[project_id] = sp
                if sp.get("confirmed"):
                    self.style_locked.add(project_id)
            if data.get("script_internal") is not None:
                self.scripts[project_id] = data["script_internal"]
            if data.get("script_ui") is not None:
                self.script_ui[project_id] = data["script_ui"]
            if data.get("yaml_preview") is not None:
                self.yaml_previews[project_id] = data["yaml_preview"]
            if data.get("evidence"):
                self.evidence_by_content_block.update(data["evidence"])
            if data.get("conversations"):
                self.conversations[project_id] = data["conversations"]
            if data.get("runs"):
                for run_id, run in data["runs"].items():
                    self.runs[run_id] = run
                    if run.get("project_id") == project_id and run.get("status") == "running":
                        self.active_run_by_project[project_id] = run_id
            if data.get("exports"):
                for export_id, export in data["exports"].items():
                    self.exports[export_id] = export

            # 恢复计数器
            self._restore_counters_from_ids(project_id)
            count += 1

        # 恢复全局 runs 和 exports 的计数器
        self._restore_counters_from_ids(*self.runs.keys())
        self._restore_counters_from_ids(*self.exports.keys())

        return count

    def _restore_counters_from_ids(self, *ids: str) -> None:
        for id_str in ids:
            m = _ID_COUNTER_PATTERN.search(id_str)
            if m:
                prefix = id_str[:m.start()].rstrip("_")
                if prefix:
                    _restore_counter(self.counters, prefix, int(m.group(1)))


STORE = AppStore()


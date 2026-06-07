# 叙影工坊

项目展示视频：待补充

面向小说影视化改编的章节分析、场景规划、剧本生成与多格式导出系统。

本仓库按资料、需求、计划和可运行代码分层维护。可运行应用位于 `code/`，全局 README 统一说明项目结构、启动方式、导出设计和常见维护注意事项。

## 目录结构

- `code/`：可运行应用代码。
- `code/backend/`：FastAPI 后端、SQLAlchemy 模型、Alembic 迁移、服务层、API 路由和后端测试。
- `code/frontend/`：React + TypeScript + Vite 前端。
- `code/test/`：验收说明和端到端测试入口。
- `doc/`：项目资料、参考文档、调研材料和原始文本。
- `spec/`：需求说明、功能规格、接口约定。
- `plan/`：项目计划、任务安排、里程碑记录。
- `code/docker-compose.yml`：本地 PostgreSQL、后端、前端和测试编排。

## Docker 启动

日常开发和验证优先使用 Docker：

```powershell
cd code
docker compose up --build
```

启动后访问：

- 前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8000/health`

后端 Docker 镜像会自动安装文档转换运行时：

- `libreoffice-writer`：用于旧版 `.doc` 上传解析，以及 `.doc` / `.pdf` 导出。
- `fonts-noto-cjk`：用于 PDF 中文字体。
- `fontconfig`：让 LibreOffice 能发现已安装字体。

使用 Docker 时通常不需要手动配置 LibreOffice。

## 本地后端启动

不使用 Docker 时，需要本机已准备 PostgreSQL、Python 虚拟环境和 LibreOffice。

后端命令必须在 `code/backend` 目录执行：

```powershell
cd code\backend
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

常用后端环境变量：

```powershell
DATABASE_URL=postgresql+psycopg://novelscript:novelscript@localhost:5433/novelscript
STORAGE_ROOT=./storage
SOFFICE_BINARY=soffice
DOCUMENT_CONVERSION_TIMEOUT_SECONDS=60
```

如果 LibreOffice 不在 `PATH` 中，需要把 `SOFFICE_BINARY` 设置为 `soffice` 可执行文件的完整路径，例如：

```powershell
SOFFICE_BINARY=C:\Program Files\LibreOffice\program\soffice.com
```

Windows 本地开发可使用 `winget` 安装 LibreOffice，并配置用户级 `SOFFICE_BINARY`：

```powershell
winget install --id TheDocumentFoundation.LibreOffice -e

[Environment]::SetEnvironmentVariable(
  "SOFFICE_BINARY",
  "C:\Program Files\LibreOffice\program\soffice.exe",
  "User"
)
```

重开 PowerShell 后验证：

```powershell
$env:SOFFICE_BINARY
& $env:SOFFICE_BINARY --version
```

如果还需要直接使用 `soffice` 命令，可把 LibreOffice 程序目录加入用户级 `PATH`：

```powershell
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$libreOfficePath = "C:\Program Files\LibreOffice\program"

if ($currentPath -notlike "*$libreOfficePath*") {
  [Environment]::SetEnvironmentVariable(
    "Path",
    "$currentPath;$libreOfficePath",
    "User"
  )
}
```

## 数据库迁移注意事项

Alembic 命令必须在后端目录执行，否则会出现两类常见错误：

- 在仓库根目录执行 `.\.venv\Scripts\python.exe`，会因为根目录没有 `.venv` 而找不到 Python。
- 在仓库根目录执行 `alembic upgrade head`，会因为找不到正确的 `alembic.ini` 配置而报 `No 'script_location' key found in configuration.`

正确命令：

```powershell
cd code\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

升级后可检查当前迁移版本：

```powershell
cd code\backend
.\.venv\Scripts\python.exe -m alembic current
```

如果生成剧本或镜像快照时报类似 `column chapter_summaries.narrative_function does not exist`，优先检查数据库迁移是否落后于代码版本。该错误通常不是剧本生成逻辑本身失败，而是 ORM 模型已经新增字段、数据库表还没有执行对应迁移。

## 前端启动

```powershell
cd code\frontend
npm install
npm run dev
```

## 测试

Docker 后端测试：

```powershell
cd code
docker compose --profile test run --rm backend-test
```

Docker 前端测试：

```powershell
cd code
docker compose --profile test run --rm frontend-test
```

Docker 前端生产构建：

```powershell
cd code
docker compose --profile test run --rm frontend-build
```

本地后端测试：

```powershell
cd code\backend
pytest tests -q
```

本地前端测试：

```powershell
cd code\frontend
npm test
npm run build
```

## 文件支持

上传：

- 小说上传：`.md`、`.txt`、`.doc`、`.docx`、`.pdf`
- 风格参考上传：`.md`、`.txt`、`.doc`、`.docx`、`.pdf`

导出：

- `yaml`
- `markdown`
- `txt`
- `clean_json`
- `docx`
- `doc`
- `pdf`

PDF 上传依赖嵌入文本抽取。纯扫描图片 PDF 通常需要先 OCR，否则可能没有可用文本。

## 最终 YAML 结构设计

当前最终 YAML 导出由 `code/backend/app/services/export_service.py` 生成。核心流程是：

1. 后端先从当前脚本版本取得内部脚本对象。
2. `to_user_clean_json()` 深拷贝内部对象，并递归移除内部追踪字段。
3. `to_yaml_preview()` 使用 `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)` 输出 YAML，保留字段顺序和中文内容。

导出的顶层结构：

```yaml
title: 剧本标题
characters: []
scenes:
- scene_id: S001
  title: 场景标题
  source_chapter_ids:
  - CH001
  scene_info: 场景信息
  characters:
  - 角色名
  scene_purpose: 场景目的
  core_conflict: 核心冲突
  content_blocks:
  - type: action
    text: 动作或叙述文本
    speaker: null
    parenthetical: null
  - type: dialogue
    text: 台词文本
    speaker: 角色名
    parenthetical: null
```

### 字段设计

- `title`：整部剧本标题，便于导出文件被独立打开时仍能识别项目。
- `characters`：全局角色列表，目前保留为空数组或后续扩展入口，避免未来增加全局角色表时破坏顶层结构。
- `scenes`：场景数组，按生成顺序排列，是剧本的主体。
- `scene_id`：稳定场景编号，例如 `S001`。保留它是为了让前端、修复流程和人工审阅能定位场景。
- `title`：场景标题，用于阅读、目录和文档导出。
- `source_chapter_ids`：场景来源章节编号。它保留章节级来源，但不暴露更细的段落追踪字段。
- `scene_info`：场景综合信息，通常包含内外景、地点和时间。
- `characters`：该场景出场角色。
- `scene_purpose`：场景在叙事中的功能。
- `core_conflict`：该场景的核心冲突。
- `content_blocks`：场景正文块，按剧本阅读顺序排列。
- `type`：正文块类型，例如 `action`、`dialogue`、`narration`、`transition`、`note`。
- `text`：正文内容。
- `speaker`：对白说话人；非对白块为 `null`。
- `parenthetical`：对白表演提示；没有提示时为 `null`。

### 为什么这样设计

YAML 导出面向用户阅读、人工修改和下游工具处理，因此采用“可读剧本结构”而不是完整内部数据库结构。

内部脚本对象里包含 `content_block_id`、`source_paragraph_ids`、`source_evidence_ids`、`paragraph_id`、`paragraph_ids`、`traceability_index` 等追踪字段。这些字段对校验、修复和证据回溯有用，但会让导出文件变得臃肿，并暴露内部实现细节。最终 YAML 会移除这些字段，只保留读者和编辑真正需要的剧本内容、场景元数据和正文块。

`yaml`、`markdown`、`txt` 当前共享同一个清理后的 YAML 主体。这样做的原因是保持文本导出的一致性：同一份脚本在不同纯文本格式下字段结构一致，减少前端预览、下载和后续比对时的偏差。

`clean_json` 与 YAML 使用同一个清理逻辑，只是输出格式换成 JSON。这保证 YAML 和 JSON 都是“用户可见版本”，而不是数据库内部版本。

`docx`、`doc`、`pdf` 则基于同一个清理后的结构重新排版成文档：场景标题作为二级标题，场景信息、出场人物、场景目的和核心冲突作为元数据段落，正文块按 `speaker: line` 或 `type: text` 的方式渲染。

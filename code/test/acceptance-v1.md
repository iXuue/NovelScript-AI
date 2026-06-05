# NovelScript AI V1 Acceptance Skeleton

本文件记录跨端验收入口。当前代码骨架已覆盖：

- 新建项目。
- 小说上传并识别章节。
- 章节确认。
- 三选一风格来源。
- Scene Plan 生成与显式确认。
- 确认后风格锁定。
- 剧本生成与 YAML 只读预览。
- content block 来源证据查询。
- clean export 去除内部追溯字段。
- run / run_step stub 记录。

后续完整验收应把 `backend/tests/integration/test_mvp_flow.py` 与前端浏览器测试串联，覆盖真实 PostgreSQL、Docker Compose 和前端交互。


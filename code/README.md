# NovelScript AI Code

本目录是仓库内的代码区。

## 目录

- `backend/`: FastAPI 后端骨架、领域 DTO、服务层、接口路由和测试。
- `frontend/`: React + TypeScript + Vite 三栏工作台骨架。
- `test/`: 跨端验收说明和后续端到端脚本入口。
- `docker-compose.yml`: 本地 PostgreSQL、后端和前端编排入口。

## 当前骨架边界

当前版本提供可运行的 deterministic stub MVP，用于确认前后端接口形状、页面结构和主流程。服务层暂以进程内存仓库串联流程，同时保留 SQLAlchemy、Alembic、PostgreSQL 和 Docker 入口，后续可将服务层替换为正式持久化实现。

## 验证

后端：

```powershell
cd E:\七牛云\code\backend
pytest tests -q
```

前端依赖安装后：

```powershell
cd E:\七牛云\code\frontend
npm install
npm test
npm run build
```


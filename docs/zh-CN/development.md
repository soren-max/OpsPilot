# 开发指南（Development）

[English](../development.md) | [简体中文](development.md)

## 前置条件

- Git
- Python 3.13（当前已验证的运行时）
- uv
- Node.js 22+ 与 npm
- Docker 与 Ansible 仅用于可选的集成工作

## 环境设置

```bash
git clone https://github.com/soren-max/OpsPilot.git
cd OpsPilot
cp .env.example .env
uv sync --project backend --extra dev
cd frontend && npm ci
```

在本地替换所有 `.env` 占位符。切勿提交 `.env` 或凭据。

## 后端

```bash
uv run --project backend uvicorn app.main:app --reload --app-dir backend
```

## 前端

```bash
cd frontend
npm run dev
```

## 数据库

SQLite 是开发环境的默认数据库。从 `backend` 目录应用迁移：

```bash
uv run --project backend alembic -c backend/alembic.ini upgrade head
```

## 测试、Lint 与类型检查

```bash
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend/app backend/tests
uv run --project backend mypy backend/app

cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

每次提交公开 PR 之前，请从仓库根目录运行 `python scripts/check-secrets.py`。

## 分支工作流

使用 `git pull --ff-only` 更新 `main`，然后创建聚焦的分支。不要在 `main` 上开发或强制推送。

## 提交规范

使用 Conventional Commits（约定式提交）并保持每个提交可评审：`feat:`、`fix:`、`refactor:`、`test:`、`docs:`、`ci:`、`chore:` 或 `build:`。不要在准备评审的分支中使用 WIP 提交。

## PR 流程

先打开 Draft PR，填写模板，等待所有必需的 CI 任务通过，审查完整的 diff 与提交历史，然后才将其标记为 ready。何时以及如何合并由项目所有者决定。

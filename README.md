# HUST Football 裁判管理系统

[![Tests](https://github.com/valleox/hustfootball/actions/workflows/tests.yml/badge.svg)](https://github.com/valleox/hustfootball/actions/workflows/tests.yml)

足协裁判管理系统，用于录入比赛、安排裁判、发布排班、收集裁判确认或请假，并导出裁判安排表。

网址：https://hustfootball.vercel.app

## 功能

- **比赛管理**：录入和修改比赛（赛事、轮次、开球时间、主客队、场地、比赛状态）。
- **裁判排班**：为每场比赛安排主裁判、第一/第二助理裁判和第四官员。
  - 同一场比赛不能重复安排同一名裁判。
  - 同一裁判在开球前后 2 小时内已有其他比赛时提示时间冲突（已取消的比赛除外）。
  - 已发布的安排被修改后自动退回草稿，只重置被更换岗位的反馈。
- **发布安排**：四个岗位全部安排后才能发布；已取消或已结束的比赛不能发布。
  草稿阶段只有排班管理员能看到裁判名单。
- **裁判反馈**：裁判登录后在首页看到自己已发布的安排，可以确认参加或申请请假（请假必须填写原因）。
- **请假处理**：排班管理员首页列出近期所有请假申请，可直接进入更换裁判。
- **Excel 导出**：导出全部已发布的裁判安排表。
- **账号安全**：用户可自行修改密码；同一用户名连续 5 次登录失败后锁定 15 分钟。
- **管理后台**：`/admin/` 维护赛事、球队、场地、裁判资料和用户账号。

## 角色与权限

| 角色 | 可以做什么 |
| --- | --- |
| 裁判员 | 查看比赛；查看自己的已发布安排并确认或请假 |
| 场次录入员 | 裁判员的权限 + 录入和修改赛事、球队、场地、比赛 |
| 排班管理员 | 场次录入员的权限 + 安排裁判、发布安排、处理请假、导出 Excel |

角色由 `python manage.py setup_roles` 创建（可重复执行）。
在后台为用户创建「裁判资料」时，会自动把该用户加入裁判员组。

## 技术栈

- Python 3.13、Django 6.0
- PostgreSQL 17（线上为 Neon）、psycopg
- django-axes（登录失败限制）、openpyxl（Excel 导出）
- 部署：Vercel（新加坡区域）；也保留 Docker Compose + gunicorn + whitenoise 配置，可在自有服务器上运行
- CI：GitHub Actions 在每次推送和 PR 时运行全部测试

## 本地开发

```bash
cd web
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py test --settings=config.test_settings
```

测试使用内存 SQLite（`config.test_settings`），不需要数据库；该配置不可用于部署。
连接真实数据库运行时，需要设置 `DJANGO_SECRET_KEY` 和 `DATABASE_URL`（或 `POSTGRES_*`）等环境变量，
完整列表见 [.env.example](.env.example)。

## 部署

- **Vercel + Neon**：环境变量、数据库迁移和手动部署步骤见 [docs/VERCEL_NEON.md](docs/VERCEL_NEON.md)。
  推送到 `main` 自动部署到正式网址，其他分支生成 Preview。
- **Docker Compose**：复制 `.env.example` 为 `.env` 并填写后运行 `docker compose up -d --build`。
  服务器环境与备份说明见 [docs/SETUP_RECORD.md](docs/SETUP_RECORD.md)。

修改模型或新增依赖带有数据表时，请先对数据库执行 `python manage.py migrate`，再部署新代码。

## 项目结构

```text
hustfootball/
├── .github/workflows/tests.yml   # CI
├── compose.yaml                  # Docker Compose 部署
├── deploy/systemd/               # 自有服务器的每日备份定时任务
├── docs/                         # 部署与搭建记录
├── scripts/backup-database.sh
└── web/
    ├── config/                   # Django 设置与路由
    ├── scheduling/               # 业务模型、视图、表单、测试
    ├── templates/                # 页面模板
    ├── requirements.txt
    └── vercel.json
```

## 计划

- 发布安排或收到请假时发送通知
- Preview 环境使用独立的 Neon 数据库分支
- 自动排班

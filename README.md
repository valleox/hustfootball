# HUST Football 裁判管理系统

足协裁判管理系统，用于录入比赛、安排裁判、发布排班、收集确认状态，并导出裁判安排。

网址：https://hustfootball.vercel.app（部署在 Vercel，数据库为 Neon PostgreSQL）。

> 下方「当前进度」等章节保留了 2026 年 8 月的初版记录；之后已完成用户页面、
> 排班发布、裁判确认/请假和 Excel 导出，部署方式见 [docs/VERCEL_NEON.md](docs/VERCEL_NEON.md)。
> 仓库仍保留 Docker Compose 配置，可在自有服务器上运行。

## 当前进度

截至 2026 年 8 月 17 日，已经完成：

- Django 项目基础结构
- PostgreSQL 数据库连接
- Docker Compose 部署
- 比赛、队伍、场地、赛事、裁判资料和裁判安排等基础模型
- 数据库首次迁移
- Django 后台管理
- 裁判员、场次录入员和排班管理员用户组
- 基础权限配置命令

后续功能仍在开发中。

## 计划功能

- 录入和维护比赛信息
- 安排主裁、两名边裁和第四官员
- 支持现场裁判和裁判组
- 发布裁判安排
- 裁判确认或请假
- 所有角色查看当前确认情况
- 按权限区分场次录入员和排班管理员
- 导出 Excel 裁判安排表
- 后续增加自动排班功能

## 技术环境

- Raspberry Pi 5
- Docker Compose
- Python 3.13
- Django 6.0
- PostgreSQL 17
- psycopg
- openpyxl

## 项目结构

```text
referee-system/
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
└── web/
    ├── Dockerfile
    ├── manage.py
    ├── requirements.txt
    ├── config/
    └── scheduling/
```

## Vercel + Neon 部署

部署配置、环境变量与迁移步骤见
[docs/VERCEL_NEON.md](docs/VERCEL_NEON.md)。Vercel Root Directory 为 `web`。

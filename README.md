# Referee System

足协裁判管理系统，用于录入比赛、安排裁判、发布排班、收集确认状态，并导出裁判安排。

项目目前处于基础功能开发阶段，运行在 Raspberry Pi 的 Docker 环境中。

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

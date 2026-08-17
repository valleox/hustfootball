# Referee System 搭建记录

本文记录足协裁判管理系统的服务器环境、项目结构、已完成工作和重要注意事项。

最后更新日期为 2026 年 8 月 17 日。

## 一、服务器环境

- 设备：Raspberry Pi 5，2GB 内存
- 项目目录：`/home/lucas/referee-system`
- 容器管理：Docker Compose
- 网站端口：8000
- 数据库：PostgreSQL 17
- 后端框架：Django 6.0
- Python：3.13
- 当前阶段：开发和测试

项目当前使用 Django 开发服务器。正式上线前需要更换为生产级服务，并配置反向代理和 HTTPS。

## 二、Docker 服务

项目包含两个服务。

### db

数据库服务使用：

```text
postgres:17-alpine

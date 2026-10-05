# Vercel + Neon 测试环境

此仓库是 https://github.com/valleox/referee-system 的独立副本，保留 Git 历史。
原 Raspberry Pi 项目与数据库不参与本测试环境的部署。

## Vercel 配置

- 仓库：valleox/referee-system-vercel-test
- Root Directory：web
- Framework Preset：Django
- Python：3.13（web/.python-version）
- 静态文件由 Vercel 自动 collectstatic 并通过 CDN 提供。
- 首页为用户面板（未登录跳转 /accounts/login/），后台仍在 /admin/。
- VERCEL=1 时强制开启 HTTPS 相关设置，DJANGO_HTTPS_ENABLED 不需要设置；
  静态文件使用 Django 默认存储，whitenoise 只用于 Docker 部署。

环境变量（测试项目的 Production 与 Preview 都必须使用测试库）：

| 变量 | 值 |
| --- | --- |
| DJANGO_SECRET_KEY | 测试环境独立随机密钥 |
| DJANGO_DEBUG | 0 |
| DATABASE_URL | Neon pooled URL，包含 sslmode=require |
| DJANGO_ALLOWED_HOSTS | 测试站点固定域名，以逗号分隔 |
| DJANGO_CSRF_TRUSTED_ORIGINS | 测试站点完整 HTTPS origin，以逗号分隔 |

Vercel 的系统环境变量会补充本次部署、分支和项目域名。不要填通配域名。
生产与预览均指本测试项目内的环境，不是原树莓派生产环境。

## 数据库迁移

使用 Neon direct URL（无 -pooler），在可信终端临时设置 DATABASE_URL 和
DJANGO_SECRET_KEY 后，从 web 目录运行：

```text
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py createsuperuser
```

迁移不放在 Vercel 构建或请求启动阶段，避免并发构建修改数据库。
不要把连接串、管理员密码、真实裁判资料或原库备份提交到 Git。
初始环境只建表与角色，不复制原库用户或业务数据。

## 检查

```text
python manage.py check
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py test --settings=config.test_settings
```

离线测试使用 SQLite，覆盖页面权限、排班、发布、裁判反馈、Excel 导出和角色初始化。
上线前另用 Neon 验证迁移、PostgreSQL 读写及 HTTPS 登录。
`config.test_settings` 不可用于部署。

## 后续更新

修改并推送此副本；Vercel Git 集成连接此副本。
涉及模型变更时先检查 migration，并对测试库执行迁移再部署。
现有 Docker Compose 仍可使用 POSTGRES_* 环境变量运行。

## 本次部署记录

- 原始提交：2be1d4ffc15e4ed3926b7e671e431a46a134339d
- 测试网址：https://hustfootball.vercel.app（旧网址 https://referee-system-vercel-test.vercel.app 以 308 永久跳转到新网址，路径和参数保留）
- Vercel 项目：vjr6/referee-system-vercel-test
- Vercel 应用运行区域：sin1（新加坡）
- Neon 项目：frosty-term-15429813（aws-ap-southeast-1，PostgreSQL 17）
- 已执行：Django migrate、setup_roles、collectstatic、本地 3 项测试。
- 已验证：HTTPS 管理后台登录、CSS 加载、通过后台创建球队并读回。
- 独立测试管理员：test-admin，随机密码只保存在本地忽略文件 .env.admin.json。
- Neon 账户不允许调整自动休眠参数，保留平台默认设置。
- 自动部署关联状态请以 Vercel 项目的 Git 设置为准。

## 后续手动部署

在仓库根目录运行（显式使用 web 下的配置，确保区域设置生效）：

```text
npx --yes vercel@61.1.0 deploy --prod --yes --scope vjr6 --local-config web/vercel.json
```

Vercel 已关联 GitHub 仓库 valleox/referee-system-vercel-test。
推送到 main 会自动部署到测试网址；其他分支使用 Preview 环境。
两类环境均使用本项目独立的 Neon 测试数据库。

最终已核对部署：dpl_6R5GeqcH3QCPvnvAF8Jr8dTnUX56，状态 Ready，运行区域 sin1。
构建服务器位于 iad1 不影响应用实际运行于 sin1。

## 2026-10-02 合并用户页面

已从 valleox/referee-system 的 feature/user-pages 分支合并：登录与首页、
比赛列表/详情/录入/修改、裁判安排、发布、裁判确认或请假、Excel 导出。
本次没有修改模型、migration 或角色权限，测试库不需要额外操作。树莓派专用的 gunicorn、compose 健康检查与每日备份脚本一并保留，
Vercel 不使用它们。

## 2026-10-02 更换域名

在 Vercel Domains 中添加 hustfootball.vercel.app（Production）。它比旧域名短，
Vercel 会把它作为 VERCEL_PROJECT_PRODUCTION_URL，settings.py 自动加入 ALLOWED_HOSTS，
因此没有修改 DJANGO_ALLOWED_HOSTS / DJANGO_CSRF_TRUSTED_ORIGINS（它们是只写的 Secret）。
同源 HTTPS 登录不需要 CSRF_TRUSTED_ORIGINS。

# Vercel + Neon 测试环境

此仓库是 https://github.com/valleox/referee-system 的独立副本，保留 Git 历史。
原 Raspberry Pi 项目与数据库不参与本测试环境的部署。

## Vercel 配置

- 仓库：valleox/referee-system-vercel-test
- Root Directory：web
- Framework Preset：Django
- Python：3.13（web/.python-version）
- 静态文件由 Vercel 自动 collectstatic 并通过 CDN 提供。
- 首页跳转 /admin/；所有业务数据仍由 Django 后台权限保护。

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

离线测试使用 SQLite，仅用于验证后台路由、登录、创建球队和角色初始化。
上线前另用 Neon 验证迁移、PostgreSQL 读写及 HTTPS 登录。
`config.test_settings` 不可用于部署。

## 后续更新

修改并推送此副本；Vercel Git 集成连接此副本。
涉及模型变更时先检查 migration，并对测试库执行迁移再部署。
现有 Docker Compose 仍可使用 POSTGRES_* 环境变量运行。

## 本次部署记录

- 原始提交：2be1d4ffc15e4ed3926b7e671e431a46a134339d
- 测试网址：https://referee-system-vercel-test.vercel.app
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

截至本次核对，Vercel Git 关联提示缺少 GitHub Login Connection；因此尚未启用
推送自动部署。先在 Vercel 账户设置关联 GitHub valleox，再将本副本关联到项目。

最终已核对部署：dpl_6R5GeqcH3QCPvnvAF8Jr8dTnUX56，状态 Ready，运行区域 sin1。
构建服务器位于 iad1 不影响应用实际运行于 sin1。

# Vercel + Neon 测试环境

此仓库（valleox/hustfootball）是项目的主仓库，从 valleox/referee-system 复制而来并保留 Git 历史。
原仓库已封存，Raspberry Pi 部署暂停使用。

## Vercel 配置

- 仓库：valleox/hustfootball
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

## 部署说明

- 网址：https://hustfootball.vercel.app（旧域名以 308 永久跳转到此网址，路径和参数保留）
- Vercel 应用运行区域：sin1（新加坡），与 Neon 数据库（aws-ap-southeast-1，PostgreSQL 17）相邻。
  构建服务器位于 iad1 不影响应用实际运行区域。
- 初始化时已执行 migrate、setup_roles、collectstatic，并验证 HTTPS 登录与 CSS 加载。
- 管理员账号与密码只保存在本地，不要提交到仓库。
- Neon 免费账户不能调整自动休眠参数，保留平台默认设置。

推送到 main 会自动部署到正式网址；其他分支使用 Preview 环境（需登录 Vercel 才能访问）。
两类环境都使用本项目的 Neon 数据库，Preview 中的操作同样会写入该库。

如需手动部署，在仓库根目录运行（显式使用 web 下的配置，确保区域设置生效）：

```text
npx --yes vercel@61.1.0 deploy --prod --yes --scope <你的 Vercel team> --local-config web/vercel.json
```

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

## 2026-10-08 登录失败限制（需要迁移）

新增 django-axes，会创建登录记录表。合并到 main 之前，先在可信终端用 Neon direct URL
（无 -pooler）对数据库执行一次迁移，否则登录页会因缺少数据表而报错：

```text
python manage.py migrate --noinput
```

迁移只新增 axes 的数据表，不修改现有业务数据；旧代码可以继续使用迁移后的数据库。
注意：Preview 与正式环境共用同一个数据库，迁移前 Preview 上的登录同样会报错。

被锁定的账号可以等待 15 分钟自动解锁，或在后台「登录安全」→「登录失败记录」中删除对应记录。

## Preview 使用独立数据库（Neon 分支）

Preview 部署连接 Neon 的 `preview` 分支，在 Preview 上的测试不会改动正式数据。

一次性设置：

1. Neon 控制台 → 项目 → **Branches** → **Create branch**：名称 `preview`，父分支 `main`。
   选「Current data」会复制当前数据（便于测试）；选「Schema only」只复制表结构。
2. 在 `preview` 分支页面点 **Connect**，打开 **Connection pooling**，复制连接字符串（带 `-pooler`）。
3. Vercel → **Settings** → **Environment Variables** → 编辑 **Preview** 的 `DATABASE_URL`，
   粘贴上一步的连接字符串并保存。Production 的 `DATABASE_URL` 保持不变。
4. 之后新推送的分支会自动使用 `preview` 数据库；已有的 Preview 部署需要 Redeploy 才会切换。

包含新 migration 的改动按以下顺序上线：

1. 用 `preview` 分支的 direct URL（不带 `-pooler`）运行 `python manage.py migrate --noinput`。
2. 推送分支，在 Preview 上测试。
3. 用 `main` 分支的 direct URL 运行同样的迁移。
4. 合并 PR，正式环境自动部署。

需要用最新的正式数据重新测试时，可在 Neon 的 `preview` 分支页面选择 **Reset from parent**。

## 邮件通知

在 Vercel 的 Production（需要时也包括 Preview）设置以下环境变量后重新部署，即可发送邮件通知；
不设置 `EMAIL_HOST` 时只有站内通知。

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| EMAIL_HOST | smtp.qq.com | 163 邮箱为 smtp.163.com，Gmail 为 smtp.gmail.com |
| EMAIL_PORT | 465 | |
| EMAIL_USE_SSL | 1 | 465 端口用 SSL |
| EMAIL_HOST_USER | 你的完整邮箱地址 | |
| EMAIL_HOST_PASSWORD | SMTP 授权码 | 在邮箱设置里开启 SMTP 后生成，不是登录密码 |
| DEFAULT_FROM_EMAIL | 你的完整邮箱地址 | QQ/163 要求与 EMAIL_HOST_USER 相同 |

## 2026-10-09 邀请码注册、工作量统计、通知（需要迁移）

新增 migration `0002_invitecode`、`0003_notification`，按上面的顺序先迁移 `preview`，再迁移 `main`。
邀请码在后台「邀请码」中创建（只有超级管理员能进入后台），把生成的码发给裁判即可。

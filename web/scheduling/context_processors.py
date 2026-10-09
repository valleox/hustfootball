from django.conf import settings


def site(request):
    # 不能叫 site_name：Django 登录页会用当前域名覆盖同名变量。
    return {"org_name": settings.SITE_NAME}


def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    return {
        "unread_notification_count": user.notifications.filter(
            read_at__isnull=True
        ).count(),
    }

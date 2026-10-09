def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    return {
        "unread_notification_count": user.notifications.filter(
            read_at__isnull=True
        ).count(),
    }

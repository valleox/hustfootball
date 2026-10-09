import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

def _match_title(match):
    kickoff = timezone.localtime(match.kickoff_at).strftime("%m月%d日 %H:%M")
    return f"{kickoff} {match.home_team} vs {match.away_team}"


def send_notifications(request, items):
    """items 为 (用户, 标题, 内容, 站内链接) 列表。

    先写入站内通知，再尝试发送邮件；邮件失败只记录日志，不影响业务操作。
    """
    if not items:
        return 0

    Notification.objects.bulk_create(
        Notification(recipient=user, message=message, link=link)
        for user, _subject, message, link in items
    )

    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0

    emails = [
        EmailMessage(
            subject=f"【{settings.SITE_NAME}】{subject}",
            body=(
                f"{message}\n\n"
                f"查看详情：{request.build_absolute_uri(link)}\n\n"
                "此邮件由系统自动发送，请勿直接回复。"
            ),
            to=[user.email],
        )
        for user, subject, message, link in items
        if user.email
    ]
    if not emails:
        return 0

    try:
        return get_connection().send_messages(emails) or 0
    except Exception:
        logger.exception("发送通知邮件失败")
        return 0


def notify_assignments_published(request, match):
    assignments = match.assignments.select_related(
        "referee__user",
    ).order_by("position")
    title = _match_title(match)
    link = reverse("scheduling:match_detail", args=[match.pk])

    items = [
        (
            assignment.referee.user,
            f"新的裁判安排：{title}",
            (
                f"你被安排为{assignment.get_position_display()}："
                f"{title}（{match.venue}）。请登录确认参加或申请请假。"
            ),
            link,
        )
        for assignment in assignments
        if assignment.referee.user.is_active
    ]
    send_notifications(request, items)
    return len(items)


def scheduling_managers():
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__name="排班管理员"))
        .distinct()
    )


def notify_leave_request(request, assignment):
    match = assignment.match
    title = _match_title(match)
    link = reverse("scheduling:assignment_update", args=[match.pk])
    message = (
        f"{assignment.referee.name} 申请请假："
        f"{title}（{assignment.get_position_display()}）。"
        f"说明：{assignment.response_note}"
    )

    items = [
        (user, f"请假申请：{title}", message, link)
        for user in scheduling_managers()
        if user.pk != assignment.referee.user_id
    ]
    send_notifications(request, items)
    return len(items)

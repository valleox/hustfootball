"""发布裁判安排的统一入口：前台单场、前台批量、后台都使用这里的规则和通知。"""

from django.db import transaction
from django.utils import timezone

from .models import Assignment, Match
from .notifications import notify_assignments_published


def publish_problem(match):
    """返回不能发布的原因；可以发布时返回 None。"""
    if match.assignment_status == Match.AssignmentStatus.PUBLISHED:
        return "本场裁判安排已经发布。"

    if match.status != Match.Status.SCHEDULED:
        return f"本场比赛{match.get_status_display()}，不能发布裁判安排。"

    assigned = set(match.assignments.values_list("position", flat=True))
    missing = [
        label
        for position, label in Assignment.Position.choices
        if position not in assigned
    ]
    if missing:
        return f"还不能发布，以下岗位尚未安排：{'、'.join(missing)}。"

    return None


def mark_published(match):
    match.assignment_status = Match.AssignmentStatus.PUBLISHED
    match.published_at = timezone.now()
    match.save(
        update_fields=["assignment_status", "published_at", "updated_at"]
    )


def publish_match(request, match):
    """检查并发布一场比赛，成功时通知裁判。

    返回 (是否发布, 已通知裁判数, 失败原因)。
    """
    with transaction.atomic():
        match = Match.objects.select_for_update().get(pk=match.pk)
        problem = publish_problem(match)
        if problem:
            return False, 0, problem
        mark_published(match)

    return True, notify_assignments_published(request, match), None


def match_label(match):
    kickoff = timezone.localtime(match.kickoff_at).strftime("%m月%d日 %H:%M")
    return f"{kickoff} {match.home_team} vs {match.away_team}"


def publish_matches(request, matches):
    """批量发布，返回 (已发布场数, 已通知人数, [未发布说明])。"""
    published = notified = 0
    skipped = []

    for match in matches:
        ok, count, problem = publish_match(request, match)
        if ok:
            published += 1
            notified += count
        else:
            skipped.append(f"{match_label(match)}：{problem}")

    return published, notified, skipped

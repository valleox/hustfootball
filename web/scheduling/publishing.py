"""发布裁判安排的统一入口：前台单场、前台批量、后台都使用这里的规则和通知。"""

from django.db import transaction
from django.utils import timezone

from .models import Assignment, Match
from .notifications import notify_assignments_published, notify_match_changed


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


def match_snapshot(match):
    """记录修改前的比赛信息，供 after_match_update 比较。"""
    return {
        "kickoff_at": match.kickoff_at,
        "venue_id": match.venue_id,
        "status": match.status,
        "label": match_label(match),
    }


def after_match_update(request, match, previous):
    """已发布比赛修改了时间、场地或状态后，重置确认并通知裁判。

    返回已通知的裁判数；比赛未发布或没有相关变动时返回 0。
    """
    if match.assignment_status != Match.AssignmentStatus.PUBLISHED:
        return 0

    changes = []
    # 前台表单只精确到分钟，秒数差异不算改期。
    kickoff_changed = match.kickoff_at.replace(
        second=0, microsecond=0
    ) != previous["kickoff_at"].replace(second=0, microsecond=0)
    if match.status != previous["status"]:
        if match.status == Match.Status.CANCELLED:
            changes.append("比赛已取消，无需到场")
        elif match.status == Match.Status.SCHEDULED:
            changes.append("比赛恢复正常进行")
    if match.status != Match.Status.CANCELLED:
        if kickoff_changed:
            kickoff = timezone.localtime(match.kickoff_at)
            changes.append(f"开球时间改为 {kickoff:%m月%d日 %H:%M}")
        if match.venue_id != previous["venue_id"]:
            changes.append(f"比赛场地改为 {match.venue}")

    if not changes:
        return 0

    # 时间变了，原来的确认或请假不再适用，需要裁判重新反馈。
    if kickoff_changed and match.status == Match.Status.SCHEDULED:
        match.assignments.exclude(
            response_status=Assignment.ResponseStatus.PENDING
        ).update(
            response_status=Assignment.ResponseStatus.PENDING,
            response_note="",
            responded_at=None,
            updated_at=timezone.now(),
        )

    return notify_match_changed(
        request, match, changes, previous_title=previous["label"]
    )


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

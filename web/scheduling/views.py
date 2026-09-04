from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (
    AssignmentForm,
    AssignmentResponseForm,
    MatchForm,
)
from .models import Assignment, Match


@never_cache
@login_required
def home(request):
    return render(request, "scheduling/home.html")


@login_required
@permission_required("scheduling.view_match", raise_exception=True)
def match_list(request):
    today = timezone.localdate()

    matches = Match.objects.select_related(
        "competition",
        "home_team",
        "away_team",
        "venue",
    )

    context = {
        "upcoming_matches": matches.filter(
            kickoff_at__date__gte=today
        ).order_by("kickoff_at", "id"),
        "past_matches": matches.filter(
            kickoff_at__date__lt=today
        ).order_by("-kickoff_at", "-id"),
    }

    return render(request, "scheduling/match_list.html", context)


@login_required
@permission_required("scheduling.view_match", raise_exception=True)
def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.select_related(
            "competition",
            "home_team",
            "away_team",
            "venue",
            "created_by",
        ).prefetch_related(
            "assignments__referee",
        ),
        pk=pk,
    )

    assignments_by_position = {
        assignment.position: assignment
        for assignment in match.assignments.all()
    }
    assignment_rows = []

    for position, position_name in Assignment.Position.choices:
        assignment = assignments_by_position.get(position)

        assignment_rows.append(
            {
                "position_name": position_name,
                "assignment": assignment,
                "can_respond": (
                    assignment is not None
                    and match.assignment_status
                    == Match.AssignmentStatus.PUBLISHED
                    and assignment.referee.user_id
                    == request.user.id
                ),
            }
        )

    return render(
        request,
        "scheduling/match_detail.html",
        {
            "match": match,
            "assignment_rows": assignment_rows,
        },
    )


@login_required
@permission_required("scheduling.add_match", raise_exception=True)
def match_create(request):
    form = MatchForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        match = form.save(commit=False)
        match.created_by = request.user
        match.save()

        messages.success(request, "比赛已成功录入。")
        return redirect(
            "scheduling:match_detail",
            pk=match.pk,
        )

    return render(
        request,
        "scheduling/match_form.html",
        {
            "form": form,
            "page_title": "录入比赛",
            "submit_label": "保存比赛",
        },
    )


@login_required
@permission_required("scheduling.change_match", raise_exception=True)
def match_update(request, pk):
    match = get_object_or_404(Match, pk=pk)
    form = MatchForm(
        request.POST if request.method == "POST" else None,
        instance=match,
    )

    if request.method == "POST" and form.is_valid():
        match = form.save()
        messages.success(request, "比赛信息已更新。")

        return redirect(
            "scheduling:match_detail",
            pk=match.pk,
        )

    return render(
        request,
        "scheduling/match_form.html",
        {
            "form": form,
            "match": match,
            "page_title": "修改比赛",
            "submit_label": "保存修改",
        },
    )

@login_required
@permission_required(
    (
        "scheduling.add_assignment",
        "scheduling.change_assignment",
    ),
    raise_exception=True,
)
def assignment_update(request, pk):
    match = get_object_or_404(
        Match.objects.select_related(
            "competition",
            "home_team",
            "away_team",
            "venue",
        ),
        pk=pk,
    )
    form = AssignmentForm(
        request.POST if request.method == "POST" else None,
        match=match,
    )

    if request.method == "POST" and form.is_valid():
        was_published = (
            match.assignment_status
            == Match.AssignmentStatus.PUBLISHED
        )
        changed = form.save(assigned_by=request.user)

        if changed and was_published:
            messages.success(
                request,
                "裁判安排已保存，原安排已退回草稿，"
                "请检查后重新发布。",
            )
        elif changed:
            messages.success(request, "裁判安排已保存。")
        else:
            messages.info(request, "裁判安排没有变化。")

        return redirect(
            "scheduling:match_detail",
            pk=match.pk,
        )

    return render(
        request,
        "scheduling/assignment_form.html",
        {
            "form": form,
            "match": match,
        },
    )

@login_required
@permission_required(
    "scheduling.publish_assignments",
    raise_exception=True,
)
@require_POST
def assignment_publish(request, pk):
    match = get_object_or_404(Match, pk=pk)

    if (
        match.assignment_status
        == Match.AssignmentStatus.PUBLISHED
    ):
        messages.info(request, "本场裁判安排已经发布。")
        return redirect(
            "scheduling:match_detail",
            pk=match.pk,
        )

    required_positions = {
        position
        for position, _label in Assignment.Position.choices
    }
    assigned_positions = set(
        match.assignments.values_list(
            "position",
            flat=True,
        )
    )
    missing_positions = required_positions - assigned_positions

    if missing_positions:
        position_labels = dict(Assignment.Position.choices)
        missing_labels = [
            position_labels[position]
            for position in sorted(missing_positions)
        ]
        messages.error(
            request,
            "还不能发布，以下岗位尚未安排："
            f"{'、'.join(missing_labels)}。",
        )
        return redirect(
            "scheduling:match_detail",
            pk=match.pk,
        )

    match.assignment_status = Match.AssignmentStatus.PUBLISHED
    match.published_at = timezone.now()
    match.save(
        update_fields=[
            "assignment_status",
            "published_at",
            "updated_at",
        ]
    )

    messages.success(request, "裁判安排已经发布。")
    return redirect(
        "scheduling:match_detail",
        pk=match.pk,
    )


@login_required
def assignment_respond(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            "match",
            "match__competition",
            "match__home_team",
            "match__away_team",
            "match__venue",
            "referee",
            "referee__user",
        ),
        pk=pk,
    )

    if assignment.referee.user_id != request.user.id:
        raise PermissionDenied("不能反馈其他裁判的安排。")

    if (
        assignment.match.assignment_status
        != Match.AssignmentStatus.PUBLISHED
    ):
        messages.error(
            request,
            "该场裁判安排尚未发布，暂时不能反馈。",
        )
        return redirect(
            "scheduling:match_detail",
            pk=assignment.match_id,
        )

    form = AssignmentResponseForm(
        request.POST if request.method == "POST" else None,
        instance=assignment,
    )

    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.responded_at = timezone.now()
        assignment.save(
            update_fields=[
                "response_status",
                "response_note",
                "responded_at",
                "updated_at",
            ]
        )

        if (
            assignment.response_status
            == Assignment.ResponseStatus.CONFIRMED
        ):
            messages.success(request, "已经确认参加本场执法。")
        else:
            messages.success(request, "请假申请已经提交。")

        return redirect(
            "scheduling:match_detail",
            pk=assignment.match_id,
        )

    return render(
        request,
        "scheduling/assignment_response_form.html",
        {
            "assignment": assignment,
            "form": form,
        },
    )

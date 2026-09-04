from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import AssignmentForm, MatchForm
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
    assignment_rows = [
        {
            "position_name": position_name,
            "assignment": assignments_by_position.get(position),
        }
        for position, position_name in Assignment.Position.choices
    ]

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

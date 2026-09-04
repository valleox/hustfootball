from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import Match


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
        ),
        pk=pk,
    )

    return render(
        request,
        "scheduling/match_detail.html",
        {"match": match},
    )

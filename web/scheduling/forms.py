from django import forms
from django.db.models import Q

from .models import Competition, Match, Team, Venue


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = (
            "competition",
            "match_number",
            "round_name",
            "kickoff_at",
            "home_team",
            "away_team",
            "venue",
            "match_level",
            "status",
            "notes",
        )
        widgets = {
            "kickoff_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["kickoff_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        self.fields["competition"].queryset = (
            self._active_or_current(
                Competition,
                self.instance.competition_id,
            )
        )
        self.fields["home_team"].queryset = (
            self._active_or_current(
                Team,
                self.instance.home_team_id,
            )
        )
        self.fields["away_team"].queryset = (
            self._active_or_current(
                Team,
                self.instance.away_team_id,
            )
        )
        self.fields["venue"].queryset = (
            self._active_or_current(
                Venue,
                self.instance.venue_id,
            )
        )

        self.fields["competition"].empty_label = "请选择赛事"
        self.fields["home_team"].empty_label = "请选择主队"
        self.fields["away_team"].empty_label = "请选择客队"
        self.fields["venue"].empty_label = "请选择比赛场地"

    @staticmethod
    def _active_or_current(model, current_id):
        condition = Q(is_active=True)

        if current_id:
            condition |= Q(pk=current_id)

        return model.objects.filter(condition)

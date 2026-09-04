from django import forms
from django.db import transaction
from django.db.models import Q

from .models import (
    Assignment,
    Competition,
    Match,
    RefereeProfile,
    Team,
    Venue,
)


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

class AssignmentForm(forms.Form):
    referee = forms.ModelChoiceField(
        label="主裁判",
        queryset=RefereeProfile.objects.none(),
        required=False,
        empty_label="暂不安排",
    )
    assistant_1 = forms.ModelChoiceField(
        label="第一助理裁判",
        queryset=RefereeProfile.objects.none(),
        required=False,
        empty_label="暂不安排",
    )
    assistant_2 = forms.ModelChoiceField(
        label="第二助理裁判",
        queryset=RefereeProfile.objects.none(),
        required=False,
        empty_label="暂不安排",
    )
    fourth_official = forms.ModelChoiceField(
        label="第四官员",
        queryset=RefereeProfile.objects.none(),
        required=False,
        empty_label="暂不安排",
    )

    position_fields = (
        ("referee", Assignment.Position.REFEREE),
        ("assistant_1", Assignment.Position.ASSISTANT_1),
        ("assistant_2", Assignment.Position.ASSISTANT_2),
        (
            "fourth_official",
            Assignment.Position.FOURTH_OFFICIAL,
        ),
    )

    def __init__(self, *args, match, **kwargs):
        super().__init__(*args, **kwargs)
        self.match = match

        assignments = {
            assignment.position: assignment
            for assignment in match.assignments.select_related(
                "referee"
            )
        }
        current_referee_ids = [
            assignment.referee_id
            for assignment in assignments.values()
        ]

        referee_queryset = RefereeProfile.objects.filter(
            Q(is_active=True) | Q(pk__in=current_referee_ids)
        ).order_by("name")

        for field_name, position in self.position_fields:
            self.fields[field_name].queryset = referee_queryset

            assignment = assignments.get(position)
            if assignment:
                self.fields[field_name].initial = (
                    assignment.referee_id
                )

    def clean(self):
        cleaned_data = super().clean()
        selected_referees = {}

        for field_name, _position in self.position_fields:
            referee = cleaned_data.get(field_name)

            if referee is None:
                continue

            previous_field = selected_referees.get(referee.pk)
            if previous_field:
                previous_label = self.fields[
                    previous_field
                ].label
                self.add_error(
                    field_name,
                    f"该裁判已经被安排为{previous_label}。",
                )
            else:
                selected_referees[referee.pk] = field_name

        return cleaned_data

    @transaction.atomic
    def save(self, *, assigned_by):
        existing_assignments = {
            assignment.position: assignment
            for assignment in self.match.assignments.select_for_update()
        }
        changed_positions = []

        for field_name, position in self.position_fields:
            selected_referee = self.cleaned_data[field_name]
            existing = existing_assignments.get(position)

            old_referee_id = (
                existing.referee_id if existing else None
            )
            new_referee_id = (
                selected_referee.pk
                if selected_referee
                else None
            )

            if old_referee_id != new_referee_id:
                changed_positions.append(
                    (position, selected_referee)
                )

        if not changed_positions:
            return False

        changed_position_values = [
            position
            for position, _referee in changed_positions
        ]

        self.match.assignments.filter(
            position__in=changed_position_values
        ).delete()

        Assignment.objects.bulk_create(
            [
                Assignment(
                    match=self.match,
                    referee=referee,
                    position=position,
                    assigned_by=assigned_by,
                    response_status=(
                        Assignment.ResponseStatus.PENDING
                    ),
                    response_note="",
                    responded_at=None,
                )
                for position, referee in changed_positions
                if referee is not None
            ]
        )

        if (
            self.match.assignment_status
            == Match.AssignmentStatus.PUBLISHED
        ):
            self.match.assignment_status = (
                Match.AssignmentStatus.DRAFT
            )
            self.match.published_at = None
            self.match.save(
                update_fields=[
                    "assignment_status",
                    "published_at",
                    "updated_at",
                ]
            )

        return True

class AssignmentResponseForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = (
            "response_status",
            "response_note",
        )
        labels = {
            "response_status": "反馈结果",
            "response_note": "反馈说明",
        }
        widgets = {
            "response_note": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "申请请假时，请填写具体原因。"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["response_status"].choices = [
            ("", "请选择反馈结果"),
            (
                Assignment.ResponseStatus.CONFIRMED,
                "确认参加执法",
            ),
            (
                Assignment.ResponseStatus.LEAVE,
                "申请请假",
            ),
        ]

    def clean(self):
        cleaned_data = super().clean()
        response_status = cleaned_data.get("response_status")
        response_note = cleaned_data.get("response_note", "").strip()

        if (
            response_status
            == Assignment.ResponseStatus.LEAVE
            and not response_note
        ):
            self.add_error(
                "response_note",
                "申请请假时必须填写说明。",
            )

        cleaned_data["response_note"] = response_note
        return cleaned_data

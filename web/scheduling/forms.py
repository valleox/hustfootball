from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, F
from django.db.models import Q
from django.utils import timezone

from .models import (
    Assignment,
    Competition,
    InviteCode,
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

# 同一裁判两场比赛的开球时间间隔小于此值时视为冲突。
ASSIGNMENT_CONFLICT_WINDOW = timedelta(hours=2)


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

        # 显示每名裁判在本赛事其他比赛中的场次，方便平均分配。
        referee_queryset = RefereeProfile.objects.filter(
            Q(is_active=True) | Q(pk__in=current_referee_ids)
        ).annotate(
            competition_total=Count(
                "assignments",
                filter=Q(
                    assignments__match__competition_id=(
                        match.competition_id
                    )
                )
                & ~Q(assignments__match=match)
                & ~Q(
                    assignments__match__status=(
                        Match.Status.CANCELLED
                    )
                ),
            )
        ).order_by("name")

        for field_name, position in self.position_fields:
            self.fields[field_name].queryset = referee_queryset
            self.fields[field_name].label_from_instance = (
                lambda referee: (
                    f"{referee.name}"
                    f"（本赛事已排 {referee.competition_total} 场）"
                )
            )

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

        self._check_time_conflicts(cleaned_data)
        return cleaned_data

    def _check_time_conflicts(self, cleaned_data):
        """只检查本次新安排的裁判，避免旧数据阻止保存其他岗位。"""
        if self.match.status == Match.Status.CANCELLED:
            return

        current_referees = {
            assignment.position: assignment.referee_id
            for assignment in self.match.assignments.all()
        }
        changed_fields = {}

        for field_name, position in self.position_fields:
            referee = cleaned_data.get(field_name)
            if (
                referee is not None
                and field_name not in self.errors
                and current_referees.get(position) != referee.pk
            ):
                changed_fields[referee.pk] = field_name

        if not changed_fields:
            return

        kickoff = self.match.kickoff_at
        conflicts = (
            Assignment.objects.filter(
                referee_id__in=changed_fields,
                match__kickoff_at__gt=(
                    kickoff - ASSIGNMENT_CONFLICT_WINDOW
                ),
                match__kickoff_at__lt=(
                    kickoff + ASSIGNMENT_CONFLICT_WINDOW
                ),
            )
            .exclude(match=self.match)
            .exclude(match__status=Match.Status.CANCELLED)
            .select_related(
                "match__home_team",
                "match__away_team",
            )
            .order_by("match__kickoff_at")
        )

        reported = set()
        for conflict in conflicts:
            if conflict.referee_id in reported:
                continue
            reported.add(conflict.referee_id)

            other_match = conflict.match
            kickoff_text = timezone.localtime(
                other_match.kickoff_at
            ).strftime("%m月%d日 %H:%M")
            self.add_error(
                changed_fields[conflict.referee_id],
                "时间冲突：该裁判已安排在"
                f"{kickoff_text} "
                f"{other_match.home_team} vs {other_match.away_team}"
                f"（{conflict.get_position_display()}）。",
            )

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
            "response_status": forms.RadioSelect(attrs={"class": "choice-buttons"}),
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


class RefereeSignupForm(UserCreationForm):
    """凭邀请码自助注册裁判账号。"""

    name = forms.CharField(label="姓名", max_length=50)
    email = forms.EmailField(
        label="电子邮箱",
        help_text="用于接收排班通知。",
    )
    phone = forms.CharField(
        label="联系电话",
        max_length=30,
        required=False,
    )
    level = forms.ChoiceField(
        label="裁判等级",
        choices=RefereeProfile.Level.choices,
        initial=RefereeProfile.Level.OTHER,
    )
    invite_code = forms.CharField(
        label="邀请码",
        max_length=40,
        help_text="请向排班管理员索取。",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)

    field_order = (
        "invite_code",
        "username",
        "name",
        "email",
        "phone",
        "level",
        "password1",
        "password2",
    )

    def clean_invite_code(self):
        code = self.cleaned_data["invite_code"].strip().upper()
        invite = InviteCode.objects.filter(code=code).first()

        if invite is None or not invite.is_usable():
            raise forms.ValidationError("邀请码无效或已过期。")

        self.invite = invite
        return code

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        user_model = get_user_model()

        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("该邮箱已经注册过。")

        return email

    @transaction.atomic
    def save(self):
        # 锁定邀请码行，防止并发注册超出使用次数。
        invite = InviteCode.objects.select_for_update().get(
            pk=self.invite.pk
        )
        if not invite.is_usable():
            raise forms.ValidationError("邀请码无效或已过期。")

        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()

        RefereeProfile.objects.create(
            user=user,
            name=self.cleaned_data["name"],
            phone=self.cleaned_data["phone"],
            level=self.cleaned_data["level"],
        )

        referee_group = Group.objects.filter(name="裁判员").first()
        if referee_group is not None:
            user.groups.add(referee_group)

        InviteCode.objects.filter(pk=invite.pk).update(
            used_count=F("used_count") + 1
        )
        return user

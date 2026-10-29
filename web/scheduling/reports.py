"""裁判报告：表单、权限判断与通知。

流程：
- 排班管理员对已发布的比赛「要求提交裁判报告」，默认指定主裁判填写；
- 本场裁判也可以在开球后自行填写（谁先开始谁就是填写人）；
- 填写人可以先保存草稿，提交后排班管理员收到通知，并可下载 Word 版报告。
"""

from django import forms
from django.forms import formset_factory
from django.urls import reverse
from django.utils import timezone

from .models import Assignment, Match, RefereeReport
from .notifications import _match_title, scheduling_managers, send_notifications
from .report_docx import team_name


# ---- 权限 ----
def is_report_manager(user):
    return user.has_perm("scheduling.change_assignment")


def match_referee_profile(user, match):
    """当前用户在本场的裁判资料；不是本场裁判时返回 None。"""
    assignment = (
        match.assignments.select_related("referee")
        .filter(referee__user=user)
        .first()
    )
    return assignment.referee if assignment else None


def report_start_problem(user, match):
    """本场裁判自行开始填写报告前的检查；可以开始时返回 None。"""
    if match.status == Match.Status.CANCELLED:
        return "本场比赛已取消，不需要裁判报告。"
    if match.assignment_status != Match.AssignmentStatus.PUBLISHED:
        return "本场裁判安排尚未发布。"
    if match.kickoff_at > timezone.now():
        return "比赛开球后才能填写裁判报告。"
    if match_referee_profile(user, match) is None:
        return "只有本场裁判可以填写裁判报告。"
    return None


def can_edit_report(user, report):
    return report.author.user_id == user.id or is_report_manager(user)


def can_download_report(user, report):
    return (
        can_edit_report(user, report)
        or match_referee_profile(user, report.match) is not None
    )


def default_author(match):
    """默认由主裁判填写；没有主裁判时取第一个岗位的裁判。"""
    assignment = (
        match.assignments.select_related("referee")
        .order_by("position")
        .first()
    )
    return assignment.referee if assignment else None


# ---- 通知 ----
def notify_report_requested(request, report):
    title = _match_title(report.match)
    link = reverse("scheduling:report_edit", args=[report.match_id])
    send_notifications(
        request,
        [
            (
                report.author.user,
                f"请提交裁判报告：{title}",
                f"排班管理员请你提交 {title}（{report.match.venue}）的裁判报告。",
                link,
            )
        ]
        if report.author.user.is_active
        else [],
    )


def notify_report_submitted(request, report):
    title = _match_title(report.match)
    link = reverse("scheduling:report_edit", args=[report.match_id])
    send_notifications(
        request,
        [
            (
                user,
                f"裁判报告已提交：{title}",
                f"{report.author.name} 已提交 {title} 的裁判报告，可在比赛详情中下载。",
                link,
            )
            for user in scheduling_managers()
            if user.pk != report.author.user_id
        ],
    )


# ---- 表单 ----
class RefereeReportForm(forms.ModelForm):
    class Meta:
        model = RefereeReport
        fields = (
            "home_score",
            "away_score",
            "has_shootout",
            "home_shootout_score",
            "away_shootout_score",
            "winner",
            "sendoff_notes",
            "penalty_notes",
            "error_notes",
            "summary",
        )
        widgets = {
            "home_score": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "away_score": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "home_shootout_score": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "away_shootout_score": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "sendoff_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "没有红牌可留空"}),
            "penalty_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "没有罚球点球可留空"}),
            "error_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "没有可留空"}),
            "summary": forms.Textarea(attrs={"rows": 5}),
            "winner": forms.RadioSelect(attrs={"class": "choice-buttons"}),
        }

    def __init__(self, *args, submitting=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitting = submitting
        match = self.instance.match
        self.fields["home_score"].label = f"{match.home_team}（主队）进球"
        self.fields["away_score"].label = f"{match.away_team}（客队）进球"
        self.fields["home_shootout_score"].label = f"{match.home_team} 点球罚进"
        self.fields["away_shootout_score"].label = f"{match.away_team} 点球罚进"
        self.fields["has_shootout"].label = "本场进入点球决胜"
        self.fields["winner"].choices = [
            (RefereeReport.Winner.HOME, f"{team_name(match.home_team)}（主队）"),
            (RefereeReport.Winner.AWAY, f"{team_name(match.away_team)}（客队）"),
            (RefereeReport.Winner.DRAW, "平局"),
        ]

    def clean(self):
        cleaned_data = super().clean()
        home, away = cleaned_data.get("home_score"), cleaned_data.get("away_score")
        if self.submitting:
            if home is None:
                self.add_error("home_score", "提交前请填写比分。")
            if away is None:
                self.add_error("away_score", "提交前请填写比分。")
            if not cleaned_data.get("summary", "").strip():
                self.add_error("summary", "提交前请填写整场吹罚问题总结。")

        shootout = cleaned_data.get("has_shootout")
        home_pk = cleaned_data.get("home_shootout_score")
        away_pk = cleaned_data.get("away_shootout_score")
        if shootout:
            if home is not None and away is not None and home != away:
                self.add_error("has_shootout", "80 分钟内已分出胜负，不需要点球决胜。")
            if self.submitting:
                if home_pk is None:
                    self.add_error("home_shootout_score", "请填写点球比分。")
                if away_pk is None:
                    self.add_error("away_shootout_score", "请填写点球比分。")
            if home_pk is not None and away_pk is not None and home_pk == away_pk:
                self.add_error("away_shootout_score", "点球决胜必须分出胜负。")
        else:
            # 没有点球决胜时不保留残留的点球数据。
            cleaned_data["home_shootout_score"] = None
            cleaned_data["away_shootout_score"] = None

        # 获胜队必须与比分一致：先看 80 分钟比分，平局再看点球比分。
        expected = self._expected_winner(home, away, shootout, home_pk, away_pk)
        winner = cleaned_data.get("winner")
        if not winner and expected:
            cleaned_data["winner"] = expected
        elif winner and expected and winner != expected:
            self.add_error(
                "winner",
                f"与比分不符，按比分获胜队应为「{dict(self.fields['winner'].choices)[expected]}」。",
            )
        elif self.submitting and not winner:
            self.add_error("winner", "请选择获胜队。")
        return cleaned_data

    @staticmethod
    def _expected_winner(home, away, shootout, home_pk, away_pk):
        if home is None or away is None:
            return None
        if home != away:
            return RefereeReport.Winner.HOME if home > away else RefereeReport.Winner.AWAY
        if not shootout:
            return RefereeReport.Winner.DRAW
        if home_pk is None or away_pk is None or home_pk == away_pk:
            return None
        return RefereeReport.Winner.HOME if home_pk > away_pk else RefereeReport.Winner.AWAY


class _RowForm(forms.Form):
    """一行明细；整行留空时忽略。"""

    required_when_filled = ()

    def is_blank(self):
        return not any(
            str(value).strip()
            for name, value in self.cleaned_data.items()
            if name != "DELETE" and value not in (None, "")
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.is_blank():
            return cleaned_data
        for name in self.required_when_filled:
            if not str(cleaned_data.get(name) or "").strip():
                self.add_error(name, "必填")
        return cleaned_data

    def row(self):
        return {
            name: str(value).strip()
            for name, value in self.cleaned_data.items()
            if name != "DELETE"
        }


class DisciplineRowForm(_RowForm):
    """警告或罚令出场的一行。"""

    required_when_filled = ("team", "number", "minute", "reason")

    team = forms.ChoiceField(label="队名", required=False)
    number = forms.CharField(label="号码", max_length=10, required=False)
    name = forms.CharField(label="队员姓名", max_length=30, required=False)
    minute = forms.CharField(
        label="时间（分钟）",
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "如 44 或 45+2"}),
    )
    reason = forms.CharField(label="原因", max_length=200, required=False)

    def __init__(self, *args, team_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].choices = [("", "—")] + [(name, name) for name in team_choices]


class GoalRowForm(_RowForm):
    required_when_filled = ("minute",)

    name = forms.CharField(label="姓名", max_length=30, required=False)
    number = forms.CharField(label="号码", max_length=10, required=False)
    minute = forms.CharField(
        label="时间（分钟）",
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "如 78"}),
    )


SHOOTOUT_RESULTS = [("", "—"), ("罚进", "罚进"), ("未进", "未进")]


class ShootoutRowForm(_RowForm):
    """点球决胜的一轮：主队罚球队员在左、客队在右；某一方没罚可留空。"""

    home_number = forms.CharField(label="主队号码", max_length=10, required=False)
    home_name = forms.CharField(label="主队姓名", max_length=30, required=False)
    home_result = forms.ChoiceField(label="主队结果", required=False, choices=SHOOTOUT_RESULTS)
    away_number = forms.CharField(label="客队号码", max_length=10, required=False)
    away_name = forms.CharField(label="客队姓名", max_length=30, required=False)
    away_result = forms.ChoiceField(label="客队结果", required=False, choices=SHOOTOUT_RESULTS)

    def clean(self):
        cleaned_data = super().clean()
        for side in ("home", "away"):
            filled = any(
                str(cleaned_data.get(f"{side}_{name}") or "").strip()
                for name in ("number", "name")
            )
            if filled and not cleaned_data.get(f"{side}_result"):
                self.add_error(f"{side}_result", "必填")
        return cleaned_data


DisciplineFormSet = formset_factory(DisciplineRowForm, extra=0, max_num=40)
GoalFormSet = formset_factory(GoalRowForm, extra=0, max_num=40)
ShootoutFormSet = formset_factory(ShootoutRowForm, extra=0, max_num=60)

# 新报告预留的空行数（页面上还可以「添加一行」）
BLANK_ROWS = {
    "cautions": 2,
    "sendoffs": 1,
    "home_goals": 2,
    "away_goals": 2,
    "shootout_kicks": 3,
}
ROW_SECTIONS = (
    ("cautions", "警告队员", DisciplineFormSet),
    ("sendoffs", "罚令出场", DisciplineFormSet),
    ("home_goals", "主队进球队员", GoalFormSet),
    ("away_goals", "客队进球队员", GoalFormSet),
)
SHOOTOUT_SECTION = ("shootout_kicks", "点球决胜罚球记录（每行一轮）", ShootoutFormSet)


def build_row_formsets(report, data=None):
    match = report.match
    team_choices = (team_name(match.home_team), team_name(match.away_team))
    formsets = {}
    for key, _label, formset_class in (*ROW_SECTIONS, SHOOTOUT_SECTION):
        kwargs = {"prefix": key}
        if formset_class is DisciplineFormSet:
            kwargs["form_kwargs"] = {"team_choices": team_choices}
        if data is None:
            rows = list(getattr(report, key) or [])
            rows += [{}] * max(BLANK_ROWS[key] - len(rows), 0)
            kwargs["initial"] = rows
            formsets[key] = formset_class(**kwargs)
        else:
            formsets[key] = formset_class(data, **kwargs)
    return formsets


def formsets_to_validate(formsets, data):
    """没有勾选点球决胜时，隐藏的罚球记录不参与校验。"""
    return [
        formset
        for key, formset in formsets.items()
        if key != SHOOTOUT_SECTION[0] or data.get("has_shootout")
    ]


def apply_row_formsets(report, formsets):
    for key, formset in formsets.items():
        if key == SHOOTOUT_SECTION[0] and not report.has_shootout:
            report.shootout_kicks = []
            continue
        setattr(
            report,
            key,
            [form.row() for form in formset.forms if form.cleaned_data and not form.is_blank()],
        )


def new_report(match, author, *, requested_by=None):
    report = RefereeReport(match=match, author=author)
    if requested_by is not None:
        report.status = RefereeReport.Status.REQUESTED
        report.requested_by = requested_by
        report.requested_at = timezone.now()
    return report


class ReportRequestForm(forms.Form):
    author = forms.ModelChoiceField(
        label="填写裁判",
        queryset=Assignment.objects.none(),
        empty_label=None,
    )

    def __init__(self, *args, match, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["author"].queryset = match.assignments.select_related("referee").order_by("position")
        self.fields["author"].label_from_instance = (
            lambda assignment: f"{assignment.get_position_display()}：{assignment.referee.name}"
        )

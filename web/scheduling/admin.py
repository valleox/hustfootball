from django.conf import settings
from django.apps import apps as django_apps
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.db.models import Prefetch
from django.urls import reverse
from datetime import timedelta

from django.utils.html import format_html, format_html_join
from django.contrib.auth.models import Group
from django.utils import timezone
from django import forms
from django.forms.models import BaseInlineFormSet

from .forms import find_time_conflicts
from .notifications import notify_assignment_removed
from .publishing import (
    after_match_update,
    match_label,
    match_snapshot,
    publish_match,
    publish_matches,
)
from .models import (
    Assignment,
    Competition,
    InviteCode,
    Match,
    MatchAssignmentSummary,
    Notification,
    RefereeProfile,
    Team,
    Venue,
)


admin.site.site_header = f"{settings.SITE_NAME} · 管理后台"
admin.site.site_title = f"{settings.SITE_NAME}管理后台"
admin.site.index_title = "系统管理"
admin.site.site_url = "/"


def update_response_time(assignment, status_changed=False):
    """反馈状态改为待确认时清空回应时间；改为确认或请假时记录当前时间。"""
    if assignment.response_status == Assignment.ResponseStatus.PENDING:
        assignment.responded_at = None
    elif status_changed or assignment.responded_at is None:
        assignment.responded_at = timezone.now()


WEEKDAYS = "一二三四五六日"


def match_overview_html(match, link_url):
    """后台列表中的比赛摘要：赛事与轮次 → 对阵 → 日期时间与场地。"""
    meta = " · ".join(
        part
        for part in (
            str(match.competition),
            match.round_name,
            f"场次 {match.match_number}" if match.match_number else "",
        )
        if part
    )
    kickoff = timezone.localtime(match.kickoff_at)
    when = (
        f"{kickoff:%Y年%m月%d日} 周{WEEKDAYS[kickoff.weekday()]} "
        f"{kickoff:%H:%M}"
    )
    return format_html(
        '<div class="match-cell">'
        '<a class="match-link row-link" href="{}">'
        '<span class="match-meta">{}</span>'
        '<strong class="match-teams">{} vs {}</strong>'
        "</a>"
        '<span class="match-time">{} · {}</span>'
        "</div>",
        link_url,
        meta,
        match.home_team,
        match.away_team,
        when,
        match.venue,
    )


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "is_active", "updated_at")
    list_filter = ("is_active", "season")
    search_fields = ("name", "season")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "short_name")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address")


@admin.register(RefereeProfile)
class RefereeProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "level", "phone", "is_active")
    list_filter = ("level", "is_active")
    search_fields = ("name", "phone", "user__username")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        referee_group = Group.objects.filter(
            name="裁判员"
        ).first()

        if referee_group is not None:
            obj.user.groups.add(referee_group)


class AssignmentInlineFormSet(BaseInlineFormSet):
    """后台排班与前台使用同一套时间冲突检查。"""

    def clean(self):
        super().clean()
        match = self.instance
        if match.status == Match.Status.CANCELLED or match.kickoff_at is None:
            return

        kickoff_changed = True
        if match.pk:
            saved_kickoff = (
                Match.objects.filter(pk=match.pk)
                .values_list("kickoff_at", flat=True)
                .first()
            )
            kickoff_changed = saved_kickoff != match.kickoff_at

        to_check = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            referee = form.cleaned_data.get("referee")
            if referee is None:
                continue
            if kickoff_changed or not form.instance.pk or "referee" in form.changed_data:
                to_check[referee.pk] = form

        conflicts = find_time_conflicts(match, match.kickoff_at, to_check)
        for referee_id, message in conflicts.items():
            to_check[referee_id].add_error("referee", message)


class AssignmentInline(admin.TabularInline):
    model = Assignment
    formset = AssignmentInlineFormSet
    extra = 1
    autocomplete_fields = ("referee",)
    fields = (
        "position",
        "referee",
        "response_status",
        "response_note",
    )


class KickoffRangeFilter(admin.SimpleListFilter):
    """比赛时间筛选，默认只看今天及以后的比赛。"""

    title = "比赛时间"
    parameter_name = "when"
    default = "upcoming"

    def lookups(self, request, model_admin):
        return (
            ("upcoming", "今天及以后"),
            ("week", "未来 7 天"),
            ("past", "已过"),
            ("all", "全部"),
        )

    def current(self):
        value = self.value()
        return value if value in dict(self.lookup_choices) else self.default

    def choices(self, changelist):
        current = self.current()
        for value, label in self.lookup_choices:
            yield {
                "selected": current == value,
                "query_string": changelist.get_query_string(
                    {self.parameter_name: value}
                ),
                "display": label,
            }

    def queryset(self, request, queryset):
        today = timezone.localdate()
        current = self.current()
        if current == "upcoming":
            return queryset.filter(kickoff_at__date__gte=today)
        if current == "week":
            return queryset.filter(
                kickoff_at__date__gte=today,
                kickoff_at__date__lt=today + timedelta(days=7),
            )
        if current == "past":
            return queryset.filter(kickoff_at__date__lt=today)
        return queryset


class UpcomingFirstMixin:
    """未来的比赛按开球时间从近到远排列；查看已过比赛时从近到远倒序。"""

    def get_ordering(self, request):
        if request.GET.get(KickoffRangeFilter.parameter_name) in ("past", "all"):
            return ("-kickoff_at", "-id")
        return ("kickoff_at", "id")


def lineup_html(match):
    """后台比赛列表里的紧凑裁判名单：岗位简称 + 姓名，按反馈状态着色。"""
    by_position = assignments_by_position(match)
    rows = []
    for position, short in LINEUP_SHORT_NAMES:
        assignment = by_position.get(position)
        if assignment is None:
            rows.append(
                format_html(
                    '<span class="lineup-row resp-empty"><b>{}</b>未安排</span>', short
                )
            )
        else:
            rows.append(
                format_html(
                    '<span class="lineup-row resp-{}" title="{}"><b>{}</b>{}</span>',
                    assignment.response_status,
                    assignment.get_response_status_display(),
                    short,
                    assignment.referee.name,
                )
            )
    return format_html(
        '<div class="lineup-cell">{}</div>', format_html_join("", "{}", ((row,) for row in rows))
    )


LINEUP_SHORT_NAMES = (
    (Assignment.Position.REFEREE, "主裁"),
    (Assignment.Position.ASSISTANT_1, "一助"),
    (Assignment.Position.ASSISTANT_2, "二助"),
    (Assignment.Position.FOURTH_OFFICIAL, "四官"),
)


@admin.register(Match)
class MatchAdmin(UpcomingFirstMixin, admin.ModelAdmin):
    list_display = (
        "match_overview",
        "lineup",
        "status",
        "assignment_status",
    )
    list_display_links = None
    list_filter = (
        KickoffRangeFilter,
        "competition",
        "status",
        "assignment_status",
        "venue",
    )
    search_fields = (
        "match_number",
        "home_team__name",
        "away_team__name",
        "competition__name",
    )
    autocomplete_fields = (
        "competition",
        "home_team",
        "away_team",
        "venue",
    )
    readonly_fields = (
        "created_by",
        "published_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "kickoff_at"
    inlines = (AssignmentInline,)
    list_select_related = (
        "competition",
        "home_team",
        "away_team",
        "venue",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(
            super().get_readonly_fields(request, obj)
        )

        if not request.user.has_perm(
            "scheduling.publish_assignments"
        ):
            readonly_fields.append("assignment_status")

        return readonly_fields

    actions = ("publish_selected",)
    actions_on_bottom = True

    @admin.display(description="比赛", ordering="kickoff_at")
    def match_overview(self, obj):
        return match_overview_html(
            obj,
            reverse("admin:scheduling_match_change", args=[obj.pk]),
        )

    @admin.display(description="裁判")
    def lineup(self, obj):
        return lineup_html(obj)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "competition",
            "home_team",
            "away_team",
            "venue",
        ).prefetch_related(
            Prefetch(
                "assignments",
                queryset=Assignment.objects.select_related("referee"),
            )
        )

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )

        # 为裁判安排选择比赛时，只列出未结束、未取消的比赛。
        if (
            request.GET.get("model_name") == "assignment"
            and request.GET.get("field_name") == "match"
        ):
            queryset = queryset.filter(
                status=Match.Status.SCHEDULED,
                kickoff_at__date__gte=timezone.localdate(),
            ).order_by("kickoff_at", "id")

        return queryset, may_have_duplicates

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user

        # 新发布的比赛先按草稿保存，等裁判安排（内联表单）保存后
        # 再在 save_related 中统一检查、发布并通知裁判。
        previous = Match.objects.filter(pk=obj.pk).first() if change else None
        was_published = (
            previous is not None
            and previous.assignment_status == Match.AssignmentStatus.PUBLISHED
        )
        request._match_was_published = was_published
        request._removed_referees = []
        request._referees_changed = False

        request._publish_match_after_save = False
        if obj.assignment_status == Match.AssignmentStatus.PUBLISHED:
            if not was_published:
                request._publish_match_after_save = True
                obj.assignment_status = Match.AssignmentStatus.DRAFT
                obj.published_at = None
        else:
            obj.published_at = None

        super().save_model(request, obj, form, change)

        # 已发布比赛改了时间、场地或状态：在裁判名单变动前通知原来的裁判。
        if was_published:
            notified = after_match_update(request, obj, match_snapshot(previous))
            if notified:
                self.message_user(
                    request,
                    f"比赛信息有变动，已通知本场 {notified} 名裁判。",
                    messages.INFO,
                )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        match = form.instance
        if (
            getattr(request, "_match_was_published", False)
            and getattr(request, "_referees_changed", False)
            and match.assignment_status == Match.AssignmentStatus.PUBLISHED
        ):
            # 与前台一致：已发布的安排换人后退回草稿，等重新发布再通知新裁判。
            match.assignment_status = Match.AssignmentStatus.DRAFT
            match.published_at = None
            match.save(
                update_fields=["assignment_status", "published_at", "updated_at"]
            )
            notify_assignment_removed(request, match, request._removed_referees)
            self.message_user(
                request,
                "裁判名单有变动，本场安排已退回草稿，请检查后重新发布。",
                messages.WARNING,
            )

        if getattr(request, "_publish_match_after_save", False):
            ok, notified, problem = publish_match(request, form.instance)
            if ok:
                self.message_user(
                    request,
                    f"裁判安排已经发布，已通知 {notified} 名裁判。",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    f"已保存为草稿，未发布：{problem}",
                    messages.WARNING,
                )

    def has_publish_permission(self, request):
        return request.user.has_perm("scheduling.publish_assignments")

    @admin.action(
        description="发布所选比赛的裁判安排",
        permissions=["publish"],
    )
    def publish_selected(self, request, queryset):
        published, notified, skipped = publish_matches(
            request,
            queryset.order_by("kickoff_at", "id"),
        )
        if published:
            self.message_user(
                request,
                f"已发布 {published} 场比赛的裁判安排，已通知 {notified} 名裁判。",
                messages.SUCCESS,
            )
        for reason in skipped:
            self.message_user(request, f"未发布：{reason}", messages.WARNING)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        removed = getattr(request, "_removed_referees", [])

        for deleted_object in formset.deleted_objects:
            if isinstance(deleted_object, Assignment):
                removed.append(
                    (deleted_object.referee, deleted_object.get_position_display())
                )
                request._referees_changed = True
            deleted_object.delete()

        changed_status = set()
        swapped = set()
        for inline_form in formset.forms:
            if "response_status" in inline_form.changed_data:
                changed_status.add(inline_form.instance.pk)
            if inline_form.instance.pk and "referee" in inline_form.changed_data:
                swapped.add(inline_form.instance.pk)
                old_referee = RefereeProfile.objects.filter(
                    pk=inline_form.initial.get("referee")
                ).first()
                if old_referee is not None:
                    removed.append(
                        (old_referee, inline_form.instance.get_position_display())
                    )

        for instance in instances:
            if isinstance(instance, Assignment):
                if instance.assigned_by_id is None:
                    instance.assigned_by = request.user
                if instance.pk is None or instance.pk in swapped:
                    request._referees_changed = True
                if instance.pk in swapped:
                    # 换了裁判：原裁判的确认或请假不能留给新裁判。
                    instance.response_status = Assignment.ResponseStatus.PENDING
                    instance.response_note = ""
                    instance.responded_at = None
                else:
                    update_response_time(
                        instance,
                        status_changed=instance.pk in changed_status,
                    )

            instance.save()

        formset.save_m2m()


class AssignmentAdminForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        match = cleaned_data.get("match")
        referee = cleaned_data.get("referee")
        if (
            match is not None
            and referee is not None
            and match.status != Match.Status.CANCELLED
            and (not self.instance.pk or {"match", "referee"} & set(self.changed_data))
        ):
            conflict = find_time_conflicts(match, match.kickoff_at, [referee.pk])
            if conflict:
                self.add_error("referee", conflict[referee.pk])
        return cleaned_data


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm
    list_display = (
        "match",
        "position",
        "referee",
        "response_status",
        "responded_at",
    )
    list_filter = (
        "position",
        "response_status",
        "match__competition",
    )
    search_fields = (
        "referee__name",
        "match__home_team__name",
        "match__away_team__name",
    )
    autocomplete_fields = ("match", "referee")
    readonly_fields = (
        "responded_at",
        "assigned_by",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "match",
        "referee",
        "match__competition",
        "match__home_team",
        "match__away_team",
    )

    def get_model_perms(self, request):
        # 列表改由「裁判安排」（每场比赛一行）提供；明细页仍可从该列表点击进入。
        return {}

    def save_model(self, request, obj, form, change):
        if obj.assigned_by_id is None:
            obj.assigned_by = request.user

        swapped = None
        if change and {"referee", "match"} & set(form.changed_data):
            swapped = Assignment.objects.select_related("match", "referee").get(
                pk=obj.pk
            )
            # 换了裁判或比赛：原来的确认或请假不能留给新的安排。
            obj.response_status = Assignment.ResponseStatus.PENDING
            obj.response_note = ""
            obj.responded_at = None
        else:
            update_response_time(
                obj,
                status_changed="response_status" in form.changed_data,
            )
        super().save_model(request, obj, form, change)

        notify_removed = (
            swapped is not None
            and swapped.match.assignment_status == Match.AssignmentStatus.PUBLISHED
        )
        # 新增或换人后，已发布的安排退回草稿，等重新发布再通知新裁判。
        affected = {}
        if not change or swapped is not None:
            affected[obj.match_id] = Match.objects.get(pk=obj.match_id)
        if swapped is not None:
            affected.setdefault(swapped.match_id, swapped.match)
        for match in affected.values():
            if match.assignment_status != Match.AssignmentStatus.PUBLISHED:
                continue
            match.assignment_status = Match.AssignmentStatus.DRAFT
            match.published_at = None
            match.save(
                update_fields=["assignment_status", "published_at", "updated_at"]
            )
            self.message_user(
                request,
                f"{match_label(match)} 的裁判安排已退回草稿，请检查后重新发布。",
                messages.WARNING,
            )
        if notify_removed:
            notify_assignment_removed(
                request,
                swapped.match,
                [(swapped.referee, swapped.get_position_display())],
            )


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "note",
        "is_active",
        "used_count",
        "max_uses",
        "expires_at",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "note")
    readonly_fields = ("used_count", "created_at", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "message", "created_at", "read_at")
    list_filter = ("read_at",)
    search_fields = ("recipient__username", "message")
    list_select_related = ("recipient",)
    readonly_fields = ("created_at",)




def assignments_by_position(match):
    if not hasattr(match, "_assignments_by_position"):
        match._assignments_by_position = {
            assignment.position: assignment
            for assignment in match.assignments.all()
        }
    return match._assignments_by_position


def position_column(position, label):
    @admin.display(description=label)
    def column(self, obj):
        assignment = assignments_by_position(obj).get(position)
        if assignment is None:
            return format_html('<span class="resp resp-empty">{}</span>', "未安排")

        return format_html(
            '<a class="chip-link" href="{}">{}</a><br>'
            '<span class="resp resp-{}">{}</span>',
            reverse(
                "admin:scheduling_assignment_change",
                args=[assignment.pk],
            ),
            assignment.referee.name,
            assignment.response_status,
            assignment.get_response_status_display(),
        )

    return column


@admin.register(MatchAssignmentSummary)
class MatchAssignmentSummaryAdmin(UpcomingFirstMixin, admin.ModelAdmin):
    list_display = (
        "match_info",
        "referee_column",
        "assistant_1_column",
        "assistant_2_column",
        "fourth_official_column",
        "assignment_status",
    )
    list_display_links = None
    list_filter = (
        KickoffRangeFilter,
        "competition",
        "assignment_status",
        "status",
    )
    search_fields = (
        "match_number",
        "home_team__name",
        "away_team__name",
        "competition__name",
    )
    date_hierarchy = "kickoff_at"
    actions = ("publish_selected",)
    actions_on_bottom = True
    list_per_page = 50

    referee_column = position_column(
        Assignment.Position.REFEREE,
        "主裁判",
    )
    assistant_1_column = position_column(
        Assignment.Position.ASSISTANT_1,
        "第一助理裁判",
    )
    assistant_2_column = position_column(
        Assignment.Position.ASSISTANT_2,
        "第二助理裁判",
    )
    fourth_official_column = position_column(
        Assignment.Position.FOURTH_OFFICIAL,
        "第四官员",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("competition", "home_team", "away_team", "venue")
            .prefetch_related(
                Prefetch(
                    "assignments",
                    queryset=Assignment.objects.select_related("referee"),
                )
            )
        )

    @admin.display(description="比赛", ordering="kickoff_at")
    def match_info(self, obj):
        return match_overview_html(
            obj,
            reverse("admin:scheduling_match_change", args=[obj.pk]),
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = {"title": "裁判安排", **(extra_context or {})}
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("scheduling.view_match")

    def has_publish_permission(self, request):
        return request.user.has_perm("scheduling.publish_assignments")

    publish_selected = MatchAdmin.publish_selected


# ---- 权限名称显示为中文 ----
# 权限名称在创建时以英文写入数据库（如 "Can add match"），翻译文件无法改变，
# 因此在角色和用户的编辑页按「应用 | 模型 | 操作」重新生成中文标签。
PERMISSION_ACTIONS = {
    "add": "新增",
    "change": "修改",
    "delete": "删除",
    "view": "查看",
}


def permission_label(permission):
    content_type = permission.content_type
    model = content_type.model_class()
    try:
        app_name = django_apps.get_app_config(content_type.app_label).verbose_name
    except LookupError:
        app_name = content_type.app_label
    model_name = model._meta.verbose_name if model else content_type.model
    action, _, rest = permission.codename.partition("_")
    if action in PERMISSION_ACTIONS and model and rest == model._meta.model_name:
        label = f"{PERMISSION_ACTIONS[action]}{model_name}"
    else:
        label = permission.name
    return f"{app_name} | {model_name} | {label}"


class ChinesePermissionsMixin:
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name in ("permissions", "user_permissions") and field:
            field.queryset = field.queryset.select_related("content_type")
            field.label_from_instance = permission_label
        return field


admin.site.unregister(Group)
admin.site.unregister(get_user_model())


@admin.register(Group)
class RoleAdmin(ChinesePermissionsMixin, GroupAdmin):
    pass


@admin.register(get_user_model())
class AccountAdmin(ChinesePermissionsMixin, UserAdmin):
    pass

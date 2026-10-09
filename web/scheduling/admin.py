from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.utils import timezone

from .publishing import publish_match, publish_matches
from .models import (
    Assignment,
    Competition,
    InviteCode,
    Match,
    Notification,
    RefereeProfile,
    Team,
    Venue,
)


admin.site.site_header = f"{settings.SITE_NAME} · 管理后台"
admin.site.site_title = f"{settings.SITE_NAME}管理后台"
admin.site.index_title = "系统管理"
admin.site.site_url = "/"


def update_response_time(assignment):
    if assignment.response_status == Assignment.ResponseStatus.PENDING:
        assignment.responded_at = None
    elif assignment.responded_at is None:
        assignment.responded_at = timezone.now()


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


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 1
    autocomplete_fields = ("referee",)
    fields = (
        "position",
        "referee",
        "response_status",
        "response_note",
        "responded_at",
    )


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "kickoff_at",
        "home_team",
        "away_team",
        "competition",
        "venue",
        "status",
        "assignment_status",
    )
    list_filter = (
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "competition",
            "home_team",
            "away_team",
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
        request._publish_match_after_save = False
        if obj.assignment_status == Match.AssignmentStatus.PUBLISHED:
            previous = None
            if change:
                previous = (
                    Match.objects.filter(pk=obj.pk)
                    .values_list("assignment_status", flat=True)
                    .first()
                )
            if previous != Match.AssignmentStatus.PUBLISHED:
                request._publish_match_after_save = True
                obj.assignment_status = Match.AssignmentStatus.DRAFT
                obj.published_at = None
        else:
            obj.published_at = None

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

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

        for deleted_object in formset.deleted_objects:
            deleted_object.delete()

        for instance in instances:
            if isinstance(instance, Assignment):
                if instance.assigned_by_id is None:
                    instance.assigned_by = request.user
                update_response_time(instance)

            instance.save()

        formset.save_m2m()


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
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
    readonly_fields = ("assigned_by", "created_at", "updated_at")
    list_select_related = (
        "match",
        "referee",
        "match__home_team",
        "match__away_team",
    )

    def save_model(self, request, obj, form, change):
        if obj.assigned_by_id is None:
            obj.assigned_by = request.user

        update_response_time(obj)
        super().save_model(request, obj, form, change)


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

from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils import timezone

from .models import (
    Assignment,
    Competition,
    Match,
    RefereeProfile,
    Team,
    Venue,
)


admin.site.site_header = "足协裁判管理系统"
admin.site.site_title = "足协管理后台"
admin.site.index_title = "系统管理"


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

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user

        if obj.assignment_status == Match.AssignmentStatus.PUBLISHED:
            if obj.published_at is None:
                obj.published_at = timezone.now()
        else:
            obj.published_at = None

        super().save_model(request, obj, form, change)

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

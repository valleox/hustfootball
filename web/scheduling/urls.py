from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.match_list, name="match_list"),
    path(
        "matches/export/",
        views.assignment_export,
        name="assignment_export",
    ),
    path(
        "matches/publish/",
        views.assignment_bulk_publish,
        name="assignment_bulk_publish",
    ),
    path(
        "matches/new/",
        views.match_create,
        name="match_create",
    ),
    path(
        "matches/<int:pk>/",
        views.match_detail,
        name="match_detail",
    ),
    path(
        "matches/<int:pk>/edit/",
        views.match_update,
        name="match_update",
    ),
    path(
        "matches/<int:pk>/assignments/edit/",
        views.assignment_update,
        name="assignment_update",
    ),
    path(
        "matches/<int:pk>/assignments/publish/",
        views.assignment_publish,
        name="assignment_publish",
    ),
    path(
        "matches/<int:pk>/report/",
        views.report_edit,
        name="report_edit",
    ),
    path(
        "matches/<int:pk>/report/request/",
        views.report_request,
        name="report_request",
    ),
    path(
        "matches/<int:pk>/report/download/",
        views.report_download,
        name="report_download",
    ),
    path(
        "reports/",
        views.report_list,
        name="report_list",
    ),
    path(
        "notifications/",
        views.notification_list,
        name="notification_list",
    ),
    path(
        "referees/workload/",
        views.referee_workload,
        name="referee_workload",
    ),
    path(
        "assignments/<int:pk>/respond/",
        views.assignment_respond,
        name="assignment_respond",
    ),
]

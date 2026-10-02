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
        "assignments/<int:pk>/respond/",
        views.assignment_respond,
        name="assignment_respond",
    ),
]

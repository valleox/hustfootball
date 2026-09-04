from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.match_list, name="match_list"),
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
]

from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.match_list, name="match_list"),
    path(
        "matches/<int:pk>/",
        views.match_detail,
        name="match_detail",
    ),
]

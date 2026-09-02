from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.home, name="home"),
]

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from scheduling import views as scheduling_views

urlpatterns = [
    path(
        "admin/login/",
        scheduling_views.admin_login_redirect,
        name="admin_login_redirect",
    ),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "accounts/signup/",
        scheduling_views.signup,
        name="signup",
    ),
    path(
        "accounts/password/",
        auth_views.PasswordChangeView.as_view(
            template_name="scheduling/password_change_form.html",
        ),
        name="password_change",
    ),
    path(
        "accounts/password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="scheduling/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("", include("scheduling.urls")),
]

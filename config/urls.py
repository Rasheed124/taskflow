from django.contrib import admin
from django.urls import include, path

from accounts.services.rate_limiting import rate_limit_auth_view
from config.settings.health import health_check


admin.site.login = rate_limit_auth_view("admin_login")(admin.site.login)


urlpatterns = [
    path("", include("core.urls")),

    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),

    path("tasks/", include("tasks.urls")),
    path("accounts/", include("accounts.urls")),
]


from django.urls import path

from core import views


app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("privacy/", views.PrivacyPolicyView.as_view(), name="privacy"),
    path("terms/", views.TermsOfServiceView.as_view(), name="terms"),
    path("csp-report/", views.csp_report, name="csp-report"),
    path("robots.txt", views.robots_txt, name="robots"),
]

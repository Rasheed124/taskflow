from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms_auth import TaskFlowAuthenticationForm
from .forms import NormalizedPasswordResetForm
from .services.rate_limiting import rate_limit_auth_view


app_name = "accounts"


urlpatterns = [


    path(
        "register/",
        rate_limit_auth_view("register")(views.register),
        name="register",
    ),

    path(
        "profile/",
        views.profile,
        name="profile",
    ),

    path(
        "email-verification/sent/",
        views.EmailVerificationSentView.as_view(),
        name="email_verification_sent",
    ),
    path(
        "email-verification/resend/",
        rate_limit_auth_view("verification_resend")(
            views.resend_email_verification
        ),
        name="resend_email_verification",
    ),
    path(
        "email-verification/resend-pending/",
        rate_limit_auth_view("verification_resend")(
            views.resend_pending_email_verification
        ),
        name="resend_pending_email_verification",
    ),
    path(
        "email-verification/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),

    # Authentication
    path(
        "login/",
        rate_limit_auth_view("login")(
            auth_views.LoginView.as_view(
                template_name="accounts/login.html",
                redirect_authenticated_user=True,
                authentication_form=TaskFlowAuthenticationForm,
            )
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # Password reset
    path(
        "password-reset/",
        rate_limit_auth_view("password_reset")(
            auth_views.PasswordResetView.as_view(
                form_class=NormalizedPasswordResetForm,
                template_name="accounts/password_reset.html",
                email_template_name="accounts/password_reset_email.html",
                subject_template_name="accounts/password_reset_subject.txt",
                success_url=reverse_lazy(
                    "accounts:password_reset_done"
                ),
            )
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        rate_limit_auth_view("password_reset_confirm")(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="accounts/password_reset_confirm.html",
                success_url=reverse_lazy(
                    "accounts:password_reset_complete"
                ),
            ),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # Authenticated password change
    path(
        "password-change/",
        views.AccountPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),
]

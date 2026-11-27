from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm

from accounts.services.email_verification import get_account_profile


User = get_user_model()


class TaskFlowAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                identifier = username.strip()
                account_exists = User.objects.filter(
                    username__iexact=identifier
                ).exists() or User.objects.filter(
                    email__iexact=identifier
                ).exists()
                if "@" in identifier and not account_exists:
                    raise forms.ValidationError(
                        "No account is registered with this email address.",
                        code="unknown_email",
                    )
                raise self.get_invalid_login_error()

            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        profile = get_account_profile(user)

        if not profile.email_verified:
            raise forms.ValidationError(
                "This account needs email verification. If you control its registered address, request a new verification link.",
                code="email_not_verified",
            )

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.db.models import Q


User = get_user_model()


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
        ]
        error_messages = {
            "username": {
                "invalid": (
                    "Use letters, numbers, and @ . + - _ characters only."
                ),
            },
        }

    def validate_unique(self):
        return None

    def clean_username(self):
        return self.cleaned_data["username"]

    def clean(self):
        cleaned_data = super().clean()
        self.add_account_conflict_errors()
        return cleaned_data

    def _account_conflicts(self):
        username = self.cleaned_data.get("username") or self.data.get("username", "")
        email = self.cleaned_data.get("email") or self.data.get("email", "")
        email = email.strip().lower() if isinstance(email, str) else ""

        username_exists = bool(username) and User.objects.filter(
            username__iexact=username
        ).exists()
        email_exists = bool(email) and User.objects.filter(
            Q(email__iexact=email)
            | Q(account_profile__pending_email__iexact=email)
        ).exists()
        return username_exists, email_exists

    def has_account_conflict(self):
        return any(self._account_conflicts())

    def add_account_conflict_errors(self):
        username_exists, email_exists = self._account_conflicts()
        if username_exists and "username" not in self.errors:
            self.add_error(
                "username",
                "This username is already in use. Please choose another.",
            )
        if email_exists and "email" not in self.errors:
            self.add_error(
                "email",
                "An account already uses this email address. Please sign in or use another email.",
            )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
        ]
        error_messages = {
            "username": {
                "invalid": (
                    "Use letters, numbers, and @ . + - _ characters only."
                ),
            },
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        email_exists = User.objects.filter(
            Q(email__iexact=email)
            | Q(account_profile__pending_email__iexact=email)
        ).exclude(
            pk=self.instance.pk
        ).exists()

        if email_exists:
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email


class ResendVerificationForm(forms.Form):
    email = forms.EmailField()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

class NormalizedPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

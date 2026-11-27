import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
import smtplib


from .forms import (
    ProfileUpdateForm,
    RegistrationForm,
    ResendVerificationForm,
)
from .models import AccountProfile


from .services.email_verification import (
    create_unverified_profile,
    get_account_profile,
    send_email_verification,
    verify_email_token_result,
)


logger = logging.getLogger(__name__)
User = get_user_model()


def invalid_verification_response(request, status_code=400, expired=False):
    return render(
        request,
        "accounts/email_verification_invalid.html",
        {"expired": expired},
        status=status_code,
    )


def get_email_delivery_error_message(error):
    """
    Return a user-friendly message for email delivery failures.
    """
    smtp_error = getattr(error, "smtp_error", "")

    if isinstance(smtp_error, bytes):
        smtp_error = smtp_error.decode(
            "utf-8",
            errors="replace",
        )

    error_details = f"{error} {smtp_error}".casefold()

    if (
        isinstance(error, smtplib.SMTPDataError)
        and "testing emails" in error_details
    ):
        return (
            "Resend rejected this verification email because your "
            "account is still in testing mode. Testing mode only "
            "allows delivery to your Resend account email address. "
            "Verify a sending domain in Resend to send emails to "
            "other addresses. Your new email-change request was "
            "not saved."
        )

    return (
        "We could not send your verification email. "
        "Your new email-change request was not saved. "
        "Please try again later."
    )

@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("tasks:list")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    create_unverified_profile(user)
            except IntegrityError:
                # Recheck conflicts if another registration claimed an
                # identifier after form validation.
                if form.has_account_conflict():
                    form.add_account_conflict_errors()
                    return render(
                        request,
                        "accounts/register.html",
                        {"form": form},
                    )
                raise

            try:
                send_email_verification(
                    request,
                    user,
                    user.email,
                )
            except Exception:
                logger.exception(
                    "Could not send registration verification email "
                    "for user %s.",
                    user.pk,
                )

                messages.warning(
                    request,
                    "Your account was created, but we could not send "
                    "the verification email. Please request another.",
                )

            return redirect("accounts:email_verification_sent")

    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )




@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(
            request.POST,
            instance=request.user,
        )

        if form.is_valid():
            proposed_email = form.cleaned_data["email"]

            with transaction.atomic():
                user = User.objects.select_for_update().get(
                    pk=request.user.pk,
                )

                account_profile = (
                    AccountProfile.objects.select_for_update()
                    .filter(user=user)
                    .first()
                )

                if account_profile is None:
                    logger.error(
                        "Account profile missing for user %s.",
                        user.pk,
                    )

                    messages.error(
                        request,
                        "Your account profile could not be found. "
                        "Please contact support.",
                    )

                    return redirect("accounts:profile")

                email_changed = (
                    proposed_email.casefold()
                    != user.email.casefold()
                )

                # Preserve the previous pending request so that
                # a failed delivery does not destroy it.
                previous_pending_email = account_profile.pending_email

                # Update username independently of email delivery.
                user.username = form.cleaned_data["username"]
                user.save(update_fields=["username"])

                if email_changed:
                    account_profile.pending_email = proposed_email
                else:
                    # Submitting the current email cancels any
                    # previously pending email change.
                    account_profile.pending_email = ""

                account_profile.save(
                    update_fields=[
                        "pending_email",
                        "updated_at",
                    ]
                )

            if email_changed:
                try:
                    send_email_verification(
                        request,
                        user,
                        proposed_email,
                    )

                except Exception as error:
                    logger.exception(
                        "Could not send email-change verification "
                        "for user %s.",
                        user.pk,
                    )

                    # Restore the previous pending email only if
                    # this request is still the active pending one.
                    with transaction.atomic():
                        profile_record = (
                            AccountProfile.objects.select_for_update()
                            .filter(user=user)
                            .first()
                        )

                        if (
                            profile_record
                            and profile_record.pending_email.casefold()
                            == proposed_email.casefold()
                        ):
                            profile_record.pending_email = (
                                previous_pending_email
                            )

                            profile_record.save(
                                update_fields=[
                                    "pending_email",
                                    "updated_at",
                                ]
                            )

                    messages.error(
                        request,
                        get_email_delivery_error_message(error),
                    )

                else:
                    messages.success(
                        request,
                        "Your profile was updated. Check your new "
                        "email address to confirm the change.",
                    )

            else:
                messages.success(
                    request,
                    "Your profile has been updated successfully.",
                )

            return redirect("accounts:profile")

    else:
        form = ProfileUpdateForm(instance=request.user)

    account_profile = get_account_profile(request.user)

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "account_profile": account_profile,
        },
    )



class EmailVerificationSentView(TemplateView):
    template_name = "accounts/email_verification_sent.html"
    http_method_names = ["get"]


@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    payload, reason = verify_email_token_result(token)

    if not isinstance(payload, dict):
        return invalid_verification_response(
            request,
            status_code=410 if reason == "expired" else 400,
            expired=reason == "expired",
        )

    if request.method == "GET":
        return render(
            request,
            "accounts/email_verification_confirm.html",
            {"token": token},
        )

    user_id = payload.get("user_id")
    email = payload.get("email")

    if (
        not isinstance(email, str)
        or not email.strip()
        or user_id is None
    ):
        return invalid_verification_response(request)

    email = email.strip().lower()

    try:
        with transaction.atomic():
            user = User.objects.select_for_update().get(
                pk=user_id,
            )

            profile = (
                AccountProfile.objects.select_for_update()
                .filter(user=user)
                .first()
            )

            if profile is None:
                return invalid_verification_response(request, status_code=410)

            # Registration verification.
            if (
                not profile.email_verified
                and user.email.casefold() == email.casefold()
            ):
                profile.email_verified = True

                profile.save(
                    update_fields=[
                        "email_verified",
                        "updated_at",
                    ]
                )

            # Email-change verification.
            elif (
                profile.pending_email
                and profile.pending_email.casefold()
                == email.casefold()
            ):
                email_in_use = User.objects.filter(
                    Q(email__iexact=email)
                    | Q(account_profile__pending_email__iexact=email)
                ).exclude(
                    pk=user.pk
                ).exists()

                if email_in_use:
                    return invalid_verification_response(
                        request,
                        status_code=410,
                    )

                user.email = email
                user.save(update_fields=["email"])

                profile.email_verified = True
                profile.pending_email = ""

                profile.save(
                    update_fields=[
                        "email_verified",
                        "pending_email",
                        "updated_at",
                    ]
                )

            else:
                return invalid_verification_response(request, status_code=410)

    except User.DoesNotExist:
        return invalid_verification_response(request, status_code=410)

    messages.success(
        request,
        "Your email address has been verified.",
        extra_tags="verification-toast",
    )

    return render(
        request,
        "accounts/email_verification_complete.html",
    )


@require_http_methods(["GET", "POST"])
def resend_email_verification(request):
    """
    Public resend workflow for registration verification only.
    """
    if request.method == "POST":
        form = ResendVerificationForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip()

            user = User.objects.filter(
                email__iexact=email,
            ).first()

            if user:
                profile = get_account_profile(user)

                if not profile.email_verified:
                    try:
                        send_email_verification(
                            request,
                            user,
                            user.email,
                        )
                    except Exception:
                        logger.exception(
                            "Registration verification resend failed "
                            "for user %s.",
                            user.pk,
                        )

            messages.info(
                request,
                "If an account requires verification for that address, "
                "we will send a verification email.",
            )

            return redirect("accounts:email_verification_sent")

    else:
        form = ResendVerificationForm()

    return render(
        request,
        "accounts/email_verification_resend.html",
        {"form": form},
    )


@login_required
@require_http_methods(["POST"])
def resend_pending_email_verification(request):
    """
    Authenticated resend workflow for a pending email change.
    """
    profile = get_account_profile(request.user)

    if not profile.pending_email:
        messages.info(
            request,
            "There is no pending email address to verify.",
        )

        return redirect("accounts:profile")

    try:
        send_email_verification(
            request,
            request.user,
            profile.pending_email,
        )

        messages.success(
            request,
            "A new verification link has been sent to your pending email.",
        )

    except Exception:
        logger.exception(
            "Pending email verification resend failed for user %s.",
            request.user.pk,
        )

        messages.warning(
            request,
            "We could not send the verification email. Please try again.",
        )

    return redirect("accounts:profile")


class AccountPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Your password has been changed successfully.",
        )

        return super().form_valid(form)

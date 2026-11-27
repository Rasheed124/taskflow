from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q

from .models import AccountProfile


User = get_user_model()
admin.site.unregister(User)


class AccountProfileInline(admin.StackedInline):
    model = AccountProfile
    can_delete = False
    extra = 0
    max_num = 1
    readonly_fields = (
        "email_verified",
        "pending_email",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields
    verbose_name = "Account profile"
    verbose_name_plural = "Account profile"


class EmailVerificationFilter(admin.SimpleListFilter):
    title = "email verification"
    parameter_name = "email_verification"

    def lookups(self, request, model_admin):
        return (
            ("verified", "Verified"),
            ("unverified", "Not verified"),
        )

    def queryset(self, request, queryset):
        if self.value() == "verified":
            return queryset.filter(account_profile__email_verified=True)
        if self.value() == "unverified":
            return queryset.filter(
                Q(account_profile__isnull=True)
                | Q(account_profile__email_verified=False)
            )
        return queryset


@admin.register(User)
class TaskFlowUserAdmin(UserAdmin):
    inlines = (AccountProfileInline,)
    list_display = (
        "username",
        "email",
        "email_verification_status",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = (
        "is_active",
        "is_staff",
        EmailVerificationFilter,
        "date_joined",
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    list_select_related = ("account_profile",)

    @admin.display(
        description="Email verified",
        ordering="account_profile__email_verified",
    )
    def email_verification_status(self, user):
        try:
            profile = user.account_profile
        except AccountProfile.DoesNotExist:
            return "No profile"
        return "Verified" if profile.email_verified else "Not verified"


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "user_email",
        "email_verified",
        "pending_email",
        "created_at",
    )
    list_filter = ("email_verified", "created_at")
    search_fields = ("user__username", "user__email", "pending_email")
    readonly_fields = (
        "user",
        "email_verified",
        "pending_email",
        "created_at",
        "updated_at",
    )
    list_select_related = ("user",)

    @admin.display(description="User email", ordering="user__email")
    def user_email(self, profile):
        return profile.user.email

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Profile state is changed by the application’s verification flow.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

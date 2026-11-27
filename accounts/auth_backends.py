from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate with Django's model backend using username or email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        identifier = username.strip()
        try:
            if "@" in identifier:
                try:
                    user = UserModel._default_manager.get(email__iexact=identifier)
                except UserModel.DoesNotExist:
                    user = UserModel._default_manager.get_by_natural_key(identifier)
            else:
                user = UserModel._default_manager.get_by_natural_key(identifier)
        except UserModel.DoesNotExist:
            # Match the password hashing work done by Django's ModelBackend
            # for an unknown username to reduce timing-based enumeration.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # An ambiguous email must never authenticate an arbitrary user.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

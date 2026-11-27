# TaskFlow admin guide

## Access

The Django admin is available at `/admin/`. Only staff accounts can enter it;
the account and permission controls remain governed by Django's staff and
superuser permissions. Admin sign-in is rate-limited by the shared account
rate limiter.

## Find and review accounts

Open **Authentication and Authorization → Users** to search by username, email,
first name, or last name. The list shows whether the account is active, whether
it has staff access, when it joined, and its email-verification state. Use the
filters to narrow by active/staff status, verification state, or join date.

Open a user to see their account profile. Verification state and pending email
are read-only here because the application's verification flow is responsible
for changing them. The **Account profiles** list provides a read-only way to
search profiles and pending email addresses.

Profiles missing from older accounts appear as **No profile** in the user list
and are included under **Not verified**. Review those accounts through the
application's account recovery and verification workflows before granting
access.

## Review tasks and categories

The existing **Tasks** and **Categories** admin pages remain available. Task
search now includes the owner's email, and category search includes the
owner's email as well as username.

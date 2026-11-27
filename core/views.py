
import json
import logging
from email.utils import parseaddr

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from core.security import safe_csp_report_fields


security_logger = logging.getLogger("core.security.csp")


class HomeView(TemplateView):
    template_name = "core/home.html"


def robots_txt(request):
    """Publish crawl guidance; application authorization remains separate."""
    return HttpResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /accounts/profile/\n"
        "Disallow: /tasks/\n"
        "Disallow: /admin/\n",
        content_type="text/plain; charset=utf-8",
    )


def _legal_context():
    _, support_email = parseaddr(settings.DEFAULT_FROM_EMAIL)

    support_email = "rashdevatrealglobe@gmail.com"
    return {
        "support_email": support_email or settings.DEFAULT_FROM_EMAIL,
    }


class LegalPageView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_legal_context())
        return context


class PrivacyPolicyView(LegalPageView):
    template_name = "core/privacy_policy.html"


class TermsOfServiceView(LegalPageView):
    template_name = "core/terms_of_service.html"


@csrf_exempt
@require_POST
def csp_report(request):
    """Accept bounded browser CSP reports and log only safe summaries."""
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 16_384:
            return HttpResponse(status=413)
    except ValueError:
        return HttpResponse(status=400)

    body = request.body
    if len(body) > 16_384:
        return HttpResponse(status=413)

    try:
        report = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    directive, blocked_origin = safe_csp_report_fields(report)
    security_logger.warning(
        "Content Security Policy violation: directive=%s blocked_origin=%s",
        directive,
        blocked_origin,
    )
    return HttpResponse(status=204)

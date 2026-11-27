from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Attach the configured CSP in report-only or enforcement mode."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        if policy:
            header = (
                "Content-Security-Policy-Report-Only"
                if getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", True)
                else "Content-Security-Policy"
            )
            response[header] = policy
        return response

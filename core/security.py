"""Shared production security policy and CSP report parsing helpers."""

from urllib.parse import urlsplit


DEFAULT_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com",
        "report-uri /csp-report/",
    ]
)


def safe_csp_report_fields(report):
    """Return bounded, non-sensitive fields from a browser CSP report."""
    if isinstance(report, list):
        report = report[0] if report else {}
    if not isinstance(report, dict):
        return "unknown", "unknown"

    body = report.get("csp-report", report.get("body", report))
    if not isinstance(body, dict):
        return "unknown", "unknown"

    directive = str(
        body.get("effective-directive")
        or body.get("violated-directive")
        or "unknown"
    )
    blocked_uri = str(body.get("blocked-uri") or body.get("blockedURL") or "unknown")
    origin = urlsplit(blocked_uri).netloc or blocked_uri
    return (
        directive.replace("\r", " ").replace("\n", " ")[:120],
        origin.replace("\r", " ").replace("\n", " ")[:120],
    )

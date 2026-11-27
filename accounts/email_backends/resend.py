
import base64
import logging
from email.message import Message

import resend

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


class EmailBackend(BaseEmailBackend):
    """
    Django email backend using the Resend HTTP API.

    Compatible with Django's email backend connection interface.
    """


    def __init__(
        self,
        *,
        api_key=None,
        fail_silently=False,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.fail_silently = fail_silently
        self.api_key = api_key

        if not self.api_key:
            raise ValueError(
                "RESEND_API_KEY is required to use the Resend email backend."
            )

        
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                if self._send(message):
                    sent_count += 1

            except Exception:
                logger.exception(
                    "Failed to send email through Resend. Subject: %s",
                    message.subject,
                )

                if not self.fail_silently:
                    raise

        return sent_count

    def _send(self, message):
        recipients = message.to or []

        if not recipients:
            logger.warning(
                "Skipping email without a To recipient. Subject: %s",
                message.subject,
            )
            return False

        resend.api_key = self.api_key

        params = {
            "from": message.from_email,
            "to": recipients,
            "subject": message.subject,
        }

        if message.cc:
            params["cc"] = message.cc

        if message.bcc:
            params["bcc"] = message.bcc

        if message.reply_to:
            params["reply_to"] = message.reply_to

        html_content = None
        text_content = None

        if message.content_subtype == "html":
            html_content = message.body
        else:
            text_content = message.body

        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_content = content
            elif mimetype == "text/plain":
                text_content = content

        if html_content is not None:
            params["html"] = html_content

        if text_content is not None:
            params["text"] = text_content

        excluded_headers = {
            "from",
            "to",
            "cc",
            "bcc",
            "subject",
            "reply-to",
            "mime-version",
            "content-type",
            "content-transfer-encoding",
        }

        custom_headers = {
            key: str(value)
            for key, value in message.extra_headers.items()
            if key.lower() not in excluded_headers
        }

        if custom_headers:
            params["headers"] = custom_headers

        attachments = self._prepare_attachments(message)

        if attachments:
            params["attachments"] = attachments

        resend.Emails.send(params)

        logger.info(
            "Email accepted by Resend. Subject: %s",
            message.subject,
        )

        return True

    @staticmethod
    def _prepare_attachments(message):
        attachments = []

        for attachment in message.attachments:
            if isinstance(attachment, Message):
                filename = attachment.get_filename() or "attachment"
                content_type = attachment.get_content_type()
                content = attachment.get_payload(decode=True)

                if content is None:
                    content = attachment.get_payload()

            else:
                filename, content, content_type = attachment

            if isinstance(content, str):
                content = content.encode("utf-8")

            encoded_content = base64.b64encode(content).decode("ascii")

            attachments.append({
                "filename": filename,
                "content": encoded_content,
                "content_type": content_type or "application/octet-stream",
            })

        return attachments

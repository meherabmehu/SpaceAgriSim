"""Transactional email delivery for account verification and password reset.

Three delivery modes, in order of preference:

1. **configured SMTP** — `SPACEAGRISIM_SMTP_HOST` is set, so messages are sent for real.
2. **development outbox** — no SMTP and a non-production environment: the message is kept in a
   bounded in-memory outbox and the token is returned to the caller, so the flow is usable locally
   and in tests without inventing an email provider.
3. **production without SMTP** — the endpoint refuses with 503 rather than pretending it sent mail.
   A silent no-op here would leave every user permanently unable to verify or reset.

Nothing in this module logs a token in production: the outbox is development-only, and the SMTP
path never writes the token anywhere except the message body.
"""

from __future__ import annotations

import logging
import smtplib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Bounded so a long-running development server cannot grow without limit.
OUTBOX: deque = deque(maxlen=50)


class EmailDeliveryUnavailable(RuntimeError):
    """No delivery channel is configured and the environment forbids the dev outbox."""


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str
    sent_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def delivery_mode() -> str:
    """What `send` would actually do right now."""
    if settings.smtp_host:
        return "smtp"
    if settings.environment == "production":
        return "unconfigured"
    return "outbox"


def send(to: str, subject: str, body: str) -> Message:
    message = Message(to=to, subject=subject, body=body)
    mode = delivery_mode()
    if mode == "unconfigured":
        raise EmailDeliveryUnavailable(
            "Email delivery is not configured. Set SPACEAGRISIM_SMTP_HOST, "
            "SPACEAGRISIM_SMTP_PORT and SPACEAGRISIM_SMTP_FROM to enable account email.")
    if mode == "outbox":
        OUTBOX.append(message)
        logger.info("development outbox: queued '%s' for delivery", subject)
        return message
    _send_smtp(message)
    return message


def _send_smtp(message: Message) -> None:
    email = EmailMessage()
    email["From"] = settings.smtp_from or settings.smtp_user
    email["To"] = message.to
    email["Subject"] = message.subject
    email.set_content(message.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(email)
    except (smtplib.SMTPException, OSError) as exc:
        # The address and token stay out of the log; only the transport failure is recorded.
        logger.warning("SMTP delivery failed: %s", type(exc).__name__)
        raise EmailDeliveryUnavailable(
            "The mail server could not be reached, so no message was sent. "
            "Try again later or contact the operator.") from exc


def last_message_for(address: str) -> Message | None:
    """Most recent development-outbox message for an address, for tests and local use."""
    for message in reversed(OUTBOX):
        if message.to == address:
            return message
    return None


def clear_outbox() -> None:
    OUTBOX.clear()

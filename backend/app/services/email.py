import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

from app.config import (
    APP_NAME,
    PASSWORD_RESET_URL_TEMPLATE,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
)


class EmailConfigurationError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


def build_password_reset_url(
    token: str,
    request_origin: str | None = None,
) -> str:
    encoded_token = quote(token, safe="")
    template = PASSWORD_RESET_URL_TEMPLATE.strip()

    if template:
        if "{token}" in template:
            return template.replace("{token}", encoded_token)

        separator = "&" if "?" in template else "?"
        return f"{template}{separator}reset_password_token={encoded_token}"

    if request_origin:
        return f"{request_origin.rstrip('/')}/?reset_password_token={encoded_token}"

    raise EmailConfigurationError(
        "Password reset URL is not configured on the server."
    )


def send_password_reset_email(
    *,
    recipient_email: str,
    recipient_name: str,
    reset_token: str,
    request_origin: str | None = None,
) -> str:
    missing_settings = []
    if not SMTP_HOST:
        missing_settings.append("SMTP_HOST")
    if not SMTP_FROM_EMAIL:
        missing_settings.append("SMTP_FROM_EMAIL")

    if missing_settings:
        raise EmailConfigurationError(
            "Password reset email is not configured on the server. Missing: "
            + ", ".join(missing_settings)
        )

    reset_url = build_password_reset_url(reset_token, request_origin=request_origin)
    message = EmailMessage()
    message["Subject"] = f"Reset your {APP_NAME} password"
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    message["To"] = recipient_email

    message.set_content(
        "\n".join(
            [
                f"Hello {recipient_name or 'there'},",
                "",
                f"We received a request to reset your {APP_NAME} password.",
                "Use the link below to choose a new password:",
                reset_url,
                "",
                "If you did not request this change, you can safely ignore this email.",
                "This link can only be used once and expires soon.",
            ]
        )
    )

    try:
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(
                SMTP_HOST,
                SMTP_PORT,
                context=ssl.create_default_context(),
                timeout=15,
            ) as server:
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.ehlo()
                if SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
    except Exception as exc:  # pragma: no cover - exercised through tests via patching
        raise EmailDeliveryError("Failed to send password reset email.") from exc

    return reset_url

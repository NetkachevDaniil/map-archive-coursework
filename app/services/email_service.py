import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_verification_email(to_email: str, verify_link: str) -> tuple[bool, str | None]:
    settings = get_settings()

    subject = "Подтверждение регистрации в OrientMaps"
    body = (
        "Здравствуйте!\n\n"
        "Для завершения регистрации перейдите по ссылке:\n"
        f"{verify_link}\n\n"
        "Если вы не регистрировались, просто проигнорируйте письмо."
    )

    # Если SMTP не настроен, выводим ссылку в консоль для локальной проверки.
    if not settings.smtp_host:
        print(f"[EMAIL DEBUG] {to_email} -> {verify_link}")
        return False, "SMTP не настроен. Ссылка подтверждения выведена в консоль сервера."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_sender
    message["To"] = to_email
    message.set_content(body)

    try:
        if settings.smtp_use_ssl:
            smtp_obj = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
        else:
            smtp_obj = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)

        with smtp_obj as smtp:
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True, None
    except Exception as exc:
        print(f"[EMAIL ERROR] Failed to send verification to {to_email}: {exc}")
        return False, f"Не удалось отправить письмо: {exc}"

"""Email notifications for address-normaliser jobs.

Sends job start/complete/failed emails to the file uploader and admin.
No-op if SMTP credentials are not configured.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import (
    CLIENT_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)


def _is_configured():
    return all([SMTP_USER, SMTP_PASSWORD, CLIENT_EMAIL])


def _send_email(subject, body, to_email=None):
    if not _is_configured():
        return

    recipient = to_email or CLIENT_EMAIL
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {recipient}: {subject}", flush=True)
    except Exception as e:
        print(f"Failed to send email: {e}", flush=True)


def notify_job_started(filename, record_count=None, uploader_email=None):
    subject = f"Address Normaliser - Processing Started: {filename}"

    estimate = ""
    if record_count:
        estimate = f"  Records: {record_count:,}\n\n"

    body = (
        f"Hi,\n\n"
        f"Your file '{filename}' has been received and is now being processed.\n\n"
        f"{estimate}"
        f"You will receive another notification when processing is complete.\n\n"
        f"Regards,\nAddress Normaliser Service"
    )
    _send_email(subject, body, to_email=uploader_email)


def notify_job_completed(filename, stats, uploader_email=None):
    subject = f"Address Normaliser - Processing Complete: {filename}"
    body = (
        f"Hi,\n\n"
        f"Your file has been processed successfully.\n\n"
        f"  File: {filename}\n"
        f"  Total Records: {stats.get('total', 0):,}\n"
        f"  Processed: {stats.get('processed', 0):,}\n"
        f"  Low Confidence: {stats.get('low_confidence', 0):,}\n"
        f"  No Address: {stats.get('no_address', 0):,}\n\n"
        f"Results are available in your Google Drive Completed folder.\n\n"
        f"Regards,\nAddress Normaliser Service"
    )
    _send_email(subject, body, to_email=uploader_email)


def notify_job_failed(filename, error_message, uploader_email=None):
    subject = f"Address Normaliser - Processing Issue: {filename}"
    body = (
        f"Hi,\n\n"
        f"We encountered an issue while processing your file '{filename}'.\n\n"
        f"Our team has been notified and will look into it.\n\n"
        f"Regards,\nAddress Normaliser Service"
    )
    _send_email(subject, body, to_email=uploader_email)

    admin_subject = f"[ADMIN] Address Normaliser job failed - {filename}"
    admin_body = f"File: {filename}\nError: {error_message}"
    _send_email(admin_subject, admin_body, to_email=SMTP_USER)

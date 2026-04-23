import os

GDRIVE_TOKEN_PATH = os.getenv("GDRIVE_TOKEN_PATH", "credentials/token.json")
GDRIVE_CLIENT_SECRETS_PATH = os.getenv("GDRIVE_CLIENT_SECRETS_PATH", "credentials/client_secret.json")
GDRIVE_UPLOAD_FOLDER_ID = os.getenv("GDRIVE_UPLOAD_FOLDER_ID", "")
GDRIVE_PROCESSING_FOLDER_ID = os.getenv("GDRIVE_PROCESSING_FOLDER_ID", "")
GDRIVE_COMPLETED_FOLDER_ID = os.getenv("GDRIVE_COMPLETED_FOLDER_ID", "")
GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID = os.getenv("GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID", "")
GDRIVE_COMPLETED_OUTPUT_FOLDER_ID = os.getenv("GDRIVE_COMPLETED_OUTPUT_FOLDER_ID", "")
GDRIVE_COMPLETED_LOGS_FOLDER_ID = os.getenv("GDRIVE_COMPLETED_LOGS_FOLDER_ID", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
NOMINATIM_ENABLED = os.getenv("NOMINATIM_ENABLED", "false").lower() == "true"
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

# Online validation (optional)
ONLINE_VALIDATION_ENABLED = os.getenv("ONLINE_VALIDATION_ENABLED", "false").lower() == "true"
ONLINE_VALIDATION_MAILABLE_ONLY = os.getenv("ONLINE_VALIDATION_MAILABLE_ONLY", "true").lower() == "true"
ONLINE_VALIDATION_REVIEW_NO_RESULT = os.getenv("ONLINE_VALIDATION_REVIEW_NO_RESULT", "false").lower() == "true"
ONLINE_VALIDATION_PROVIDERS = tuple(
    p.strip().lower()
    for p in os.getenv("ONLINE_VALIDATION_PROVIDERS", "tomtom,geoapify,locationiq").split(",")
    if p.strip()
)

ONLINE_VALIDATION_TIMEOUT_SECONDS = int(os.getenv("ONLINE_VALIDATION_TIMEOUT_SECONDS", "10"))

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "")
LOCATIONIQ_API_KEY = os.getenv("LOCATIONIQ_API_KEY", "")

# Email notifications (optional - leave empty to disable)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL", "")

ADDR_COLUMN_PREFIX = "ADDR"
IC_COLUMN = "ICNO"
NAME_COLUMN = "NAME"

EXCEL_MIMETYPES = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]

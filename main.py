import logging
import os
import sys
import time
import tempfile

import pandas as pd

from src import config
from src import gdrive
from src import notifier
from src.pipeline import process_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def process_one_file(file_info):
    file_id = file_info["id"]
    filename = file_info["name"]
    uploader_email = file_info.get("lastModifyingUser", {}).get("emailAddress")
    logger.info("Processing: %s (uploaded by %s)", filename, uploader_email or "unknown")

    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, filename)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(tmp, f"{base_name}_NORMALISED.xlsx")

        gdrive.download_file(file_id, input_path)
        gdrive.move_to_processing(file_id)

        record_count = None
        try:
            record_count = len(pd.read_excel(input_path))
        except Exception:
            pass
        notifier.notify_job_started(filename, record_count, uploader_email)

        try:
            stats = process_file(input_path, output_path)
        except Exception as e:
            logger.exception("Processing failed: %s", filename)
            notifier.notify_job_failed(filename, str(e), uploader_email)
            raise

        gdrive.upload_results(output_path, stats, filename)
        gdrive.move_to_archive(file_id)

        notifier.notify_job_completed(filename, stats, uploader_email)

    logger.info("Done: %s — %s", filename, stats)


def main():
    required = [
        "GDRIVE_UPLOAD_FOLDER_ID",
        "GDRIVE_PROCESSING_FOLDER_ID",
        "GDRIVE_COMPLETED_FOLDER_ID",
        "GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID",
    ]

    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error("Missing env vars: %s", missing)
        sys.exit(1)

    logger.info(
        "Address Normaliser started. Polling every %ds.",
        config.POLL_INTERVAL_SECONDS,
    )

    while True:
        try:
            files = gdrive.list_upload_folder()
            if files:
                process_one_file(files[0])
            else:
                logger.debug("No files in upload folder.")
        except Exception:
            logger.exception("Error during processing")

        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

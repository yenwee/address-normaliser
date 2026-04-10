import logging
import os
import sys
import time
import tempfile

from src import config
from src import gdrive
from src.pipeline import process_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def process_one_file(file_info):
    file_id = file_info["id"]
    filename = file_info["name"]
    logger.info("Processing: %s", filename)

    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, filename)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(tmp, f"{base_name}_NORMALISED.xlsx")

        gdrive.download_file(file_id, input_path)
        gdrive.move_to_processing(file_id)

        stats = process_file(input_path, output_path)

        gdrive.upload_results(output_path, stats, filename)
        gdrive.move_to_archive(file_id)

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

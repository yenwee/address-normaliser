"""Fix existing xlsx files on Google Drive that have inlineStr cells.

Downloads files from the Drive Output folder, converts inline strings to
shared strings, and uploads back. Preserves cell data and formatting.
"""
import argparse
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.io import gdrive
from src.config import (
    GDRIVE_COMPLETED_FOLDER_ID,
    GDRIVE_COMPLETED_OUTPUT_FOLDER_ID,
)
from src.io.excel_writer import _convert_inline_to_shared_strings


def list_output_files(name_contains=None):
    service = gdrive._get_service()
    folder = GDRIVE_COMPLETED_OUTPUT_FOLDER_ID or gdrive._ensure_subfolder(
        "Output", GDRIVE_COMPLETED_FOLDER_ID
    )
    q = f"'{folder}' in parents and trashed=false and name contains '.xlsx'"
    if name_contains:
        q += f" and name contains '{name_contains}'"
    results = service.files().list(
        q=q,
        fields="files(id, name, size)",
        pageSize=1000,
    ).execute()
    return results.get("files", []), folder


def has_inline_strings(xlsx_path):
    with zipfile.ZipFile(xlsx_path) as z:
        sheet_names = [n for n in z.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")]
        for name in sheet_names:
            with z.open(name) as f:
                content = f.read().decode("utf-8", errors="replace")
            if 'inlineStr' in content:
                return True
    return False


def fix_file(file_id, filename, folder_id):
    service = gdrive._get_service()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(tmp_fd)
    try:
        gdrive.download_file(file_id, tmp_path)
        if not has_inline_strings(tmp_path):
            print(f"  Skip {filename} (no inlineStr)")
            return False
        _convert_inline_to_shared_strings(tmp_path)
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(tmp_path)
        service.files().update(fileId=file_id, media_body=media).execute()
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", help="Only fix files whose name contains this substring")
    parser.add_argument("--dry-run", action="store_true", help="List files that would be fixed")
    args = parser.parse_args()

    files, folder_id = list_output_files(args.filter)
    print(f"Found {len(files)} xlsx files in Output folder")

    fixed = 0
    for f in files:
        print(f"\n{f['name']} ({int(f.get('size', 0)):,} bytes)")
        if args.dry_run:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
            os.close(tmp_fd)
            try:
                gdrive.download_file(f["id"], tmp_path)
                if has_inline_strings(tmp_path):
                    print("  [DRY] Would fix")
                    fixed += 1
                else:
                    print("  [DRY] No inlineStr, skip")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        else:
            if fix_file(f["id"], f["name"], folder_id):
                print(f"  Fixed")
                fixed += 1

    print(f"\n{'Would fix' if args.dry_run else 'Fixed'}: {fixed} / {len(files)}")


if __name__ == "__main__":
    main()

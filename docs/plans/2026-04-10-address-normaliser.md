# Address Normaliser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically select the best mailing address from up to 40 address variants per IC number, normalize it, validate against Malaysian postcode DB, and output a single formatted mailing block per IC.

**Architecture:** Google Drive polling service (same pattern as str-scrape). Reads Excel files with ADDR0-ADDR40 columns, parses comma-separated address fields, normalizes abbreviations, clusters similar addresses via fuzzy matching, scores by frequency x completeness, validates postcode/city/state, and outputs Excel with formatted mailing addresses. Nominatim geocoding used only for low-confidence results.

**Tech Stack:** Python 3.11, pandas, xlrd, openpyxl, rapidfuzz, requests, google-api-python-client

---

## Project Structure

```
address-normaliser/
├── main.py                     # Entry point - polls Drive, orchestrates
├── src/
│   ├── __init__.py
│   ├── config.py               # Env vars and constants
│   ├── gdrive.py               # Google Drive helpers (from str-scrape)
│   ├── parser.py               # Parse comma-separated ADDR fields
│   ├── normaliser.py           # Abbreviation expansion, cleanup
│   ├── clusterer.py            # Fuzzy match clustering
│   ├── scorer.py               # Completeness + frequency scoring
│   ├── validator.py            # Postcode DB validation + correction
│   ├── nominatim.py            # Geocoding fallback for low-confidence
│   ├── formatter.py            # Mailing block formatter
│   └── pipeline.py             # Main orchestration
├── data/
│   └── postcodes.json          # Malaysian postcode DB (heiswayi)
├── credentials/                # OAuth tokens (gitignored)
├── scripts/
│   ├── authorize_gdrive.py     # One-time OAuth setup (from str-scrape)
│   └── setup_drive.py          # One-time Drive folder creation
├── tests/
│   ├── test_parser.py
│   ├── test_normaliser.py
│   ├── test_clusterer.py
│   ├── test_scorer.py
│   ├── test_validator.py
│   └── test_pipeline.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

### Task 1: Project Scaffold + Malaysian Postcode DB

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `data/postcodes.json`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create requirements.txt**

```
pandas>=2.0.0
xlrd>=2.0.1
openpyxl>=3.1.0
rapidfuzz>=3.0.0
requests>=2.31.0
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
```

**Step 2: Create .env.example**

```
GDRIVE_TOKEN_PATH=credentials/token.json
GDRIVE_CLIENT_SECRETS_PATH=credentials/client_secret.json
GDRIVE_UPLOAD_FOLDER_ID=
GDRIVE_PROCESSING_FOLDER_ID=
GDRIVE_COMPLETED_FOLDER_ID=
GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID=
POLL_INTERVAL_SECONDS=30
NOMINATIM_ENABLED=false
CONFIDENCE_THRESHOLD=0.6
```

**Step 3: Create src/config.py**

```python
import os

GDRIVE_TOKEN_PATH = os.getenv("GDRIVE_TOKEN_PATH", "credentials/token.json")
GDRIVE_CLIENT_SECRETS_PATH = os.getenv("GDRIVE_CLIENT_SECRETS_PATH", "credentials/client_secret.json")
GDRIVE_UPLOAD_FOLDER_ID = os.getenv("GDRIVE_UPLOAD_FOLDER_ID", "")
GDRIVE_PROCESSING_FOLDER_ID = os.getenv("GDRIVE_PROCESSING_FOLDER_ID", "")
GDRIVE_COMPLETED_FOLDER_ID = os.getenv("GDRIVE_COMPLETED_FOLDER_ID", "")
GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID = os.getenv("GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
NOMINATIM_ENABLED = os.getenv("NOMINATIM_ENABLED", "false").lower() == "true"
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

ADDR_COLUMN_PREFIX = "ADDR"
IC_COLUMN = "ICNO"
NAME_COLUMN = "NAME"

EXCEL_MIMETYPES = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
```

**Step 4: Download postcodes.json into data/**

Source: `heiswayi/malaysia-postcodes` GitHub repo → `data/json/postcodes.json`

**Step 5: Create .gitignore**

```
credentials/
.env
__pycache__/
*.pyc
jobs/
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: project scaffold with config and postcode DB"
```

---

### Task 1B: Copy Credentials + Create Drive Folders

**Files:**
- Create: `scripts/setup_drive.py`
- Copy: `credentials/` from str-scrape

**Step 1: Copy OAuth credentials from str-scrape**

```bash
cp -r /Users/wee/Desktop/SideQuest/str-scrape/credentials /Users/wee/Desktop/SideQuest/address-normaliser/credentials
```

This reuses the same Google account OAuth token. No need to re-authorize.

**Step 2: Create scripts/setup_drive.py**

```python
#!/usr/bin/env python3
"""One-time setup: create Google Drive folder structure for address-normaliser.

Creates folders under the existing 'Falcon Field' shared folder in Google Drive.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.gdrive import _get_service

# Parent: "Falcon Field" folder (sibling to "STR Automation")
FALCON_FIELD_FOLDER_ID = "1I9e4nu0t_3LxFw6gX5szG8YULTUrnZHx"

FOLDER_STRUCTURE = {
    "Address Normaliser": {
        "Upload": {},
        "Processing": {},
        "Completed": {
            "Output": {},
            "Logs": {},
        },
        "Archive": {
            "Upload": {},
            "Completed": {},
        },
    },
}

ENV_MAPPING = {
    "Upload": "GDRIVE_UPLOAD_FOLDER_ID",
    "Processing": "GDRIVE_PROCESSING_FOLDER_ID",
    "Completed": "GDRIVE_COMPLETED_FOLDER_ID",
    "Archive": "GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID",
    "Output": "GDRIVE_COMPLETED_OUTPUT_FOLDER_ID",
    "Logs": "GDRIVE_COMPLETED_LOGS_FOLDER_ID",
}


def create_folder(service, name, parent_id=None):
    """Create a Drive folder and return its ID."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def create_structure(service, structure, parent_id=None, env_vars=None):
    """Recursively create folder structure. Returns dict of env var mappings."""
    if env_vars is None:
        env_vars = {}

    for name, children in structure.items():
        folder_id = create_folder(service, name, parent_id)
        print(f"  Created: {name} -> {folder_id}")

        if name in ENV_MAPPING:
            env_vars[ENV_MAPPING[name]] = folder_id

        if children:
            create_structure(service, children, folder_id, env_vars)

    return env_vars


def main():
    print("Setting up Google Drive folders for Address Normaliser...")
    print(f"Parent folder: Falcon Field ({FALCON_FIELD_FOLDER_ID})")
    service = _get_service()
    env_vars = create_structure(service, FOLDER_STRUCTURE, parent_id=FALCON_FIELD_FOLDER_ID)

    print("\n--- Add these to your .env file ---\n")
    for key, value in sorted(env_vars.items()):
        print(f"{key}={value}")

    print("\nDone! Copy the above into your .env file.")


if __name__ == "__main__":
    main()
```

**Step 3: Run the setup script**

```bash
cd /Users/wee/Desktop/SideQuest/address-normaliser
python scripts/setup_drive.py
```

Expected output: folder IDs printed for each env var. Copy into `.env`.

**Step 4: Create .env from output**

```bash
cp .env.example .env
# Paste the folder IDs from setup script output
```

**Step 5: Verify folders exist in Google Drive**

Open Google Drive in browser → confirm "Address Normaliser" folder with subfolders.

**Step 6: Commit (exclude credentials and .env)**

```bash
git add scripts/setup_drive.py && git commit -m "feat: Drive folder setup script"
```

---

### Task 2: Address Parser

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`

Parses comma-separated ADDR strings into structured dicts. Inferred field positions from data analysis:

```
Position 0: address_line (street address)
Position 1: address_line2 (area/taman)
Position 2: address_line3 (additional / sometimes junk)
Position 3: postcode (5-digit, most consistent position)
Position 4: city
Position 5: state
Position 6: trailing empty (ignored)
```

Fields 4 and 5 sometimes swap (city/state) — parser must detect this using a known-states set.

**Step 1: Write failing tests**

```python
# tests/test_parser.py
from src.parser import parse_address, parse_all_addresses
import pandas as pd

def test_parse_standard_7_fields():
    raw = "NO 235 LRG 5 JALAN KERETAPI, TAMAN SPRINGFIELD, , 93250, KUCHING, SARAWAK, "
    result = parse_address(raw)
    assert result["address_line"] == "NO 235 LRG 5 JALAN KERETAPI"
    assert result["address_line2"] == "TAMAN SPRINGFIELD"
    assert result["postcode"] == "93250"
    assert result["city"] == "KUCHING"
    assert result["state"] == "SARAWAK"

def test_parse_swapped_city_state():
    raw = "NO.1 LRG PUTERI GUNUNG SIMPANG AMPAT, , , 14100, PULAU PINANG, , "
    result = parse_address(raw)
    assert result["postcode"] == "14100"
    assert result["state"] == "PULAU PINANG"

def test_parse_null_fields():
    raw = "NO 55 BATU 8 JALAN TRONG CHANGKAT JERING, NULL, , 34850, NULL, PERAK, "
    result = parse_address(raw)
    assert result["address_line2"] == ""
    assert result["city"] == ""
    assert result["state"] == "PERAK"

def test_parse_empty_address():
    raw = ", , , , , , "
    result = parse_address(raw)
    assert result is None

def test_parse_junk_ic_number():
    raw = ", , 60168240208, , , , "
    result = parse_address(raw)
    assert result is None

def test_parse_8_field_record():
    raw = "LOT 265, Batu, TAMAN PASAR PUTIH PHASE 1, , 88100, KOTA KINABALU, SABAH, "
    result = parse_address(raw)
    assert result["postcode"] == "88100"
    assert result["state"] == "SABAH"

def test_parse_all_addresses_from_row():
    row = pd.Series({
        "ICNO": "900208125173",
        "NAME": "AZMAN",
        "ADDR0": "LOT 265, Batu, TAMAN PASAR PUTIH, , 88100, KOTA KINABALU, SABAH, ",
        "ADDR1": "LORONG 5 -LOT 265 TAMAN PARK PUTIH, , , 88100, KOTA KINABALU, SABAH, ",
        "ADDR2": ", , , , , , ",
    })
    results = parse_all_addresses(row, ["ADDR0", "ADDR1", "ADDR2"])
    assert len(results) == 2  # ADDR2 is empty, should be excluded
```

**Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_parser.py -v
```

**Step 3: Implement parser**

```python
# src/parser.py
import re

KNOWN_STATES = {
    "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN",
    "PAHANG", "PERAK", "PERLIS", "PULAU PINANG", "SABAH",
    "SARAWAK", "SELANGOR", "TERENGGANU",
    "WILAYAH PERSEKUTUAN", "W.P. KUALA LUMPUR", "WP KUALA LUMPUR",
    "WP", "WPKL", "KL", "KUALA LUMPUR", "PENANG",
    "N. SEMBILAN", "N.SEMBILAN", "LABUAN", "PUTRAJAYA",
    "W.P. PUTRAJAYA", "W.P. LABUAN",
}

POSTCODE_RE = re.compile(r"^\d{5}$")
JUNK_RE = re.compile(r"^\d{10,12}$")  # IC/phone numbers


def parse_address(raw):
    """Parse a comma-separated address string into structured dict."""
    if not raw or not isinstance(raw, str):
        return None

    parts = [p.strip() for p in raw.split(",")]

    # Clean NULL strings
    parts = ["" if p.upper() == "NULL" else p for p in parts]

    # Check if all fields are empty or junk
    meaningful = [p for p in parts if p and not JUNK_RE.match(p.replace("-", "").replace(" ", ""))]
    if not meaningful:
        return None

    # Find postcode position (scan for 5-digit field)
    postcode = ""
    postcode_idx = -1
    for i, p in enumerate(parts):
        if POSTCODE_RE.match(p):
            postcode = p
            postcode_idx = i
            break

    # If no standalone postcode, try extracting from address line
    if not postcode:
        for i, p in enumerate(parts):
            m = re.search(r"\b(\d{5})\b", p)
            if m:
                postcode = m.group(1)
                break

    # Extract city and state from fields after postcode
    city = ""
    state = ""

    if postcode_idx >= 0:
        remaining = [p for p in parts[postcode_idx + 1:] if p]
        for field in remaining:
            if field.upper().strip() in KNOWN_STATES:
                state = field.upper().strip()
            elif not city:
                city = field.upper().strip()
    else:
        # No postcode found — scan all fields for state
        for p in parts:
            if p.upper().strip() in KNOWN_STATES:
                state = p.upper().strip()

    # Address lines = everything before postcode (or first 3 fields)
    if postcode_idx >= 0:
        addr_parts = parts[:postcode_idx]
    else:
        addr_parts = parts[:3]

    # Filter out empty/junk from address lines
    addr_lines = [p for p in addr_parts if p and not JUNK_RE.match(p.replace("-", "").replace(" ", ""))]

    address_line = addr_lines[0].strip() if len(addr_lines) > 0 else ""
    address_line2 = addr_lines[1].strip() if len(addr_lines) > 1 else ""
    address_line3 = addr_lines[2].strip() if len(addr_lines) > 2 else ""

    # Also check if city/state appear before postcode (swapped format)
    if not state:
        for p in addr_parts:
            if p.upper().strip() in KNOWN_STATES:
                state = p.upper().strip()

    if not address_line:
        return None

    return {
        "address_line": address_line.upper(),
        "address_line2": address_line2.upper(),
        "address_line3": address_line3.upper(),
        "postcode": postcode,
        "city": city,
        "state": state,
        "raw": raw.strip(),
    }


def parse_all_addresses(row, addr_columns):
    """Parse all ADDR columns from a DataFrame row, return list of valid parsed addresses."""
    results = []
    for col in addr_columns:
        val = row.get(col)
        if val and isinstance(val, str) and val.strip():
            parsed = parse_address(val)
            if parsed:
                parsed["source_column"] = col
                results.append(parsed)
    return results
```

**Step 4: Run tests — expect PASS**

```bash
pytest tests/test_parser.py -v
```

**Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py && git commit -m "feat: address parser with field detection and junk filtering"
```

---

### Task 3: Address Normaliser (Abbreviation Expansion)

**Files:**
- Create: `src/normaliser.py`
- Create: `tests/test_normaliser.py`

**Step 1: Write failing tests**

```python
# tests/test_normaliser.py
from src.normaliser import normalise_address, expand_abbreviations

def test_expand_jln():
    assert "JALAN" in expand_abbreviations("JLN AMPANG")

def test_expand_tmn():
    assert "TAMAN" in expand_abbreviations("TMN MELAWATI")

def test_expand_lrg():
    assert "LORONG" in expand_abbreviations("LRG 5")

def test_expand_kg():
    assert "KAMPUNG" in expand_abbreviations("KG BATU MUDA")

def test_expand_multiple():
    result = expand_abbreviations("NO 1 JLN 2 TMN MELAWATI LRG 3")
    assert "JALAN" in result
    assert "TAMAN" in result
    assert "LORONG" in result

def test_no_partial_expansion():
    """JLNS should NOT become JALANS"""
    result = expand_abbreviations("JLNS TEST")
    assert "JALANS" not in result

def test_normalise_full_address():
    addr = {
        "address_line": "NO 1 JLN 2",
        "address_line2": "TMN MELAWATI",
        "address_line3": "",
        "postcode": "53100",
        "city": "KL",
        "state": "WILAYAH PERSEKUTUAN",
        "raw": "test",
    }
    result = normalise_address(addr)
    assert result["address_line"] == "NO 1 JALAN 2"
    assert result["address_line2"] == "TAMAN MELAWATI"
    assert result["state"] == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

def test_normalise_extra_whitespace():
    addr = {
        "address_line": "NO  1   JLN   2",
        "address_line2": "",
        "address_line3": "",
        "postcode": "53100",
        "city": "KUALA LUMPUR",
        "state": "WP",
        "raw": "test",
    }
    result = normalise_address(addr)
    assert "  " not in result["address_line"]
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement normaliser**

```python
# src/normaliser.py
import re

ABBREVIATIONS = {
    r"\bJLN\b": "JALAN",
    r"\bJL\b": "JALAN",
    r"\bTMN\b": "TAMAN",
    r"\bLRG\b": "LORONG",
    r"\bKG\b": "KAMPUNG",
    r"\bKPG\b": "KAMPUNG",
    r"\bKMPG\b": "KAMPUNG",
    r"\bBDR\b": "BANDAR",
    r"\bSG\b": "SUNGAI",
    r"\bBT\b": "BATU",
    r"\bPSR\b": "PASAR",
    r"\bPPR\b": "PROJEK PERUMAHAN RAKYAT",
    r"\bSBG\b": "SUBANG",
    r"\bPJY\b": "PUTRAJAYA",
    r"\bSEC\b": "SEKSYEN",
    r"\bSEK\b": "SEKSYEN",
    r"\bKWS\b": "KAWASAN",
    r"\bPER\b": "PERINDUSTRIAN",
    r"\bIND\b": "INDUSTRI",
    r"\bSRI\b": "SERI",
    r"\bDR\b": "DARUL",
}

STATE_NORMALISATIONS = {
    "WP": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WPKL": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "KL": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "W.P. KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WP KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "PENANG": "PULAU PINANG",
    "N. SEMBILAN": "NEGERI SEMBILAN",
    "N.SEMBILAN": "NEGERI SEMBILAN",
    "W.P. PUTRAJAYA": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    "W.P. LABUAN": "WILAYAH PERSEKUTUAN LABUAN",
    "LABUAN": "WILAYAH PERSEKUTUAN LABUAN",
    "PUTRAJAYA": "WILAYAH PERSEKUTUAN PUTRAJAYA",
}


def expand_abbreviations(text):
    """Expand common Malaysian address abbreviations using word-boundary regex."""
    text = text.upper()
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text)
    return text


def normalise_text(text):
    """Normalise whitespace and casing."""
    text = text.upper().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", " ", text)  # "LORONG 5 -LOT" → "LORONG 5 LOT"
    return text


def normalise_state(state):
    """Normalise state name to standard form."""
    state = state.upper().strip()
    return STATE_NORMALISATIONS.get(state, state)


def normalise_address(addr):
    """Normalise a parsed address dict — expand abbreviations, clean whitespace, fix state."""
    return {
        "address_line": expand_abbreviations(normalise_text(addr["address_line"])),
        "address_line2": expand_abbreviations(normalise_text(addr["address_line2"])),
        "address_line3": expand_abbreviations(normalise_text(addr["address_line3"])),
        "postcode": addr["postcode"].strip(),
        "city": normalise_text(addr["city"]),
        "state": normalise_state(addr.get("state", "")),
        "raw": addr["raw"],
        "source_column": addr.get("source_column", ""),
    }
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/normaliser.py tests/test_normaliser.py && git commit -m "feat: address normaliser with abbreviation expansion"
```

---

### Task 4: Completeness Scorer

**Files:**
- Create: `src/scorer.py`
- Create: `tests/test_scorer.py`

**Step 1: Write failing tests**

```python
# tests/test_scorer.py
from src.scorer import score_completeness

def test_complete_address_high_score():
    addr = {
        "address_line": "NO 235 LORONG 5 JALAN KERETAPI",
        "address_line2": "TAMAN SPRINGFIELD",
        "address_line3": "",
        "postcode": "93250",
        "city": "KUCHING",
        "state": "SARAWAK",
    }
    score = score_completeness(addr)
    assert score >= 8  # has postcode(3) + city(2) + state(2) + street_number(1) + street_name(1)

def test_minimal_address_low_score():
    addr = {
        "address_line": "KAMPUNG PARIS 3",
        "address_line2": "",
        "address_line3": "",
        "postcode": "",
        "city": "",
        "state": "",
    }
    score = score_completeness(addr)
    assert score <= 2

def test_postcode_only():
    addr = {
        "address_line": "SOME PLACE",
        "address_line2": "",
        "address_line3": "",
        "postcode": "90200",
        "city": "",
        "state": "",
    }
    score = score_completeness(addr)
    assert 3 <= score <= 5
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement scorer**

```python
# src/scorer.py
import re

STREET_NUMBER_RE = re.compile(r"\b(NO|LOT|UNIT|BLK|BLOK)\b", re.IGNORECASE)
STREET_NAME_RE = re.compile(r"\b(JALAN|LORONG|PERSIARAN|LEBUH|LINTANG|LENGKOK)\b", re.IGNORECASE)
AREA_RE = re.compile(r"\b(TAMAN|KAMPUNG|BANDAR|DESA|PANGSAPURI|FLAT|APARTMENT)\b", re.IGNORECASE)


def score_completeness(addr):
    """Score an address by completeness. Higher = more complete."""
    score = 0

    if addr.get("postcode") and re.match(r"^\d{5}$", addr["postcode"]):
        score += 3

    if addr.get("city"):
        score += 2

    if addr.get("state"):
        score += 2

    address_text = f"{addr.get('address_line', '')} {addr.get('address_line2', '')}"

    if STREET_NUMBER_RE.search(address_text):
        score += 1

    if STREET_NAME_RE.search(address_text):
        score += 1

    if AREA_RE.search(address_text):
        score += 1

    if addr.get("address_line2"):
        score += 1

    return score
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/scorer.py tests/test_scorer.py && git commit -m "feat: address completeness scorer"
```

---

### Task 5: Fuzzy Clusterer

**Files:**
- Create: `src/clusterer.py`
- Create: `tests/test_clusterer.py`

Groups address variants that refer to the same physical location.

**Step 1: Write failing tests**

```python
# tests/test_clusterer.py
from src.clusterer import cluster_addresses

def test_cluster_same_address_variants():
    addresses = [
        {"address_line": "NO 235 LORONG 5 JALAN KERETAPI", "address_line2": "TAMAN SPRINGFIELD", "address_line3": "", "postcode": "93250", "city": "KUCHING", "state": "SARAWAK", "raw": "a", "source_column": "ADDR0"},
        {"address_line": "NO 235 LORONG 5 TAMAN SPRINGFIELD JALAN KERETAPI", "address_line2": "", "address_line3": "", "postcode": "93250", "city": "KUCHING", "state": "SARAWAK", "raw": "b", "source_column": "ADDR1"},
        {"address_line": "NO 177 LORONG 5 OFF JALAN KERETAPI", "address_line2": "TAMAN SPRINGFIELD", "address_line3": "", "postcode": "93350", "city": "KUCHING", "state": "SARAWAK", "raw": "c", "source_column": "ADDR2"},
    ]
    clusters = cluster_addresses(addresses)
    # First two should cluster together (same address, slight reorder)
    # Third might cluster with them (similar but different number + postcode)
    assert len(clusters) >= 1
    assert len(clusters) <= 2

def test_cluster_different_addresses():
    addresses = [
        {"address_line": "NO 235 LORONG 5 JALAN KERETAPI", "address_line2": "TAMAN SPRINGFIELD", "address_line3": "", "postcode": "93250", "city": "KUCHING", "state": "SARAWAK", "raw": "a", "source_column": "ADDR0"},
        {"address_line": "NO 6A JALAN 2/12A", "address_line2": "KAMPUNG BATU MUDA", "address_line3": "", "postcode": "51100", "city": "KUALA LUMPUR", "state": "WP", "raw": "b", "source_column": "ADDR1"},
    ]
    clusters = cluster_addresses(addresses)
    assert len(clusters) == 2  # Completely different addresses

def test_cluster_empty_input():
    assert cluster_addresses([]) == []
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement clusterer**

```python
# src/clusterer.py
from rapidfuzz import fuzz


def _address_text(addr):
    """Combine address fields into single comparable string."""
    parts = [
        addr.get("address_line", ""),
        addr.get("address_line2", ""),
        addr.get("postcode", ""),
    ]
    return " ".join(p for p in parts if p).upper()


def _similarity(addr1, addr2):
    """Token-based similarity between two addresses (0-100)."""
    text1 = _address_text(addr1)
    text2 = _address_text(addr2)
    return fuzz.token_sort_ratio(text1, text2)


def cluster_addresses(addresses, threshold=65):
    """Cluster addresses by fuzzy similarity. Returns list of clusters (each a list of addresses)."""
    if not addresses:
        return []

    clusters = []
    assigned = [False] * len(addresses)

    for i, addr in enumerate(addresses):
        if assigned[i]:
            continue

        cluster = [addr]
        assigned[i] = True

        for j in range(i + 1, len(addresses)):
            if assigned[j]:
                continue
            sim = _similarity(addr, addresses[j])
            if sim >= threshold:
                cluster.append(addresses[j])
                assigned[j] = True

        clusters.append(cluster)

    return clusters
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/clusterer.py tests/test_clusterer.py && git commit -m "feat: fuzzy address clustering with rapidfuzz"
```

---

### Task 6: Postcode Validator

**Files:**
- Create: `src/validator.py`
- Create: `tests/test_validator.py`

Validates and corrects postcode↔city↔state using the Malaysian postcode DB.

**Step 1: Write failing tests**

```python
# tests/test_validator.py
from src.validator import PostcodeValidator

def test_valid_postcode_city_state():
    v = PostcodeValidator("data/postcodes.json")
    result = v.validate("93250", "KUCHING", "SARAWAK")
    assert result["valid"] is True

def test_wrong_state_for_postcode():
    v = PostcodeValidator("data/postcodes.json")
    result = v.validate("93250", "KUCHING", "JOHOR")
    assert result["valid"] is False
    assert result["suggested_state"] == "SARAWAK"

def test_missing_state():
    v = PostcodeValidator("data/postcodes.json")
    result = v.validate("93250", "KUCHING", "")
    assert result["suggested_state"] == "SARAWAK"

def test_missing_city():
    v = PostcodeValidator("data/postcodes.json")
    result = v.validate("93250", "", "SARAWAK")
    assert result["suggested_city"] != ""

def test_unknown_postcode():
    v = PostcodeValidator("data/postcodes.json")
    result = v.validate("00000", "", "")
    assert result["valid"] is False

def test_state_from_postcode_prefix():
    v = PostcodeValidator("data/postcodes.json")
    # 50xxx-60xxx = KL
    result = v.validate("50000", "", "")
    assert "KUALA LUMPUR" in result.get("suggested_state", "").upper() or "WILAYAH" in result.get("suggested_state", "").upper()
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement validator**

```python
# src/validator.py
import json
from rapidfuzz import fuzz, process

POSTCODE_STATE_PREFIXES = {
    "01": "PERLIS", "02": "PERLIS",
    "05": "KEDAH", "06": "KEDAH", "08": "KEDAH", "09": "KEDAH",
    "10": "PULAU PINANG", "11": "PULAU PINANG", "12": "PULAU PINANG", "13": "PULAU PINANG", "14": "PULAU PINANG",
    "15": "KELANTAN", "16": "KELANTAN", "17": "KELANTAN", "18": "KELANTAN",
    "20": "TERENGGANU", "21": "TERENGGANU", "22": "TERENGGANU", "23": "TERENGGANU", "24": "TERENGGANU",
    "25": "PAHANG", "26": "PAHANG", "27": "PAHANG", "28": "PAHANG",
    "30": "PERAK", "31": "PERAK", "32": "PERAK", "33": "PERAK", "34": "PERAK", "35": "PERAK", "36": "PERAK",
    "40": "SELANGOR", "41": "SELANGOR", "42": "SELANGOR", "43": "SELANGOR", "44": "SELANGOR",
    "45": "SELANGOR", "46": "SELANGOR", "47": "SELANGOR", "48": "SELANGOR",
    "50": "WILAYAH PERSEKUTUAN KUALA LUMPUR", "51": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "52": "WILAYAH PERSEKUTUAN KUALA LUMPUR", "53": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "54": "WILAYAH PERSEKUTUAN KUALA LUMPUR", "55": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "56": "WILAYAH PERSEKUTUAN KUALA LUMPUR", "57": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "58": "WILAYAH PERSEKUTUAN KUALA LUMPUR", "59": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "60": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "62": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    "63": "SELANGOR", "64": "SELANGOR",
    "68": "SELANGOR", "69": "SELANGOR",
    "70": "NEGERI SEMBILAN", "71": "NEGERI SEMBILAN", "72": "NEGERI SEMBILAN", "73": "NEGERI SEMBILAN",
    "75": "MELAKA", "76": "MELAKA", "77": "MELAKA", "78": "MELAKA",
    "79": "JOHOR", "80": "JOHOR", "81": "JOHOR", "82": "JOHOR", "83": "JOHOR",
    "84": "JOHOR", "85": "JOHOR", "86": "JOHOR",
    "87": "WILAYAH PERSEKUTUAN LABUAN",
    "88": "SABAH", "89": "SABAH", "90": "SABAH", "91": "SABAH",
    "93": "SARAWAK", "94": "SARAWAK", "95": "SARAWAK", "96": "SARAWAK", "97": "SARAWAK", "98": "SARAWAK",
}


class PostcodeValidator:
    def __init__(self, postcodes_path):
        with open(postcodes_path) as f:
            data = json.load(f)

        self._postcode_map = {}  # postcode → {"city": str, "state": str}
        self._all_cities = set()

        for state_obj in data.get("states", []):
            state_name = state_obj["name"].upper()
            for city_obj in state_obj.get("cities", []):
                city_name = city_obj["name"].upper()
                self._all_cities.add(city_name)
                for pc in city_obj.get("postcodes", []):
                    self._postcode_map[pc] = {"city": city_name, "state": state_name}

    def validate(self, postcode, city, state):
        """Validate postcode/city/state and suggest corrections."""
        postcode = postcode.strip()
        city = city.strip().upper()
        state = state.strip().upper()

        result = {
            "valid": False,
            "suggested_postcode": postcode,
            "suggested_city": city,
            "suggested_state": state,
        }

        # Lookup in DB
        db_entry = self._postcode_map.get(postcode)

        if db_entry:
            result["suggested_city"] = db_entry["city"]
            result["suggested_state"] = db_entry["state"]

            state_match = self._states_match(state, db_entry["state"])
            city_match = not city or fuzz.token_sort_ratio(city, db_entry["city"]) > 70

            result["valid"] = state_match and city_match
        else:
            # Fallback: use postcode prefix to guess state
            prefix = postcode[:2] if len(postcode) >= 2 else ""
            if prefix in POSTCODE_STATE_PREFIXES:
                result["suggested_state"] = POSTCODE_STATE_PREFIXES[prefix]

        return result

    def _states_match(self, provided, expected):
        """Check if provided state matches expected, accounting for variations."""
        if not provided:
            return True  # Missing = not wrong
        return fuzz.token_sort_ratio(provided, expected) > 70

    def correct_address(self, addr):
        """Validate and correct an address dict in-place. Returns (corrected_addr, validation_result)."""
        vr = self.validate(addr.get("postcode", ""), addr.get("city", ""), addr.get("state", ""))

        corrected = dict(addr)
        if vr["suggested_state"]:
            corrected["state"] = vr["suggested_state"]
        if vr["suggested_city"]:
            corrected["city"] = vr["suggested_city"]

        return corrected, vr
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/validator.py tests/test_validator.py && git commit -m "feat: postcode validator with Malaysian DB"
```

---

### Task 7: Nominatim Fallback (Low-Confidence Only)

**Files:**
- Create: `src/nominatim.py`
- Create: `tests/test_nominatim.py`

Only called for addresses scoring below CONFIDENCE_THRESHOLD. Rate limited to 1 req/sec.

**Step 1: Write failing test**

```python
# tests/test_nominatim.py
from unittest.mock import patch, MagicMock
from src.nominatim import geocode_address

def test_geocode_returns_structured_result():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{
        "display_name": "235, Lorong 5, Taman Springfield, 93250 Kuching, Sarawak, Malaysia",
        "address": {
            "road": "Lorong 5",
            "suburb": "Taman Springfield",
            "city": "Kuching",
            "state": "Sarawak",
            "postcode": "93250",
            "country": "Malaysia",
        },
        "importance": 0.45,
    }]

    with patch("src.nominatim.requests.get", return_value=mock_response):
        result = geocode_address("NO 235 LORONG 5 TAMAN SPRINGFIELD 93250 KUCHING SARAWAK")

    assert result is not None
    assert result["state"] == "Sarawak"
    assert result["postcode"] == "93250"

def test_geocode_no_results():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    with patch("src.nominatim.requests.get", return_value=mock_response):
        result = geocode_address("XYZXYZXYZ NOWHERE")

    assert result is None
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

```python
# src/nominatim.py
import time
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "address-normaliser/1.0 (falcon-field-partners)"

_last_request_time = 0


def geocode_address(query):
    """Geocode a Malaysian address using Nominatim. Returns structured result or None."""
    global _last_request_time

    # Rate limit: 1 request per second
    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "countrycodes": "my",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        _last_request_time = time.time()

        if resp.status_code != 200 or not resp.json():
            return None

        hit = resp.json()[0]
        addr = hit.get("address", {})

        return {
            "display_name": hit.get("display_name", ""),
            "road": addr.get("road", ""),
            "suburb": addr.get("suburb", ""),
            "city": addr.get("city", addr.get("town", addr.get("village", ""))),
            "state": addr.get("state", ""),
            "postcode": addr.get("postcode", ""),
            "importance": hit.get("importance", 0),
        }
    except (requests.RequestException, ValueError):
        return None
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/nominatim.py tests/test_nominatim.py && git commit -m "feat: nominatim geocoding fallback"
```

---

### Task 8: Mailing Block Formatter

**Files:**
- Create: `src/formatter.py`
- Create: `tests/test_formatter.py`

**Step 1: Write failing tests**

```python
# tests/test_formatter.py
from src.formatter import format_mailing_block

def test_full_address_block():
    addr = {
        "address_line": "NO 235 LORONG 5 JALAN KERETAPI",
        "address_line2": "TAMAN SPRINGFIELD",
        "address_line3": "",
        "postcode": "93250",
        "city": "KUCHING",
        "state": "SARAWAK",
    }
    block = format_mailing_block(addr)
    expected = "NO 235 LORONG 5 JALAN KERETAPI\nTAMAN SPRINGFIELD\n93250 KUCHING\nSARAWAK"
    assert block == expected

def test_no_address_line2():
    addr = {
        "address_line": "NO 1 JALAN AMPANG",
        "address_line2": "",
        "address_line3": "",
        "postcode": "50450",
        "city": "KUALA LUMPUR",
        "state": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    }
    block = format_mailing_block(addr)
    assert block == "NO 1 JALAN AMPANG\n50450 KUALA LUMPUR\nWILAYAH PERSEKUTUAN KUALA LUMPUR"

def test_missing_postcode():
    addr = {
        "address_line": "KAMPUNG PARIS 3",
        "address_line2": "",
        "address_line3": "",
        "postcode": "",
        "city": "KOTA KINABALU",
        "state": "SABAH",
    }
    block = format_mailing_block(addr)
    assert block == "KAMPUNG PARIS 3\nKOTA KINABALU\nSABAH"

def test_with_address_line3():
    addr = {
        "address_line": "NO 1 JALAN 2",
        "address_line2": "TAMAN MELAWATI",
        "address_line3": "OFF JALAN GOMBAK",
        "postcode": "53100",
        "city": "KUALA LUMPUR",
        "state": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    }
    block = format_mailing_block(addr)
    lines = block.split("\n")
    assert len(lines) == 5
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement**

```python
# src/formatter.py

def format_mailing_block(addr):
    """Format a normalised address into a mailing block string."""
    lines = []

    if addr.get("address_line"):
        lines.append(addr["address_line"])

    if addr.get("address_line2"):
        lines.append(addr["address_line2"])

    if addr.get("address_line3"):
        lines.append(addr["address_line3"])

    # Postcode + City on same line
    pc_city = " ".join(filter(None, [addr.get("postcode", ""), addr.get("city", "")]))
    if pc_city.strip():
        lines.append(pc_city.strip())

    if addr.get("state"):
        lines.append(addr["state"])

    return "\n".join(lines)
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add src/formatter.py tests/test_formatter.py && git commit -m "feat: mailing block formatter"
```

---

### Task 9: Main Pipeline

**Files:**
- Create: `src/pipeline.py`
- Create: `tests/test_pipeline.py`

Orchestrates: read Excel → parse → normalise → cluster → score → select → validate → format → write Excel.

**Step 1: Write failing test**

```python
# tests/test_pipeline.py
import os
import pandas as pd
from src.pipeline import process_file

def test_process_sample_file(tmp_path):
    """Integration test with a small synthetic dataset."""
    input_path = tmp_path / "test_input.xlsx"
    output_path = tmp_path / "test_output.xlsx"

    data = {
        "ICNO": ["900208125173", "830509135841"],
        "NAME": ["AZMAN BIN SAHIDI", "KEVIN ANAK SIMON"],
        "ADDR0": [
            "LOT 265, Batu, TAMAN PASAR PUTIH PHASE 1, , 88100, KOTA KINABALU, SABAH, ",
            "NO 235 LRG 5 JALAN KERETAPI, TAMAN SPRINGFIELD, , 93250, KUCHING, SARAWAK, ",
        ],
        "ADDR1": [
            "LORONG 5 -LOT 265 TAMAN PARK PUTIH PUTA, , , 88100, KOTA KINABALU, SABAH, ",
            "NO 235 LORONG 5 TAMAN SPRING FIELD JALAN KERETAPI 93250 KUCHING SARAWAK, , , , , , ",
        ],
        "ADDR2": [
            ", , , , , , ",
            "NO 177 LRG 5 OFF JALAN KERETAPI, TAMAN SPRINGFIELD, , 93350, KUCHING, SARAWAK, ",
        ],
    }
    df = pd.DataFrame(data)
    df.to_excel(input_path, index=False)

    stats = process_file(str(input_path), str(output_path))

    assert os.path.exists(output_path)
    result_df = pd.read_excel(output_path)
    assert len(result_df) == 2
    assert "ICNO" in result_df.columns
    assert "NAME" in result_df.columns
    assert "MAILING_ADDRESS" in result_df.columns
    assert "CONFIDENCE" in result_df.columns

    # Check addresses are non-empty
    for addr in result_df["MAILING_ADDRESS"]:
        assert addr and len(addr) > 10
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement pipeline**

```python
# src/pipeline.py
import logging
import pandas as pd
import xlrd

from src.parser import parse_all_addresses
from src.normaliser import normalise_address
from src.clusterer import cluster_addresses
from src.scorer import score_completeness
from src.validator import PostcodeValidator
from src.nominatim import geocode_address
from src.formatter import format_mailing_block
from src.config import NOMINATIM_ENABLED, CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

POSTCODES_PATH = "data/postcodes.json"


def _read_excel(path):
    """Read Excel file, handling both .xls and .xlsx formats."""
    if path.endswith(".xls"):
        wb = xlrd.open_workbook(path, ignore_workbook_corruption=True)
        df = pd.read_excel(wb, engine="xlrd")
    else:
        df = pd.read_excel(path, engine="openpyxl")
    return df


def _get_addr_columns(df):
    """Get sorted ADDR column names from DataFrame."""
    cols = [c for c in df.columns if c.upper().startswith("ADDR")]
    cols.sort(key=lambda x: int("".join(filter(str.isdigit, x)) or "0"))
    return cols


def _select_best_address(clusters):
    """From scored clusters, select the best address. Returns (address, confidence)."""
    if not clusters:
        return None, 0.0

    best_cluster = None
    best_cluster_score = -1

    for cluster in clusters:
        freq = len(cluster)
        max_completeness = max(score_completeness(a) for a in cluster)
        cluster_score = freq * max_completeness
        if cluster_score > best_cluster_score:
            best_cluster_score = cluster_score
            best_cluster = cluster

    # From best cluster, pick the most complete address
    best_addr = max(best_cluster, key=score_completeness)
    max_possible = 11  # max completeness score
    confidence = min(score_completeness(best_addr) / max_possible, 1.0)

    return best_addr, confidence


def process_file(input_path, output_path):
    """Process an input Excel file and write results to output Excel."""
    logger.info("Reading %s", input_path)
    df = _read_excel(input_path)
    addr_columns = _get_addr_columns(df)

    if not addr_columns:
        raise ValueError(f"No ADDR columns found in {input_path}")

    # Filter out header/test rows
    ic_col = "ICNO"
    if ic_col in df.columns:
        df = df[~df[ic_col].astype(str).str.strip().str.lower().isin(["ic", "icno", ""])]

    validator = PostcodeValidator(POSTCODES_PATH)

    results = []
    stats = {"total": len(df), "processed": 0, "low_confidence": 0, "no_address": 0}

    for idx, row in df.iterrows():
        ic = str(row.get(ic_col, "")).strip()
        name = str(row.get("NAME", "")).strip()

        # Step 1: Parse all addresses
        parsed = parse_all_addresses(row, addr_columns)
        if not parsed:
            results.append({"ICNO": ic, "NAME": name, "MAILING_ADDRESS": "", "CONFIDENCE": 0.0})
            stats["no_address"] += 1
            continue

        # Step 2: Normalise
        normalised = [normalise_address(a) for a in parsed]

        # Step 3: Cluster
        clusters = cluster_addresses(normalised)

        # Step 4: Select best
        best_addr, confidence = _select_best_address(clusters)

        if not best_addr:
            results.append({"ICNO": ic, "NAME": name, "MAILING_ADDRESS": "", "CONFIDENCE": 0.0})
            stats["no_address"] += 1
            continue

        # Step 5: Validate postcode
        best_addr, vr = validator.correct_address(best_addr)

        # Step 6: Nominatim fallback for low confidence
        if NOMINATIM_ENABLED and confidence < CONFIDENCE_THRESHOLD:
            stats["low_confidence"] += 1
            query = f"{best_addr['address_line']} {best_addr.get('postcode', '')} {best_addr.get('city', '')} {best_addr.get('state', '')}"
            geo = geocode_address(query.strip())
            if geo and geo.get("postcode"):
                if not best_addr.get("postcode"):
                    best_addr["postcode"] = geo["postcode"]
                if not best_addr.get("city") and geo.get("city"):
                    best_addr["city"] = geo["city"].upper()
                if not best_addr.get("state") and geo.get("state"):
                    best_addr["state"] = geo["state"].upper()
                confidence = min(confidence + 0.2, 1.0)

        # Step 7: Format mailing block
        mailing = format_mailing_block(best_addr)

        results.append({
            "ICNO": ic,
            "NAME": name,
            "MAILING_ADDRESS": mailing,
            "CONFIDENCE": round(confidence, 2),
        })
        stats["processed"] += 1

    # Write output
    result_df = pd.DataFrame(results)
    result_df.to_excel(output_path, index=False, engine="openpyxl")

    logger.info("Wrote %d results to %s", len(results), output_path)
    logger.info("Stats: %s", stats)

    return stats
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py && git commit -m "feat: main address processing pipeline"
```

---

### Task 10: Google Drive Integration + Main Entry Point

**Files:**
- Create: `src/gdrive.py` (adapted from str-scrape)
- Create: `scripts/authorize_gdrive.py`
- Create: `main.py`

**Step 1: Create src/gdrive.py**

Adapt from `/Users/wee/Desktop/SideQuest/str-scrape/src/gdrive.py` with these functions:
- `_get_service()` — singleton Drive API service
- `list_upload_folder()` — list Excel files in Upload folder
- `download_file(file_id, local_path)` — download file
- `move_file(file_id, target_folder_id)` — move between folders
- `move_to_processing(file_id)` — shortcut
- `move_to_archive(file_id)` — shortcut
- `upload_file(local_path, folder_id, filename)` — upload result
- `upload_or_replace_file(local_path, folder_id, filename)` — idempotent upload
- `upload_results(result_path, stats, original_filename)` — upload output + logs

Reference the str-scrape implementation at `/Users/wee/Desktop/SideQuest/str-scrape/src/gdrive.py` — same OAuth pattern, same folder structure logic.

**Step 2: Create scripts/authorize_gdrive.py**

Same as str-scrape: `InstalledAppFlow.from_client_secrets_file()` → `run_local_server()` → save token.

**Step 3: Create main.py**

```python
# main.py
import logging
import os
import sys
import time
import tempfile

from src import config
from src import gdrive
from src.pipeline import process_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def process_one_file(file_info):
    """Download, process, and upload results for one file."""
    file_id = file_info["id"]
    filename = file_info["name"]
    logger.info("Processing: %s", filename)

    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, filename)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(tmp, f"{base_name}_NORMALISED.xlsx")

        # Download
        gdrive.download_file(file_id, input_path)

        # Move to processing
        gdrive.move_to_processing(file_id)

        # Process
        stats = process_file(input_path, output_path)

        # Upload results
        gdrive.upload_results(output_path, stats, filename)

        # Archive original
        gdrive.move_to_archive(file_id)

    logger.info("Done: %s — %s", filename, stats)


def main():
    """Poll Google Drive for new files and process them."""
    required = ["GDRIVE_UPLOAD_FOLDER_ID", "GDRIVE_PROCESSING_FOLDER_ID",
                "GDRIVE_COMPLETED_FOLDER_ID", "GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID"]

    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error("Missing env vars: %s", missing)
        sys.exit(1)

    logger.info("Address Normaliser started. Polling every %ds.", config.POLL_INTERVAL_SECONDS)

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
```

**Step 4: Commit**

```bash
git add main.py src/gdrive.py scripts/authorize_gdrive.py && git commit -m "feat: Google Drive integration and main entry point"
```

---

### Task 11: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY main.py .

CMD ["python", "-u", "main.py"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  app:
    build: .
    env_file: .env
    volumes:
      - ./credentials:/app/credentials
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
```

**Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml && git commit -m "feat: Docker setup"
```

---

### Task 12: End-to-End Test with Real Data

**Files:** None created — manual verification step.

**Step 1: Run pipeline against the sample file**

```bash
python -c "
from src.pipeline import process_file
stats = process_file('/Users/wee/Downloads/feb_tps0_qresults.xls', '/tmp/normalised_output.xlsx')
print(stats)
"
```

**Step 2: Verify output**

```bash
python -c "
import pandas as pd
df = pd.read_excel('/tmp/normalised_output.xlsx')
print(f'Rows: {len(df)}')
print(f'Columns: {list(df.columns)}')
print(f'Empty addresses: {(df[\"MAILING_ADDRESS\"] == \"\").sum()}')
print(f'Low confidence (<0.6): {(df[\"CONFIDENCE\"] < 0.6).sum()}')
print()
print('=== SAMPLE OUTPUT (first 5) ===')
for _, row in df.head(5).iterrows():
    print(f'IC: {row[\"ICNO\"]}')
    print(f'Name: {row[\"NAME\"]}')
    print(f'Address:\\n{row[\"MAILING_ADDRESS\"]}')
    print(f'Confidence: {row[\"CONFIDENCE\"]}')
    print('---')
"
```

**Step 3: Review and adjust thresholds if needed**

Check: Are the selected addresses sensible? Are confidence scores reasonable? Any obvious wrong picks?

**Step 4: Final commit**

```bash
git add -A && git commit -m "chore: end-to-end verification complete"
```

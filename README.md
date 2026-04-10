# Address Normaliser

Automatically selects the best mailing address from up to 40 address variants per Malaysian IC number. Validates against the official Malaysian postcode database and outputs a formatted, colour-coded Excel file ready for mailing.

## How It Works

1. **Drop** an Excel file into the Google Drive Upload folder
2. The system reads all address fields (ADDR0-ADDR40) for each IC
3. Normalises abbreviations (Jln → Jalan, Tmn → Taman, Lrg → Lorong, Kg → Kampung)
4. Clusters similar addresses and picks the most frequent + most complete
5. Validates postcode/city/state against 2,932 Malaysian postcodes
6. **Pick up** the result from the Completed folder

Output: one row per IC with a single formatted mailing address and a confidence score. Red-highlighted rows need manual attention.

## Quick Start

### Local (one-off processing)

```bash
pip install -r requirements.txt

python cli.py input.xls                    # outputs input_NORMALISED.xlsx
python cli.py input.xls output.xlsx        # custom output path
python cli.py input.xls --nominatim        # enable OSM geocoding fallback
```

### Google Drive (production)

```bash
# One-time: set up OAuth credentials
cp /path/to/client_secret.json credentials/
python scripts/authorize_gdrive.py

# One-time: create Drive folder structure
python scripts/setup_drive.py
# Copy the output into .env

# Run
python main.py
```

### Docker

```bash
cp .env.example .env
# Fill in Google Drive folder IDs

docker compose up -d
```

## Output Format

| Column | Description |
|--------|-------------|
| ICNO | IC number |
| NAME | Person's name |
| MAILING_ADDRESS | Formatted mailing block (multi-line) |
| CONFIDENCE | 0.0 to 1.0 (higher = more complete) |

### Row Colours

| Colour | Meaning |
|--------|---------|
| White | Ready to mail |
| Red | Unmailable (no address, no postcode, or no street) |
| Yellow | Low confidence, needs review |

## Tests

```bash
python -m pytest tests/ -v
```

## Configuration

See `.env.example` for all available settings:

| Variable | Default | Description |
|----------|---------|-------------|
| GDRIVE_UPLOAD_FOLDER_ID | | Google Drive Upload folder |
| GDRIVE_PROCESSING_FOLDER_ID | | Google Drive Processing folder |
| GDRIVE_COMPLETED_FOLDER_ID | | Google Drive Completed folder |
| GDRIVE_ARCHIVE_UPLOAD_FOLDER_ID | | Google Drive Archive folder |
| POLL_INTERVAL_SECONDS | 30 | How often to check for new files |
| NOMINATIM_ENABLED | false | Enable OSM geocoding for low-confidence addresses |
| CONFIDENCE_THRESHOLD | 0.6 | Below this, addresses are flagged for review |

## Project Structure

```
src/
  parser.py       - Parse comma-separated address fields
  normaliser.py   - Expand abbreviations, normalise state names
  clusterer.py    - Fuzzy-match address variants (rapidfuzz)
  scorer.py       - Score address completeness (0-11)
  validator.py    - Validate postcode/city/state against Malaysian DB
  nominatim.py    - Optional OSM geocoding fallback
  formatter.py    - Format mailing block, deduplicate lines
  pipeline.py     - Orchestrate everything
  gdrive.py       - Google Drive integration
  config.py       - Environment config
data/
  postcodes.json  - Malaysian postcode database (2,932 postcodes)
```

## Requirements

- Python 3.11+
- pandas, xlrd, openpyxl, rapidfuzz, requests
- Google Drive API credentials (for production mode)

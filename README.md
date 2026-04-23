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

```bash
make install         # install dependencies
make test            # run all unit tests
make run             # process tests/benchmark/input.xls
make score           # score output against golden answers
make help            # show all available commands
```

### Local (one-off processing)

```bash
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
make setup-drive
# Copy the output into .env

# Run (polls Drive every 30s)
python main.py

# Or via Docker
make docker-up
```

### Deploy to production (contabo-vps)

```bash
make deploy          # git pull + docker rebuild + restart on contabo-vps
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

## Tests and Evaluation

```bash
make test            # run 157 unit tests
make score           # score against expert golden answers (1,037 records)
make benchmark       # regression check against frozen baseline
make eval            # 13 automated quality checks
make validate        # generate client-facing validation report
```

Current accuracy: **98.4% (A+)** against expert golden answers.
See `docs/plans/` for optimisation history.

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
| ONLINE_VALIDATION_ENABLED | false | Validate selected addresses online (logs only, no extra Excel columns) |
| ONLINE_VALIDATION_MAILABLE_ONLY | true | Only run online validation for mailable addresses |
| ONLINE_VALIDATION_REVIEW_NO_RESULT | false | If true, no-result online checks are flagged for manual review |
| ONLINE_VALIDATION_PROVIDERS | tomtom,geoapify,locationiq | Fallback order for online providers |
| ONLINE_VALIDATION_TIMEOUT_SECONDS | 10 | Timeout per online validation request |
| TOMTOM_API_KEY | | TomTom geocoding API key |
| GEOAPIFY_API_KEY | | Geoapify geocoding API key |
| LOCATIONIQ_API_KEY | | LocationIQ geocoding API key |
| SMTP_HOST, SMTP_USER, SMTP_PASSWORD, CLIENT_EMAIL | | Email notifications (optional) |

## Project Structure

```
src/
  pipeline.py          - Main orchestrator
  config.py            - Environment variables

  processing/          - Core domain logic
    parser.py          - Parse comma-separated address fields
    normaliser.py      - Expand abbreviations, normalise state names
    clusterer.py       - Fuzzy-match address variants (rapidfuzz)
    scorer.py          - Score address completeness (0-12)
    validator.py       - Validate postcode/city/state against Malaysian DB
    formatter.py       - Format mailing block (line ordering)
    text_utils.py      - Regex cleanup helpers (dedup, period fixes)

  steps/               - Pipeline stages
    select.py          - Cluster + address selection (popularity + consensus)
    enrich.py          - JALAN prefix, cross-cluster, ensemble, spelling
    clean.py           - Strip leaked fields, merge standalone words
    geocode.py         - Optional Nominatim fallback

  io/                  - I/O and integrations
    excel_reader.py    - Read .xls/.xlsx, detect ADDR columns
    excel_writer.py    - Write output, colour-code rows
    gdrive.py          - Google Drive integration
    notifier.py        - Email notifications
    nominatim.py       - OSM geocoding client

data/
  postcodes.json       - Malaysian postcode database (2,932 postcodes)
```

## Requirements

- Python 3.11+
- pandas, xlrd, openpyxl, rapidfuzz, requests
- Google Drive API credentials (for production mode)

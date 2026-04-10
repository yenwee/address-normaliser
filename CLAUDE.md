# Address Normaliser

Malaysian address normalisation system for Falcon Field & Partners. Automatically selects the best mailing address from up to 40 address variants per IC number.

## Architecture

```
Input Excel (ICNO + ADDR0-ADDR40)
  -> Parse comma-separated fields
  -> Normalise (expand abbreviations, fix state names)
  -> Cluster similar addresses (rapidfuzz token similarity)
  -> Score clusters (frequency x completeness)
  -> Select best address from best cluster
  -> Validate postcode/city/state (Malaysian postcode DB)
  -> Format mailing block
  -> Colour-coded Excel output
```

## Key Files

- `src/parser.py` - Parse comma-separated ADDR fields into structured dicts
- `src/normaliser.py` - Expand abbreviations (Jln->Jalan, Tmn->Taman), normalise state names
- `src/clusterer.py` - Fuzzy match addresses using rapidfuzz token_sort_ratio
- `src/scorer.py` - Score completeness (0-11): postcode, city, state, street number, street name, area
- `src/validator.py` - Validate postcode->city->state against Malaysian DB (2,932 postcodes)
- `src/nominatim.py` - Optional OSM geocoding fallback for low-confidence addresses
- `src/formatter.py` - Format into mailing block, deduplicate lines
- `src/pipeline.py` - Orchestrates everything, highlights Excel output
- `src/gdrive.py` - Google Drive polling (adapted from str-scrape)
- `src/config.py` - Environment variables
- `main.py` - Entry point with Drive polling loop
- `data/postcodes.json` - Malaysian postcode database (heiswayi/malaysia-postcodes)

## Data Format

Each ADDR column is comma-separated with ~7 fields:
```
address_line, address_line2, address_line3, postcode, city, state, (empty)
```

Fields 4/5 (city/state) sometimes swap. Postcode position is most reliable (field index 3-4). Some fields contain NULL strings, phone numbers, or IC numbers (junk).

## Running

### Local
```bash
python -c "from src.pipeline import process_file; process_file('input.xls', 'output.xlsx')"
```

### Google Drive (production)
```bash
# First time: create Drive folders
python scripts/setup_drive.py

# Run polling service
python main.py

# Or via Docker
docker compose up -d
```

### Tests
```bash
python -m pytest tests/ -v
```

## Deployment

Same pattern as str-scrape. Runs on hustle-oci server (149.118.147.82:2222).
```bash
git clone <repo> address-normaliser
cp credentials/ .  # from str-scrape (same Google account)
cp .env .
docker compose up -d
```

Google Drive folder structure under "Falcon Field > Address Normaliser":
- Upload/ - client drops Excel here
- Processing/ - auto-moved during processing
- Completed/Output/ - result Excel
- Completed/Logs/ - status report
- Archive/ - processed files

## Known Quirks

- Source data has "Kampung" and "Jalan" as separate comma fields -> merged in pipeline
- 4-digit postcodes (Perlis/Kedah/Langkawi) zero-padded to 5 digits
- Unit numbers with hyphens (39-01-09) preserved, word hyphens stripped
- Abbreviations stuck to digits (117KPG) split only for known abbreviations
- Postcode+city sometimes embedded in address line text -> stripped in pipeline
- State names sometimes leak into address fields -> stripped in pipeline

## Phase 2 Backlog

- Address merging: combine best fields from cluster instead of picking single best
- MyKad IC state cross-check (positions 7-8 encode birth state)
- Email notification on completion (like str-scrape)

## Client

Falcon Field & Partners Sdn Bhd (Harjit Kaur)
- Proposal: P-0027 (RM 1,000 setup + RM 100/month)
- Same client as str-scrape (P-0026)
- Hustle OS invoices: INV-0023 to INV-0027

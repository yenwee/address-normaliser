# Address Normaliser

Malaysian address normalisation system for Falcon Field & Partners. Automatically selects the best mailing address from up to 40 address variants per IC number.

## Architecture

```
Input Excel (ICNO + ADDR0-ADDR40)
  -> Parse comma-separated fields
  -> Normalise (expand abbreviations, fix state names)
  -> Cluster similar addresses (rapidfuzz token similarity)
  -> Score clusters (frequency x completeness + consensus)
  -> Select best address (consensus-aware, descriptiveness bonus)
  -> Enrich from cluster (JALAN prefix, missing fields)
  -> Ensemble enhance (fill empty fields from cluster majority vote)
  -> Validate postcode/city/state (Malaysian postcode DB)
  -> Smart format (line reorder: street/area/postcode+city/state)
  -> Colour-coded Excel output (red=unmailable, white=ready)
```

## Key Files

- `src/parser.py` - Parse comma-separated ADDR fields into structured dicts
- `src/normaliser.py` - Expand abbreviations (Jln->Jalan, Tmn->Taman, 30+ mappings), normalise state names
- `src/clusterer.py` - Fuzzy match addresses using rapidfuzz token_sort_ratio (threshold 65)
- `src/scorer.py` - Score completeness (0-12): postcode, city, state, street number, street name, area, descriptiveness
- `src/validator.py` - Validate postcode->city->state against Malaysian DB (2,932 postcodes)
- `src/nominatim.py` - Optional OSM geocoding fallback for low-confidence addresses
- `src/formatter.py` - Smart line reorder, PETI SURAT first, dedup lines/phrases, clean symbols
- `src/pipeline.py` - Orchestrates everything, ensemble enhance, highlights Excel output
- `src/gdrive.py` - Google Drive polling (adapted from str-scrape)
- `src/config.py` - Environment variables
- `main.py` - Entry point with Drive polling loop
- `cli.py` - CLI for local testing
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
python cli.py input.xls                    # auto-names output
python cli.py input.xls output.xlsx        # custom output
python cli.py input.xls --nominatim        # with OSM fallback
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

### Evaluation
```bash
# Quality checks (13 automated checks)
python scripts/evaluate.py output.xlsx

# Score against expert golden answers (1,037 records)
python scripts/score_against_golden.py output.xlsx

# Regression check against frozen baseline
python scripts/benchmark.py output.xlsx

# Generate validation report for client
python scripts/generate_validation_report.py input.xls output.xlsx report.xlsx
```

## Deployment

Same pattern as str-scrape. Runs on hustle-oci server (149.118.147.82:2222).
```bash
git clone https://github.com/yenwee/address-normaliser.git
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
- PETI SURAT (PO Box) always moved to first line for mailing
- Line 1 reordering: LOT/NO before LORONG/JALAN (Malaysian postal convention)
- Consensus selection: when cluster scores are close, prefer address agreed by more members
- Descriptiveness bonus: named streets (LORONG PUTERI GUNUNG) preferred over numbered (LORONG 3)

## Current Accuracy

Pipeline scores **94.6%** against expert golden answers (1,037 records).
- Postcode: 95.4% | City: 94.7% | State: 94.2% | Street: 93.2%
- See `docs/plans/2026-04-17-pipeline-fixes.md` for 7 bugs to push to ~100%

## Phase 2 Backlog

See `docs/plans/2026-04-17-pipeline-fixes.md` for prioritised fixes:
1. Duplicated text within lines (~130 records)
2. Truncated JALAN/KAMPUNG/BATU (~70 records)
3. Missing state (~35 records)
4. Wrong cluster picked (~5 records)
5. SRI->SERI wrong expansion (~15 records)
6. Dot-separated junk cleanup (~5 records)
7. "Batu" standalone artifact (~20 records)

Other backlog:
- Full address merging (combine best fields from cluster)
- MyKad IC state cross-check (positions 7-8 encode birth state)
- Email notification on completion (like str-scrape)

## Client

Falcon Field & Partners Sdn Bhd (Harjit Kaur)
- Proposal: P-0027 (RM 1,000 setup + RM 100/month)
- Same client as str-scrape (P-0026)
- Hustle OS invoices: INV-0023 to INV-0027
- GitHub: https://github.com/yenwee/address-normaliser

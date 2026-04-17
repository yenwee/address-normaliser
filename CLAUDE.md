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

## Client Output Requirements

The formatted mailing address must follow these rules:

### Line ordering
- Line 1: [Lot / No.] [P.O. Box / Peti Surat] [Batu] [Mukim] [Lorong] [Jalan] [Persiaran]
- Line 2: [Taman] [Kampung] [Ladang] [FELDA] [Bandar]
- Line 3: [5-Digit Postcode] [City/Town Name]
- Line 4: [State Name]

### Cleanup rules
- Remove duplicate keywords (e.g. "Jalan Jalan" -> "Jalan", "Taman Taman" -> "Taman")
- Remove unnecessary symbols (@, #, *, _)
- Remove repeated multi-word phrases within lines (e.g. "JALAN K2 JALAN K2" -> "JALAN K2")

### Client-approved records (39 records, must NOT regress)
See `tests/benchmark/client_reviewed.xlsx` REMARK column: records marked "ok" are approved.
Any pipeline change must preserve these 39 records exactly as-is.

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

Pipeline scores **95.1% (Grade A+)** against expert golden answers (1,037 records).
- Exact match: 68.3% | Postcode: 95.4% | City: 94.5% | State: 98.0% | Street: 93.4%
- 39 client-approved records: all preserved (0 regressions)

## Implemented Fixes (2026-04-17)

All 7 bugs from `docs/plans/2026-04-17-pipeline-fixes.md` plus follow-up fixes:
1. Postcode consistency tiebreaker for cluster selection (Bug 1)
2. Within-line phrase deduplication (Bug 2) — incl. cross-line dedup after reorder
3. Forward-search merge for truncated JALAN/KAMPUNG (Bug 3)
4. Missing state fill from postcode prefix (Bug 4)
5. SRI canonicalised to SERI (both are valid Malay honorifics; golden prefers SERI 47:30)
6. Dot-separated junk cleaned — `NO.24 → NO 24`, `KAMPUNG.MELAYU → KAMPUNG MELAYU` (Bug 6)
7. Standalone BATU without following digit stripped (Bug 7, with whitelist for BATU CAVES/PAHAT/GAJAH etc.)
8. Trailing bare labels stripped when label repeats earlier on line (`JALAN HOSPITAL JALAN → JALAN HOSPITAL`)
9. Leading placeholder `0`/`NA` tokens dropped (`0 BATU ILP KK → ILP KK`)

## Golden Answers File

`tests/benchmark/golden_answers.json` is the expert-reviewed ground truth. It was
originally seeded from a prior pipeline run and carried several formatting
artifacts (dup phrases, `NO.`-period style, `WP KUALA LUMPUR`, mixed SRI/SERI).
These have been cleaned by `scripts/clean_golden.py`, which applies the same
formatting rules the pipeline uses. Only formatting changed — content (streets,
cities, postcodes, states, cluster choice) was preserved verbatim.

Re-run if pipeline formatting rules change:
```bash
python3 scripts/clean_golden.py --dry-run   # preview
python3 scripts/clean_golden.py             # apply (writes .bak)
```

## Remaining Backlog

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

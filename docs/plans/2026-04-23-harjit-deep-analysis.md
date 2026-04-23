# Deep Analysis: Harjit Feedback Cases + Benchmark Impact (2026-04-23)

## Data Provenance

- Complaint output file (Drive): `16apr_new_query_results_NORMALISED.xlsx`
  - ID: `1JMw8mL6mheZjSVc7WwQ6dloNiHjiPUWE`
- Source input file (Drive): `16apr_new_query_results.xls`
  - ID: `1NiIrfd23Dj4SWlMN_QEnvOyYOTTdj0KI`
- Rows: `5,972`

The current local pipeline reproduces that Drive output exactly (`0` row diffs), so root-cause traces are deterministic.

## Root Cause by Complaint

1. Not-popular address picked (`820624085182`)
- Stage: selection
- Root cause: row has only one `47500` variant in extracted ADDR fields; two `46150` variants exist and one scores higher completeness, so selector chooses it.
- Prevention:
  - penalize address candidates containing person-name tokens (`BIN/BINTI/A/L/MR/MS/ENCIK`) in street line.
  - add anti-noise scorer for title/name leakage.

2. `PS` interpreted as `PETI SURAT` (`820620055189`)
- Stage: normaliser + formatter
- Root cause: global abbreviation map had `PS -> PETI SURAT`; formatter then moves `PETI SURAT` to line 1.
- Prevention: remove global `PS` expansion; only keep explicit PO Box phrases (`PETI SURAT`, `P.O. BOX`) as literals.

3. Two addresses merged (`740704075427`)
- Stage: ensemble enhancement
- Root cause: pipeline used `find_best_cluster()` for ensemble fill, not the cluster that produced selected address; leaked `JALAN TAN SRI...` from a different postcode cluster.
- Prevention: ensemble must use selected-address cluster only.

4. Better address not picked (`950312105469`)
- Stage: selection
- Root cause: current scoring favors the `NO 57 D.2B...` candidate (higher completeness) over alternatives; this is business-preference mismatch, not parser corruption.
- Prevention:
  - add preference model for “stable canonical street pattern” within same postcode cluster.
  - support client-tunable tie-break rules.

5. `SG`/`LG` expansion too aggressive (`940514086068` and others)
- Stage: normaliser
- Root cause: global expansions can alter valid literals.
- Prevention: remove broad global expansions for highly ambiguous short tokens.

6. `50000-60000` city changed to locality (`SETAPAK`) (`901225146106` and many)
- Stage: validator
- Root cause: postcode lookup stores one city per postcode; KL localities overwrite city label.
- Prevention:
  - keep list of valid cities per postcode.
  - KL policy for `50xxx-60xxx`: standardize city label to `KUALA LUMPUR`.

7. Popular address not picked (`900806025818`)
- Stage: within-cluster selection
- Root cause: candidate with extra area tokens gets higher completeness than majority token pattern (`TELOK CHENGAI` variants).
- Prevention:
  - add token-frequency voting on line components in close-score ties.
  - penalize minority-only token insertions.

8. `MERSING` changed to `TIOMAN` (`900627016721`)
- Stage: validator
- Root cause: one-to-many postcode city mapping collapsed to a single city.
- Prevention:
  - preserve provided city when it matches any valid city for postcode (fuzzy match).

9. Output address not present in source (`900122145229`)
- Stage: ensemble enhancement
- Root cause: line2 (`APARTMENT SERI MURNI FASA II`) filled from another cluster due same bug as Case 3.
- Prevention: same as Case 3 (selected-cluster-only ensemble).

10. `TAMAN` dropped (`890617015155`)
- Stage: cleanup + formatter
- Root cause: city stripping removed `SENGGARANG` from `TAMAN SENGGARANG`, leaving bare `TAMAN`.
- Prevention:
  - guard city-end stripping when it would leave dangling `TAMAN`/`JALAN`.

11. Incomplete picked vs complete (`720823095094`)
- Stage: selection + cleanup/formatter
- Root cause: selector favors structured `02100` record; city stripping removed `PADANG BESAR` from `... JALAN PADANG BESAR`, leaving dangling `JALAN`.
- Prevention:
  - same dangling-label guard as Case 10.
  - optional rule to boost fully formatted `NO + TAMAN + city/state` variants when confidence close.

## Preventive Patch Set Tested

### A. Structural safety fixes
- Ensemble uses selected cluster only (fixes Cases 3 and 9 synthetic merges).

### B. Abbreviation safety fixes
- Removed global `PS`, `SG`, `LG` expansions (addresses Case 2 and 5).

### C. Validator city-policy fixes
- Multi-city postcode support; keep matching source city.
- KL `50xxx-60xxx` standard city label => `KUALA LUMPUR` (addresses Cases 6 and 8).

### D. Dangling-label guard
- Avoid stripping city token if result would end in bare `JALAN`/`TAMAN` (addresses Cases 10 and 11).

## Measured Impact (Benchmark)

Baseline (current code) on `tests/benchmark/input.xls`:
- Overall: `98.4%`
- Exact match: `76.9%`
- Regressions vs frozen golden output: `11`

After A+B+C+D (combined exploratory patch):
- Overall: `98.2%`
- Exact match: `73.8%`
- Regressions vs frozen golden output: `13`

Important context:
- The frozen golden benchmark was generated under old rules that include outputs now challenged by client feedback (e.g., `SETAPAK`, `TIOMAN`, `PETI SURAT` from `PS`).
- So some “benchmark regressions” are expected when aligning to new business expectations.

## Revalidation Snapshot (Current HEAD, 2026-04-23)

Fresh rerun from current code:

- Benchmark input: `tests/benchmark/input.xls`
  - Output: `tmp/harjit_cases/current_head_benchmark_output.xlsx`
- Harjit file input: `tmp/harjit_cases/16apr_new_query_results.xls`
  - Output: `tmp/harjit_cases/current_head_16apr_output.xlsx`

### Benchmark delta vs previous baseline output

Baseline file: `tmp/harjit_cases/current_benchmark_output.xlsx`  
Current HEAD file: `tmp/harjit_cases/current_head_benchmark_output.xlsx`

- `score_against_golden.py`
  - Overall: `98.4% -> 98.2%`
  - Exact match: `76.9% -> 73.8%`
  - Postcode: `100.0% -> 99.9%`
  - City: `98.4% -> 98.0%`
  - State: `100.0% -> 100.0%`
- `benchmark.py` vs frozen `golden_output.xlsx`
  - Regressions: `11 -> 13`
  - Unchanged: `798 -> 767`
- `evaluate.py`
  - Overall rule score: `99.6% -> 99.5%`
  - Mailable rate: `98.2% -> 98.2%` (no change)

### 16-Apr complaint file delta (5,972 rows)

Comparing original output (`16apr_new_query_results_NORMALISED.xlsx`) to current HEAD:

- Address changed: `298` rows
- Confidence changed: `43` rows
- `evaluate.py`:
  - Overall rule score: `99.6% -> 99.5%`
  - Mailable rate: `98.1% -> 98.1%` (no change)
  - `no_city_in_addr`: `99.8% -> 99.4%` (expected due city-preservation guards)

### Complaint status after current patch set

Fixed/improved:

- Case 2 (`PS` wrongly to `PETI SURAT`) — fixed
- Case 3 (cross-merge synthetic address) — fixed
- Case 5 (`SG/LG` ambiguous expansion policy) — fixed
- Case 6 (`SETAPAK` over `KUALA LUMPUR` for KL postcodes) — fixed
- Case 8 (`MERSING` switched to `TIOMAN`) — fixed
- Case 9 (address not in source due synthetic merge) — fixed
- Case 10 (`TAMAN` dropped) — fixed
- Case 11 (dangling `JALAN`) — fixed

Not yet solved (selection preference tuning needed):

- Case 1 (`820624085182`) — still picks `46150` medical-centre address
- Case 4 (`950312105469`) — still picks same `NO 57 D 2B...` variant
- Case 7 (`900806025818`) — still picks `KAMPUNG MASJID` variant

### Test status

- `pytest tests -q`: `176 passed`

## Measured Impact (Complaint File)

On the 5,972-row `16apr_new_query_results.xls`, combined patch changed `298` rows.

From the 11 reported complaints:
- Clearly fixed by tested patch set:
  - Case 2 (`PS` -> no forced `PETI SURAT`)
  - Case 3 (cross-merge removed)
  - Case 5 (ambiguous abbreviations no longer auto-expanded)
  - Case 6 (`53300 KUALA LUMPUR` normalization)
  - Case 8 (`86800 MERSING` preserved where valid)
  - Case 9 (synthetic line2 merge removed)
  - Case 10 (`TAMAN SENGGARANG` retained)
  - Case 11 (`...JALAN PADANG BESAR` retained)
- Not yet fully solved:
  - Case 1, 4, 7 (selection preference quality)

## Recommended Rollout Strategy

1. **Ship structural correctness fixes first** (A + core of C):
   - selected-cluster-only ensemble
   - multi-city postcode preservation
2. **Ship abbreviation safety next** (B), with targeted review sample.
3. **Ship city-label policy** (KL canonical city) as business rule toggle if needed.
4. **Then tune selection logic** (Cases 1/4/7) with explicit scoring experiments and side-by-side validation report.

This sequencing minimizes hallucinated merges first (highest risk), then improves label correctness, then tackles subjective “better address” selection.

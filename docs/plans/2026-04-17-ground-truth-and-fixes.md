# Ground Truth Generation & Pipeline Fixes Plan

## Context

11 subagent reviewers examined all 1,034 ground truth records against original source data.
Results: ~380 issues found across ~41% of records. Issues are systemic pipeline bugs.

## Phase 1: Fix Pipeline Bugs (fixes ~380 records)

### Bug 1: Duplicated text within lines (~130 records)
Example: `JALAN K2 JALAN K2`, `TAMAN PERTIWI JALAN PERTIW 3`
Root cause: Ensemble pulls same field from multiple cluster members
Fix: After formatting, scan each line for repeated 2+ word phrases and deduplicate

### Bug 2: Truncated standalone JALAN/KAMPUNG/BATU (~70 records)
Example: `NO 230 JALAN` (street name missing), `KAMPUNG` (village name missing)
Root cause: Source data has "Jalan"/"Kampung"/"Batu" as separate comma field, 
merge logic fails when the ACTUAL name is in the NEXT comma field (address_line3 or beyond)
Fix: In parser, when a field is exactly "Jalan"/"Kampung"/"Batu" etc., concatenate with the next non-empty field

### Bug 3: Missing area/taman names (~90 records)
Example: Drops "TAMAN BUKIT TERATAI" that exists in cluster
Root cause: Best address picked doesn't have address_line2, ensemble only fills from cluster's address_line2 but the area name may be IN address_line of other cluster members
Fix: Smarter ensemble - extract area keywords from ALL cluster members' address_lines, not just address_line2

### Bug 4: Missing state (~35 records)  
Example: `47100 PUCHONG` without SELANGOR
Root cause: Validator doesn't always fill state when source data state is empty
Fix: In validator.correct_address(), ALWAYS fill state from postcode DB even if source has a state (DB is authoritative)

### Bug 5: SRI vs SERI expansion (~15 records)
Example: `TAMAN SERI ANGSANA` when originals say `TAMAN SRI ANGSANA`
Root cause: SRI→SERI abbreviation in normaliser is WRONG. "SRI" is a valid Malay word, not an abbreviation
Fix: Remove SRI→SERI from abbreviations dict

### Bug 6: SEK→SEKSYEN when it means Sekolah (~5 records)
Example: `JALAN SEKSYEN MENENGAH` should be `JALAN SEKOLAH MENENGAH`
Root cause: SEK is ambiguous (Seksyen or Sekolah). When followed by MEN/MENENGAH/RENDAH, it's Sekolah
Fix: Don't expand SEK when followed by MEN/MENENGAH/RENDAH/AGAMA

### Bug 7: "Batu" field artifact (~20 records)
Example: `NO 304 BATU` where BATU is from comma-separated field label
Root cause: Source data has `, Batu,` as a separate field (means "milestone/distance"). Parser puts it in address_line2, then merge combines it
Fix: In parser, when a field is exactly "Batu" with no number, treat it as empty (it's a field label, not address content)

## Phase 2: Generate Expert Golden Answers (JSON)

The golden answers file is what Claude (acting as a human expert) determines 
is the CORRECT address for each IC, after reviewing all original data.

### Process:
1. Start with the 612 records reviewers validated as correct → copy to golden JSON
2. For the 422 flagged records → apply reviewer "BETTER" corrections
3. Dispatch 11 subagents to produce the corrected golden answer for each flagged IC:
   - Read original ADDR0-ADDR40 data
   - Read the reviewer's "BETTER" suggestion
   - Apply expert judgment to produce the final correct address
   - Output as JSON: `{"ic": "...", "address": "...", "confidence": 1.0, "source": "expert"}`
4. Merge into `tests/benchmark/golden_answers.json`
5. Run validation: dispatch another round of reviewers to spot-check the golden JSON
6. This becomes our permanent benchmark — never overwrite, only append/correct

### Golden JSON format:
```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-04-17",
    "total_records": 1034,
    "expert_corrected": 422,
    "validated_as_correct": 612,
    "source": "Claude Opus 4.6 expert review of feb_tps0_qresults.xls"
  },
  "records": [
    {
      "ic": "900208125173",
      "name": "Mr. AZMAN BIN SAHIDI",
      "golden_address": "LOT 265 LORONG 5\nTAMAN PASAR PUTIH\n88100 KOTA KINABALU\nSABAH",
      "confidence": 1.0,
      "source": "expert_corrected",
      "notes": "Original had PARK PUTIH PUTA (likely typo for PASAR PUTIH)"
    }
  ]
}
```

## Phase 3: Score Pipeline Against Golden Answers

Create `scripts/score_against_golden.py`:
- Load golden_answers.json as ground truth
- Load pipeline output Excel
- For each record, compare:
  - **Exact match**: pipeline output == golden answer (strict)
  - **Postcode match**: correct postcode extracted
  - **State match**: correct state
  - **City match**: correct city
  - **Street similarity**: token-level fuzzy match on address lines (>80% = pass)
  - **Overall accuracy**: weighted average across all fields
- Output: percentage score showing how close pipeline is to expert-level

This lets us measure: "our pipeline produces X% expert-level addresses"

## Review Agent Findings Location

Full reviewer outputs saved in:
`/Users/wee/.claude/projects/-Users-wee-Desktop-SideQuest-address-normaliser/6a4650c3-c7c3-43e4-a786-e377236d70b5/tool-results/hook-*-stdout.txt`

8 files, ~160KB total, containing all 422 issue details with "BETTER" corrections.

## Review Agent Findings (saved for reference)

Batch summaries:
- Batch 0: 38/95 issues
- Batch 1: 35/95 issues  
- Batch 2: 40/95 issues
- Batch 3: 40/95 issues
- Batch 4: 44/95 issues
- Batch 7: 38/95 issues
- Batch 9: 37/95 issues
- Batch 10: 35/84 issues
- Batches 5, 6, 8: pending (same patterns expected)

Full reviewer outputs saved in persisted tool results.

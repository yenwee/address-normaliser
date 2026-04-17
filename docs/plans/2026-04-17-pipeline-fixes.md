# Pipeline Fixes — Validated Against Golden Answers

## Current Score: 94.4% (Grade A)

## Top Pipeline Bugs (from golden answer cross-validation)

### Bug 1: Wrong cluster picked (5 records confirmed wrong)
ICs: 860813565210, 820412125058, 870122565149, 831030105266, 841006016473

**Root cause**: When two clusters have similar frequency × completeness scores, 
the pipeline sometimes picks the wrong one. The postcode frequency count is the 
most reliable signal but isn't always used as the primary tiebreaker.

**Fix**: After scoring clusters, add a postcode-frequency tiebreaker:
```python
# Current: cluster_score = len(cluster) * max_completeness
# Better:  also factor in postcode consistency
postcode_counts = Counter(a['postcode'] for a in cluster if a['postcode'])
postcode_consistency = max(postcode_counts.values()) / len(cluster) if postcode_counts else 0
cluster_score = len(cluster) * max_completeness * (0.5 + 0.5 * postcode_consistency)
```

### Bug 2: Duplicated text in address lines (~130 records)
Example: `JALAN K2 JALAN K2`, `TAMAN PERTIWI JALAN PERTIW 3`

**Root cause**: Ensemble enhancement pulls address_line2 from a cluster sibling 
that has the same street name, creating duplication.

**Fix**: In formatter, after combining all lines, scan for repeated 2+ word 
phrases within each line and deduplicate:
```python
def _dedup_within_line(line):
    words = line.split()
    for length in range(len(words)//2, 1, -1):
        for i in range(len(words) - 2*length + 1):
            phrase = words[i:i+length]
            next_phrase = words[i+length:i+2*length]
            if phrase == next_phrase:
                return ' '.join(words[:i+length] + words[i+2*length:])
    return line
```

### Bug 3: Truncated JALAN/KAMPUNG/BATU (~70 records)
Example: `NO 230 JALAN` (street name missing after JALAN)

**Root cause**: Source data has "Jalan" as separate comma field. Parser puts it in 
address_line2. The _merge_standalone_words function in pipeline merges it with 
address_line3, but if address_line3 is empty, "JALAN" stays alone.

**Fix**: In parser, when a field is exactly "Jalan"/"Kampung"/"Batu"/"Lorong" 
(single word, known label), concatenate with the NEXT non-empty field regardless 
of position, not just the adjacent one.

### Bug 4: Missing state (~35 records)
**Fix**: After validator.correct_address(), if state is still empty, use 
POSTCODE_STATE_PREFIXES to fill it. The validator already has this logic but 
it's not always triggered.

### Bug 5: SRI→SERI wrong expansion (~15 records)
**Fix**: Remove SRI→SERI from ABBREVIATIONS dict. SRI is a valid Malay word 
(honorific), not an abbreviation of SERI.

### Bug 6: Dot-separated junk not cleaned (e.g. 432.P5.KOLEJ15.UPM)
**Fix**: In normaliser, replace periods between alphanumeric characters with 
spaces: `re.sub(r'(\w)\.(\w)', r'\1 \2', text)`

### Bug 7: "Batu" standalone field artifact
**Fix**: In parser, when a field is exactly "Batu" (the Malay word for 
milestone/stone) without a number following, treat as empty. Only keep "Batu" 
when followed by a number (e.g. "Batu 7").

## Estimated Impact

| Fix | Records improved | Score impact |
|-----|-----------------|-------------|
| Duplicated text | ~130 | +3-4% |
| Truncated words | ~70 | +2-3% |
| Missing state | ~35 | +0.5% |
| Wrong cluster | ~5 | +0.3% |
| SRI→SERI | ~15 | +0.2% |
| Dot cleanup | ~5 | +0.1% |
| Batu artifact | ~20 | +0.3% |
| **Total** | **~280** | **+6-8%** |

## Target: 94.4% → ~100% (Grade A+)

# Harjit Feedback Cases (2026-04-23)

## Source File on Google Drive

All reported screenshots map to:

- `16apr_new_query_results_NORMALISED.xlsx`
  - Drive file ID: `1JMw8mL6mheZjSVc7WwQ6dloNiHjiPUWE`
  - Created: `2026-04-20T04:16:00.497Z`
- Duplicate copy (same issue rows):
  - Drive file ID: `1qBq2-aK8NyOS2cE0k1hJ6gTv3ZH9uXQQ`
  - Created: `2026-04-20T04:14:46.984Z`

## Case List

1. **Not-popular address picked over popular one**
   - IC: `820624085182`
   - Output snippet: `...SUWAY MEDICAL CENTRE... 46150 PETALING JAYA`
   - Complaint: frequent `47500 SUBANG JAYA` variants were ignored.
   - Category: selection weighting / cluster winner.

2. **`PS` expanded wrongly to `PETI SURAT`**
   - IC: `820620055189`
   - Output snippet: `PETI SURAT 5/13 ... TAMAN PINGGIRAN SUNGAI GADUT`
   - Complaint: `PS` means `PINGGIRAN SENAWANG`, not PO Box.
   - Category: abbreviation collision.

3. **Two addresses merged into one synthetic address**
   - IC: `740704075427`
   - Output snippet: `34 BU 7/8 BANDAR UTAMA JALAN TAN SERI TEH EWE LIM ...`
   - Complaint: mixed Petaling Jaya + Penang components.
   - Category: cross-cluster merge leak.

4. **Better address not picked**
   - IC: `950312105469`
   - Output snippet: `NO 57 D 2B JALAN DATO DAGANG 31 ...`
   - Complaint: a more complete/clean variant exists in source.
   - Category: within-cluster candidate ranking.

5. **Abbreviation expansion too aggressive (`SG`, `LG`)**
   - Example IC shown: `940514086068`
   - Output snippet: `NO 436 JALAN TM ...`
   - Complaint: `SG/LG` should not always be expanded globally.
   - Category: normalisation safety.

6. **KL postcode locality override (`SETAPAK`)**
   - Example IC shown: `901225146106` (and many others)
   - Output snippet: `53300 SETAPAK` (user expects `KUALA LUMPUR`)
   - Complaint: 50000-60000 KL postcodes forced into locality names.
   - Category: validator city override policy.

7. **Popular address not picked**
   - IC: `900806025818`
   - Output snippet: `NO 39 JALAN / KAMPUNG MASJID / 06600 KUALA KEDAH`
   - Complaint: more frequent source variant not selected.
   - Category: selection consensus logic.

8. **City changed from `MERSING` to `TIOMAN`**
   - IC: `900627016721` (and other `86800` rows)
   - Output snippet: `86800 TIOMAN JOHOR`
   - Complaint: source system city is `MERSING`.
   - Category: one-to-many postcode city mapping in validator.

9. **Address not present in source system**
   - IC: `900122145229`
   - Output snippet: `NO 19 JALAN INTAN 6 / APARTMENT SERI MURNI FASA II / 43200 CHERAS`
   - Complaint: output became synthetic composite not found as-is in source.
   - Category: over-enrichment / synthetic assembly.

10. **`TAMAN` dropped**
    - IC: `890617015155`
    - Output snippet: `NO 2 JALAN PADI MASRIA / 83200 SENGGARANG / JOHOR`
    - Complaint: should retain `TAMAN SENGGARANG`.
    - Category: line reorder / area token loss.

11. **Incomplete address chosen despite complete address existing**
    - IC: `720823095094`
    - Output snippet: `KAMPUNG TITI TINGGI JALAN / 02100 PADANG BESAR / PERLIS`
    - Complaint: complete `NO 14 TAMAN SENA INDAH ... KANGAR PERLIS` exists.
    - Category: completeness vs popularity decision.

## Working Order (Recommended)

1. Block synthetic merges (Cases 3, 9).
2. Fix abbreviation collisions/safety (Cases 2, 5).
3. Fix selection consensus/completeness ranking (Cases 1, 4, 7, 11).
4. Fix validator city policy for shared postcodes (Cases 6, 8).
5. Fix formatter area-token retention (Case 10).

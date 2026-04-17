"""Cluster-based enrichment of the selected address.

Two kinds of enrichment applied in order:

1. enrich_from_cluster: light merge
   - Add JALAN/LORONG prefix to bare street number patterns (e.g. "2/12A")
   - Cross-cluster street name borrowing when clusters describe the same place

2. ensemble_enhance: fill missing fields from cluster majority vote
   - Fill empty address_line2 / postcode / city / state
   - Word-level spelling correction on address_line

Both steps only ADD info; they never replace existing non-empty fields
(except for word-level spelling which swaps individual misspelled tokens).
"""

import re
from collections import Counter

from src.processing.parser import KNOWN_STATES
from src.steps.select import find_best_cluster


def enrich_from_cluster(best_addr: dict, clusters: list) -> dict:
    """Light merge: enrich the best address with specific info from cluster siblings.

    Currently handles:
    - Missing JALAN/LORONG prefix before street number patterns (e.g. "2/12A")
    - Cross-cluster street name borrowing when addresses describe same place
    """
    # Find the cluster that contains best_addr (not always the highest-scoring
    # cluster, since popularity scoring may have selected a different one)
    best_cluster = None
    for c in clusters:
        if any(a is best_addr for a in c):
            best_cluster = c
            break
    if best_cluster is None:
        best_cluster = find_best_cluster(clusters)

    if len(best_cluster) < 2 and len(clusters) < 2:
        return best_addr

    enriched = dict(best_addr)
    addr_line = enriched.get("address_line", "")

    # Check for street number pattern without JALAN/LORONG prefix
    # e.g. "NO 69 2/12A" — the "2/12A" looks like a street ref
    street_num_pattern = re.search(r"\b(\d+/\d+\w?)\b", addr_line)
    if street_num_pattern:
        num = street_num_pattern.group(1)
        has_prefix = bool(re.search(
            rf"\b(?:JALAN|LORONG|PERSIARAN|LEBUH)\s+{re.escape(num)}",
            addr_line, re.IGNORECASE,
        ))

        if not has_prefix:
            # Search cluster siblings for JALAN/LORONG before this number
            for sibling in best_cluster:
                sib_line = sibling.get("address_line", "") + " " + sibling.get("address_line2", "")
                m = re.search(
                    rf"\b(JALAN|LORONG|PERSIARAN|LEBUH)\s+{re.escape(num)}",
                    sib_line, re.IGNORECASE,
                )
                if m:
                    prefix = m.group(1)
                    enriched["address_line"] = re.sub(
                        rf"\b{re.escape(num)}\b",
                        f"{prefix} {num}",
                        enriched["address_line"],
                        count=1,
                    )
                    break

    # Cross-cluster street enrichment: if selected address has no street keyword
    # on EITHER line, borrow from another cluster describing the SAME place.
    addr_line = enriched.get("address_line", "")
    addr_line2 = enriched.get("address_line2", "")
    _STREET_KW_RE = re.compile(r"\b(?:JALAN|LORONG|PERSIARAN|LEBUH)\b", re.IGNORECASE)
    if not _STREET_KW_RE.search(addr_line) and not _STREET_KW_RE.search(addr_line2):
        best_pc = enriched.get("postcode", "")
        if best_pc:
            from rapidfuzz import fuzz as _fuzz
            best_text = " ".join(filter(None, [
                enriched.get("address_line", ""),
                enriched.get("address_line2", ""),
                enriched.get("city", ""),
            ])).upper()

            for other_cluster in clusters:
                if other_cluster is best_cluster:
                    continue
                for sib in other_cluster:
                    sib_pc = sib.get("postcode", "")
                    if sib_pc != best_pc:
                        continue
                    sib_line = sib.get("address_line", "")
                    if not _STREET_KW_RE.search(sib_line):
                        continue
                    # Guard 1: reject if borrowed line embeds a postcode
                    if re.search(r"\b\d{5}\b", sib_line):
                        continue
                    # Guard 2: reject if current content not found in borrowed
                    addr_clean = re.sub(r"[\s\-.]", "", addr_line.upper())
                    sib_clean = re.sub(r"[\s\-.]", "", sib_line.upper())
                    if addr_clean and addr_clean[:5] not in sib_clean:
                        # Clusters must also be semantically similar
                        sib_text = " ".join(filter(None, [
                            sib.get("address_line", ""),
                            sib.get("address_line2", ""),
                            sib.get("city", ""),
                        ])).upper()
                        if _fuzz.token_sort_ratio(best_text, sib_text) < 55:
                            continue
                    enriched["address_line"] = sib_line
                    break
                else:
                    continue
                break

    return enriched


def ensemble_enhance(best_addr: dict, cluster: list) -> dict:
    """Fill missing fields from cluster majority vote. Never replace non-empty fields."""
    if len(cluster) < 2:
        return best_addr

    enhanced = dict(best_addr)

    # Fill empty address_line2 from cluster siblings
    if not enhanced.get("address_line2", "").strip():
        l2_candidates = []
        for a in cluster:
            l2 = a.get("address_line2", "").strip()
            if l2 and l2.upper() not in KNOWN_STATES:
                if not re.search(r"\b\d{5}\b", l2):
                    l2_candidates.append(l2)
        if l2_candidates:
            enhanced["address_line2"] = Counter(l2_candidates).most_common(1)[0][0]

    # Fill empty postcode
    if not enhanced.get("postcode", "").strip():
        pcs = [a["postcode"] for a in cluster if re.match(r"^\d{5}$", a.get("postcode", ""))]
        if pcs:
            enhanced["postcode"] = Counter(pcs).most_common(1)[0][0]

    # Fill empty city
    if not enhanced.get("city", "").strip():
        cities = [a["city"] for a in cluster if a["city"].strip()]
        if cities:
            enhanced["city"] = Counter(cities).most_common(1)[0][0]

    # Fill empty state
    if not enhanced.get("state", "").strip():
        states = [a["state"] for a in cluster if a["state"].strip()]
        if states:
            enhanced["state"] = Counter(states).most_common(1)[0][0]

    # Word-level spelling correction: fix individual misspelled words using
    # cluster majority vote. Only swaps words at the same position when the
    # majority spelling differs. Requires 3+ structurally similar lines.
    addr_line = enhanced.get("address_line", "").strip()
    if addr_line and len(cluster) >= 3:
        from rapidfuzz import fuzz
        words = addr_line.split()
        similar_lines = []
        for a in cluster:
            sib = a.get("address_line", "").strip()
            if sib and len(sib.split()) == len(words):
                similar_lines.append(sib.split())

        if len(similar_lines) >= 2:
            corrected = list(words)
            for i, word in enumerate(words):
                if re.match(r"^\d+$", word) or len(word) <= 2:
                    continue
                spellings = Counter()
                for sib_words in similar_lines:
                    sib_word = sib_words[i]
                    if fuzz.ratio(word.upper(), sib_word.upper()) > 60:
                        spellings[sib_word] += 1
                if not spellings:
                    continue
                majority_word, majority_count = spellings.most_common(1)[0]
                current_count = spellings.get(word, 0)
                # Only swap if majority is larger, words are similar but different,
                # and we're not dropping a suffix (e.g. 1084D -> 1084)
                if (majority_count > current_count
                        and majority_word.upper() != word.upper()
                        and fuzz.ratio(word.upper(), majority_word.upper()) > 60
                        and not (len(majority_word) < len(word)
                                 and word.startswith(majority_word))):
                    corrected[i] = majority_word
            enhanced["address_line"] = " ".join(corrected)

    return enhanced

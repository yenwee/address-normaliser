"""Address clusterer for grouping similar Malaysian address variants.

Clusters address dicts that refer to the same physical location using
fuzzy string matching via rapidfuzz token_sort_ratio. Handles typos,
abbreviations, and word reordering common in Malaysian address data.
"""

from rapidfuzz.fuzz import token_sort_ratio


def _address_text(addr: dict) -> str:
    """Combine address fields into a single comparable string.

    Joins address_line, address_line2, and postcode (uppercased),
    skipping any empty parts.

    Args:
        addr: Address dict with keys address_line, address_line2, postcode.

    Returns:
        Uppercased combined string for fuzzy comparison.
    """
    parts = [
        addr.get("address_line", ""),
        addr.get("address_line2", ""),
        addr.get("postcode", ""),
    ]
    combined = " ".join(p for p in parts if p)
    return combined.upper()


def _similarity(addr1: dict, addr2: dict) -> float:
    """Compute token-sort similarity between two address dicts.

    Uses rapidfuzz token_sort_ratio which handles word reordering
    by sorting tokens alphabetically before comparison.

    Args:
        addr1: First address dict.
        addr2: Second address dict.

    Returns:
        Similarity score from 0 to 100.
    """
    text1 = _address_text(addr1)
    text2 = _address_text(addr2)
    return token_sort_ratio(text1, text2)


def cluster_addresses(addresses: list[dict], threshold: float = 65) -> list[list[dict]]:
    """Group addresses by fuzzy similarity into clusters.

    For each unassigned address, creates a new cluster and compares it
    against all remaining unassigned addresses. Addresses with similarity
    at or above the threshold are added to the same cluster.

    Args:
        addresses: List of address dicts (from parser output).
        threshold: Minimum token_sort_ratio score (0-100) to consider
            two addresses as the same location. Default 65.

    Returns:
        List of clusters, where each cluster is a list of address dicts
        that refer to the same physical location.
    """
    if not addresses:
        return []

    assigned = [False] * len(addresses)
    clusters: list[list[dict]] = []

    for i, addr in enumerate(addresses):
        if assigned[i]:
            continue

        cluster = [addr]
        assigned[i] = True

        for j in range(i + 1, len(addresses)):
            if assigned[j]:
                continue
            if _similarity(addr, addresses[j]) >= threshold:
                cluster.append(addresses[j])
                assigned[j] = True

        clusters.append(cluster)

    return clusters

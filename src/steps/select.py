"""Address cluster selection.

Selects the best cluster and then the best address within that cluster.

Cluster scoring factors:
  - size (more members = more evidence)
  - max completeness (well-formed address)
  - postcode consistency (members agree on postcode within cluster)
  - raw postcode popularity (cluster's postcode appears often across all ADDR columns)

Within-cluster selection:
  - completeness score (primary)
  - consensus / descriptiveness tiebreaker when scores are close
"""

from collections import Counter
from typing import Optional

from src.processing.scorer import score_completeness

MAX_COMPLETENESS_SCORE = 12
_POPULARITY_WEIGHT = 0.5


def select_best_address(
    clusters: list[list[dict]],
    raw_postcode_counts: Optional[Counter] = None,
) -> tuple[Optional[dict], float]:
    """Select the best address from clustered address variants.

    Scores each cluster by: len(cluster) * max(score_completeness(addr)),
    factored by postcode consistency and raw postcode popularity.

    Args:
        clusters: List of address clusters from cluster_addresses.
        raw_postcode_counts: Postcode frequency across ALL raw ADDR columns.

    Returns:
        Tuple of (best_address_dict, confidence) or (None, 0.0).
    """
    if not clusters:
        return None, 0.0

    max_raw = max(raw_postcode_counts.values()) if raw_postcode_counts else 0

    best_cluster = None
    best_cluster_score = -1

    for cluster in clusters:
        if not cluster:
            continue
        max_addr_score = max(score_completeness(addr) for addr in cluster)
        # Factor in postcode consistency: clusters where members agree on postcode score higher
        postcodes = [a["postcode"] for a in cluster if a.get("postcode", "").strip()]
        if postcodes:
            postcode_counts = Counter(postcodes)
            postcode_consistency = max(postcode_counts.values()) / len(cluster)
            dominant_pc = postcode_counts.most_common(1)[0][0]
        else:
            postcode_consistency = 0
            dominant_pc = ""
        cluster_score = len(cluster) * max_addr_score * (0.5 + 0.5 * postcode_consistency)
        # Factor in raw postcode popularity across all ADDR columns
        if raw_postcode_counts and max_raw and dominant_pc:
            popularity = raw_postcode_counts.get(dominant_pc, 0) / max_raw
            cluster_score *= (1 - _POPULARITY_WEIGHT + _POPULARITY_WEIGHT * popularity)
        if cluster_score > best_cluster_score:
            best_cluster_score = cluster_score
            best_cluster = cluster

    if best_cluster is None:
        return None, 0.0

    best_addr = select_from_cluster(best_cluster)
    confidence = min(score_completeness(best_addr) / MAX_COMPLETENESS_SCORE, 1.0)

    return best_addr, confidence


def select_from_cluster(cluster: list[dict]) -> dict:
    """Select the best address from a cluster using completeness + consensus.

    When multiple addresses have similar completeness scores, prefer the one
    whose street name pattern is agreed upon by more cluster members.
    E.g. if 2 addresses say 'LORONG PUTERI GUNUNG' and 1 says 'LORONG 3',
    prefer the descriptive version even if the generic one scores slightly higher.
    """
    if len(cluster) == 1:
        return cluster[0]

    scored = [(addr, score_completeness(addr)) for addr in cluster]
    max_score = max(s for _, s in scored)

    # If clear winner (3+ points ahead of all others), just pick it
    runner_up = sorted(set(s for _, s in scored), reverse=True)
    if len(runner_up) >= 2 and runner_up[0] - runner_up[1] >= 3:
        return max(cluster, key=score_completeness)

    # Close scores — use consensus tiebreaker
    # Within 2 points of max, factor in how many cluster members agree
    from rapidfuzz import fuzz
    top_addrs = [(a, s) for a, s in scored if s >= max_score - 2]

    best = None
    best_combined = -1
    for addr, sc in top_addrs:
        consensus = sum(
            1 for other in cluster
            if fuzz.token_sort_ratio(addr["address_line"], other["address_line"]) > 70
        )
        # Consensus can override up to a 2-point score gap
        combined = sc + consensus * 2
        if combined > best_combined:
            best_combined = combined
            best = addr

    return best


def find_best_cluster(clusters: list) -> list:
    """Return the cluster that matches select_best_address's scoring."""
    best = None
    best_score = -1
    for cluster in clusters:
        if not cluster:
            continue
        max_addr_score = max(score_completeness(a) for a in cluster)
        postcodes = [a["postcode"] for a in cluster if a.get("postcode", "").strip()]
        if postcodes:
            postcode_consistency = max(Counter(postcodes).values()) / len(cluster)
        else:
            postcode_consistency = 0
        score = len(cluster) * max_addr_score * (0.5 + 0.5 * postcode_consistency)
        if score > best_score:
            best_score = score
            best = cluster
    return best or []

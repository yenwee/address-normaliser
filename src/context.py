"""Shared state passed through the address processing pipeline.

Each step takes an AddressContext, mutates the relevant fields, and returns
the context. This keeps pipeline step signatures consistent and makes it
easy to inspect or log intermediate state during development.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AddressContext:
    """Shared state passed through pipeline steps.

    Attributes:
        ic: ICNO string (Malaysian IC number).
        name: Person's name.
        parsed: List of parsed address dicts from parse_all_addresses.
        normalised: List of normalised address dicts (uppercased, expanded).
        clusters: List of address clusters from cluster_addresses.
        raw_postcode_counts: Frequency of each postcode across raw ADDR columns.
            Used for popularity-weighted cluster scoring.
        best_cluster: The selected cluster (list of address dicts).
        best_address: The selected address dict from best_cluster.
        confidence: Normalised completeness score (0.0 to 1.0).
        mailing_block: Final formatted multi-line mailing address string.
    """

    ic: str
    name: str
    parsed: list[dict] = field(default_factory=list)
    normalised: list[dict] = field(default_factory=list)
    clusters: list[list[dict]] = field(default_factory=list)
    raw_postcode_counts: Counter = field(default_factory=Counter)
    best_cluster: Optional[list[dict]] = None
    best_address: Optional[dict] = None
    confidence: float = 0.0
    mailing_block: str = ""

"""Accession namespace regexes + structural modality routing (SPEC 4).

Single source of truth. Detection is structural (namespace, repository, structured
metadata), never prose-based. Stdlib only.
"""
from __future__ import annotations

import re

from .enums import Modality, Repository

# (regex, repository, default modality or None meaning "QUERY the source API")
NAMESPACE: list[tuple[re.Pattern[str], Repository, Modality | None]] = [
    (re.compile(r"^PXD\d+$", re.I), Repository.PRIDE, Modality.PROTEOMICS_MS),
    (re.compile(r"^MSV\d+$", re.I), Repository.MASSIVE, Modality.PROTEOMICS_MS),
    (re.compile(r"^JPST\d+$", re.I), Repository.JPOST, Modality.PROTEOMICS_MS),
    (re.compile(r"^MTBLS\d+$", re.I), Repository.METABOLIGHTS, Modality.METABOLOMICS),
    (re.compile(r"^ST\d+$", re.I), Repository.METABOLOMICS_WORKBENCH, Modality.METABOLOMICS),
    (re.compile(r"^(GSE|GSM)\d+$", re.I), Repository.GEO, None),
    (re.compile(r"^E-\w+-\d+$", re.I), Repository.ARRAYEXPRESS, None),
    (re.compile(r"^(SRR|SRX|SRP|PRJNA)\w+$", re.I), Repository.SRA, None),
]

# Any well-formed accession or platform id (used by the verifier for format checks).
ACCESSION_RE = re.compile(r"^(GSE|GSM|GPL|SRR|SRX|SRP|PRJNA|E-\w+-|PXD|MSV|JPST|MTBLS|ST)\w*$", re.I)


def classify_namespace(accession: str) -> tuple[Repository, Modality | None, bool]:
    """Return (repository, default_modality_or_None, namespace_valid)."""
    for rx, repo, mod in NAMESPACE:
        if rx.match(accession.strip()):
            return repo, mod, True
    return Repository.UNKNOWN, Modality.UNKNOWN, False


def is_well_formed(accession: str) -> bool:
    return bool(ACCESSION_RE.match((accession or "").strip()))

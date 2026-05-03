"""
Controlled-vocabulary loader.

Loads SKOS-lite YAML files from `vocabularies/` and provides lookup helpers.
Transforms validate against these vocabularies — unknown terms are logged
and surfaced as warnings, not failures, so source drift doesn't break the
pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

LOG = logging.getLogger(__name__)
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "vocabularies"


@dataclass(frozen=True)
class Vocabulary:
    scheme: str
    title: str
    by_source_term: dict[str, str]   # source_term -> id
    by_id: dict[str, dict]           # id -> full term dict


def load(name: str, vocab_dir: Path = DEFAULT_DIR) -> Vocabulary:
    path = vocab_dir / f"{name}.yaml"
    with path.open() as fh:
        data = yaml.safe_load(fh)
    by_source_term: dict[str, str] = {}
    by_id: dict[str, dict] = {}
    for term in data.get("terms", []):
        by_id[term["id"]] = term
        if "source_term" in term:
            by_source_term[term["source_term"]] = term["id"]
    return Vocabulary(
        scheme=data["scheme"],
        title=data["title"],
        by_source_term=by_source_term,
        by_id=by_id,
    )


@lru_cache(maxsize=8)
def _cached(name: str) -> Vocabulary:
    return load(name)


def normalize(name: str, source_term: str) -> str:
    """Map a source term to its canonical id. Unknown terms pass through with a warning."""
    if source_term is None:
        return source_term
    vocab = _cached(name)
    if source_term in vocab.by_source_term:
        return vocab.by_source_term[source_term]
    LOG.warning("unknown term in vocabulary %r: %r", name, source_term)
    return source_term

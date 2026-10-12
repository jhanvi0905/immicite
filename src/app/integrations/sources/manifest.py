"""Loads the source registry (sources.yaml): which documents make up the corpus."""

from pathlib import Path

import yaml

from app.domain.corpus import Source


def load_manifest(path: Path) -> list[Source]:
    entries = yaml.safe_load(path.read_text())["sources"]
    sources = [Source.model_validate(entry) for entry in entries]
    slugs = [source.slug for source in sources]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise ValueError(f"duplicate source slugs in {path}: {', '.join(duplicates)}")
    return sources

"""Command-line entry point for jobs: `immicite ingest`, `immicite status`.

Like main.py, this is a composition root: it wires integrations into services.
"""

import argparse
import asyncio
import logging
import sys

from app.config import Settings
from app.domain.corpus import Authority
from app.domain.ports import IngestAlreadyRunning
from app.integrations.db.repository import PostgresCorpusRepository, create_engine
from app.integrations.http import PoliteClient
from app.integrations.sources.manifest import load_manifest
from app.integrations.sources.reader import HttpSourceReader
from app.services.ingest import Outcome, ingest, retire_removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="immicite")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest_parser = commands.add_parser("ingest", help="pull sources into the corpus")
    ingest_parser.add_argument(
        "--authority", choices=[level.value for level in Authority], help="only this level"
    )
    ingest_parser.add_argument("--source", action="append", metavar="SLUG", help="only this source")
    ingest_parser.add_argument(
        "--dry-run", action="store_true", help="fetch and parse, write nothing"
    )

    commands.add_parser("status", help="show what the corpus holds")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    if args.command == "ingest":
        return asyncio.run(_ingest(settings, args.authority, args.source, args.dry_run))
    return asyncio.run(_status(settings))


async def _ingest(
    settings: Settings, authority: str | None, slugs: list[str] | None, dry_run: bool
) -> int:
    sources = load_manifest(settings.sources_manifest)
    unknown = set(slugs or ()) - {s.slug for s in sources}
    if unknown:
        print(f"unknown source: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    selected = [
        s
        for s in sources
        if (authority is None or s.authority == authority) and (not slugs or s.slug in slugs)
    ]
    if not selected:
        print("no sources match", file=sys.stderr)
        return 2

    engine = create_engine(settings.database_url)
    repository = PostgresCorpusRepository(engine)
    client = PoliteClient()
    retired: list[str] = []
    try:
        reader = HttpSourceReader(client, sources)
        results = await ingest(selected, reader, repository, dry_run=dry_run)
        if not dry_run:
            retired = await retire_removed(sources, repository)
    except IngestAlreadyRunning:
        print("another ingest is already running", file=sys.stderr)
        return 3
    finally:
        await client.aclose()
        await engine.dispose()

    for result in results:
        detail = result.error or f"{result.segments} segments"
        print(f"{result.outcome:<10} {detail:<14} {result.slug}")
    for slug in retired:
        print(f"{'retired':<10} {'':<14} {slug}")
    return 1 if any(r.outcome is Outcome.FAILED for r in results) else 0


async def _status(settings: Settings) -> int:
    engine = create_engine(settings.database_url)
    try:
        rows = await PostgresCorpusRepository(engine).status()
    finally:
        await engine.dispose()
    live = [row for row in rows if row.current_segments]
    print(f"{'authority':<26}{'versions':>8}{'segments':>10}{'unembedded':>12}  source")
    for row in live:
        print(
            f"{row.authority:<26}{row.versions:>8}{row.current_segments:>10}"
            f"{row.unembedded_segments:>12}  {row.slug}"
        )
    if len(live) < len(rows):
        print(f"({len(rows) - len(live)} retired sources not shown)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fetches a source over HTTP and parses it with the parser for its kind."""

from collections.abc import Callable, Iterable

from app.domain.corpus import ParsedDocument, Source, SourceKind
from app.domain.links import LinkResolver
from app.integrations.http import PoliteClient
from app.integrations.sources import canada_ca, justice_laws

Parser = Callable[[Source, bytes, LinkResolver], ParsedDocument]

PARSERS: dict[SourceKind, Parser] = {
    SourceKind.LAW_XML: justice_laws.parse,
    SourceKind.WEB_PAGE: canada_ca.parse,
}


class HttpSourceReader:
    def __init__(self, client: PoliteClient, manifest: Iterable[Source]) -> None:
        self._client = client
        # Built from the whole manifest, so links into any law in the corpus resolve.
        self._resolver = LinkResolver.from_sources(manifest)

    async def read(self, source: Source) -> tuple[bytes, ParsedDocument]:
        parser = PARSERS[source.kind]
        raw = await self._client.get(source.url)
        return raw, parser(source, raw, self._resolver)

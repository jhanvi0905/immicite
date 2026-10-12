"""Stable hashes used to detect change in a source and in a single segment."""

import hashlib
import json

from app.domain.corpus import ParsedDocument, ParsedSegment


def _sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def text_hash(segment: ParsedSegment) -> str:
    """Identifies what would be embedded. An unchanged hash means the embedding is reusable."""
    return _sha256([list(segment.heading_path), segment.body])


def content_hash(document: ParsedDocument) -> str:
    """Identifies a version of a source by its parsed content, not its raw bytes.

    Raw bytes change on every consolidation date or page render even when the text does not.
    """
    return _sha256(
        [
            document.published_on.isoformat() if document.published_on else None,
            [
                [
                    s.ref,
                    s.parent_ref,
                    s.kind,
                    list(s.heading_path),
                    s.body,
                    s.url,
                    s.last_amended_on.isoformat() if s.last_amended_on else None,
                    s.anchor,
                    [
                        [
                            link.origin,
                            link.text,
                            link.target_url,
                            link.target_fragment,
                            link.target_class,
                            link.target_ref,
                        ]
                        for link in s.links
                    ],
                ]
                for s in document.segments
            ],
        ]
    )

"""Retrieval rules that need no model: routing exact refs, and fusing ranked lists."""

import re
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.corpus import Authority, Source, SourceKind


@dataclass(frozen=True)
class RetrievedSegment:
    """A current segment as retrieval returns it, with what a citation needs."""

    id: UUID
    ref: str
    authority: Authority
    heading_path: tuple[str, ...]
    body: str
    url: str
    last_amended_on: date | None


class RefRouter:
    """Finds the law refs a question names outright, such as R205(c)(ii) or IRPA 40(1).

    It only reads the question. Whether a ref exists is for the corpus to say.
    """

    def __init__(self, laws: Mapping[str, str]) -> None:
        # A law's short name as a user writes it -> its ref prefix: {"IRPR": "R"}.
        self._prefixes = {name.upper(): prefix for name, prefix in laws.items()}
        names = "|".join(re.escape(name) for name in self._prefixes)
        prefixes = "|".join(re.escape(prefix) for prefix in set(self._prefixes.values()))
        # A prefix is glued to its number ("R205"); a name stands apart ("IRPR s. 205").
        self._pattern = re.compile(
            rf"(?<![\w.])(?:(?P<name>{names})\s+(?:(?:section|s\.)\s*)?|(?P<prefix>{prefixes}))"
            r"(?P<number>Sch[0-9.]*[0-9]|Sch|[0-9]+(?:\.[0-9]+)*)"
            r"(?P<labels>(?:\([0-9A-Za-z.]+\))*)"
            r"(?P<term>#[a-z0-9-]+)?(?![\w(])",
            re.IGNORECASE,
        )

    @classmethod
    def from_sources(cls, sources: Iterable[Source]) -> "RefRouter":
        return cls({s.slug: s.ref_prefix for s in sources if s.kind is SourceKind.LAW_XML})

    def refs(self, question: str) -> list[str]:
        """The refs named in the question, in the order they appear, without repeats."""
        found = []
        for match in self._pattern.finditer(question):
            name, prefix = match["name"], match["prefix"]
            prefix = self._prefixes[name.upper()] if name else prefix.upper()
            number = re.sub(r"(?i)^sch", "Sch", match["number"])
            # Labels keep their case: (a) is a paragraph and (A) is a clause.
            found.append(prefix + number + match["labels"] + (match["term"] or ""))
        return list(dict.fromkeys(found))


def reciprocal_rank_fusion[T: Hashable](rankings: Sequence[Sequence[T]], k: int = 60) -> list[T]:
    """Merge ranked lists into one, best first.

    An item scores 1 / (k + rank) in each list that holds it. Ties keep the order in
    which items were first seen, so the result is the same on every run.
    """
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda item: -scores[item])

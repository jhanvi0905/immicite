# 0016 · A domain graph of requirements, with every fact tied to a quote
Status: proposed (would amend 0006)

## Context
Retrieved text answers "what does the rule say?". It does not reliably answer "what are
all the requirements for this program, and which facts change them?". A checklist built
from retrieved passages misses a requirement whenever its passage is not retrieved, and
nothing shows that it was missed.

## Decision
- **Two graph layers.** The link graph (0012) records what cites what. A new domain
  graph records what the rules are.
- **The ontology is versioned as code.**
  - Node types: Program, Requirement, Fact, Document, Lookup table, Exemption.
  - Edge types: `leads_to`, `requires`, `depends_on_fact`, `evidenced_by`,
    `checked_against`, `excepted_by`.
  - Every node and edge has `stated_in` provenance: the segment and the exact quote that
    states it.
- **Requirement catalogs**, one per program, are kept in the repo and written in
  readiness order, PGWP first.
- **Extraction.** A model proposes candidates from a segment. Code keeps a candidate only
  if its quote appears word for word in the segment, it maps to a catalog entry, and its
  types are valid. Statements that map to nothing appear in the ingest report.
- **Extraction runs as its own pass after a version is published and never blocks
  ingest**, for the same reason embedding does not (0010).
- Graph facts are versioned with the segments they come from.
- **Storage:** node, edge and provenance tables in the existing Postgres database,
  traversed with recursive SQL (0001).
- **Uses:**
  - the checklist walks the graph: program → requirements → facts. This replaces the
    checklist built from retrieved text in 0006. It still pauses with a LangGraph
    interrupt in its own node to ask for a missing fact. It is offered only for
    structured programs; for others it returns `not_available` and suggests research mode.
  - research mode follows `leads_to` pathways for structured programs.
  - exact conflict detection: the same requirement stated differently at two levels.
  - change impact: one query lists what an amendment affects.
- **Evals:** extraction precision and recall on a labelled sample, per catalog; and the
  graph-walk checklist compared with a model-built checklist.

## Alternatives considered
- Neo4j: a second store to run and keep in step, for a graph of thousands of nodes that
  recursive SQL traverses easily.
- Graphiti: built for an agent's changing memory; our facts change only when a source does.
- GraphRAG-style community summaries: generated text with no quote behind it, which
  breaks "cite or stay silent".
- Model-built checklists with no graph: nothing to check completeness against.

## Consequences
- Extraction is a new model role that reads segments at ingest time, outside any
  request. The word-for-word quote check is what keeps an invented fact out.
- Catalogs are a standing cost per program, and a program is not *structured* without one.
- A fact disappears when the quote behind it does, so an amended clause removes what
  depended on it until extraction runs again.

## Open
- Who writes and reviews catalogs. Eval cases are human-written by rule; catalogs decide
  what counts as a requirement and likely need the same rule.
- The extraction precision target.
- The checklist contract and thread expiry.

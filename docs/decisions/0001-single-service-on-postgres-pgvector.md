# 0001 · Single service on Postgres with pgvector
Status: accepted

## Context
The system needs semantic search, exact keyword search, metadata filters, versioned
sources and lineage from each answer back to its source, at tens of thousands of
segments. One person builds and operates it. Old versions accumulate over time, and
approximate vector indexes apply filters after scanning, which can return far fewer
results than requested.

## Decision
One Python service backed by one Postgres database using pgvector and built-in full-text
search.
- Embeddings use 1,024 dimensions.
- Segments carry an `is_current` flag maintained by ingest.
- HNSW and full-text indexes are partial indexes over current segments.
- Filtered vector queries enable pgvector's iterative index scans.

## Alternatives considered
- Qdrant or Chroma next to a relational database: a second store, a sync process, and
  lineage queries across a network boundary.
- Azure AI Search: strong hybrid search, but it cannot run locally and becomes a second
  source of truth.
- `halfvec` at the full 3,072 dimensions (HNSW supports up to 4,000 for `halfvec`): more
  storage and slower search for a gain not yet measured. Revisit if evals show
  embedding quality is the bottleneck.
- A view selecting each source's latest version: correct results, but old versions
  would crowd the index as they accumulate.

## Consequences
- Versions and lineage are foreign keys, and the same SQL runs locally and on Azure.
- Ingest must flip `is_current` in the same transaction as inserting the new segments.
- Any future embedding model must output 1,024 dimensions or come with a migration.
- Revisit at tens of millions of vectors or heavy multi-tenant filtering.